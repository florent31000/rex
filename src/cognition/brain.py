"""
Rex Brain - Main orchestrator for the robot's intelligence.
Coordinates perception, cognition, and action modules.
"""

import asyncio
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta

from src.utils.logger import log
from src.utils.config import Settings


class RexBrain:
    """
    Main brain orchestrator for Rex.
    
    Coordinates:
    - Perception (camera, microphone, robot state)
    - Cognition (LLM, memory, context)
    - Action (movement, speech, behaviors)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        log_callback: Optional[Callable[[str, str], None]] = None,
        speech_callback: Optional[Callable[[str], None]] = None,
        emotion_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize Rex Brain.
        
        Args:
            config: Configuration dictionary
            log_callback: Callback for logging messages
            speech_callback: Callback when Rex speaks
            emotion_callback: Callback to change eye emotion
        """
        self.config = config
        self._log_callback = log_callback
        self._speech_callback = speech_callback
        self._emotion_callback = emotion_callback
        
        # State
        self._running = False
        self._body_connected = False
        self._listening = False
        self._in_conversation = False
        self._emergency_stop = False
        
        # Conversation state
        self._conversation_start: Optional[datetime] = None
        self._last_speech: Optional[datetime] = None
        self._current_speaker: Optional[str] = None
        
        # Robot state
        self._robot_battery: float = 100.0
        self._phone_battery: float = 100.0
        self._robot_mode: str = "idle"
        
        # Timers
        self._last_scene_analysis: Optional[datetime] = None
        self._last_idle_action: Optional[datetime] = None
        self._last_battery_check: Optional[datetime] = None
        
        # Subsystems - initialized lazily
        self._robot_controller = None
        self._audio_processor = None
        self._camera_processor = None
        self._llm_client = None
        self._speaker = None
        self._memory = None
        self._mission_manager = None
        
        self._init_subsystems()
        
    def _init_subsystems(self):
        """Initialize all subsystems."""
        self._log("Initializing subsystems...", "INFO")
        
        # Rex can work without a body
        self._body_connected = False
        self._log("Note: Robot body not connected - Rex can talk but not move", "WARNING")
        
        # Initialize LLM client
        try:
            from src.cognition.llm_client import LLMClient
            self._llm_client = LLMClient(self.config, log_callback=self._log)
            self._log("LLM client initialized (Claude)", "SUCCESS")
        except Exception as e:
            self._log(f"LLM client failed: {e}", "ERROR")
            
        # Initialize speaker (TTS)
        try:
            from src.action.speaker import Speaker
            self._speaker = Speaker(self.config, log_callback=self._log)
            self._log("Speaker initialized (OpenAI TTS)", "SUCCESS")
        except Exception as e:
            self._log(f"Speaker failed: {e}", "ERROR")
            
        # Initialize mission manager
        try:
            from src.cognition.mission_manager import MissionManager
            self._mission_manager = MissionManager(log_callback=self._log)
            self._mission_manager.set_action_executor(self._execute_action)
            self._log("Mission manager initialized", "SUCCESS")
        except Exception as e:
            self._log(f"Mission manager failed: {e}", "ERROR")
            
        # Audio processor will be started separately
        self._audio_initialized = False
        
        self._running = True
        self._log("Subsystems initialized", "SUCCESS")
        
    @property
    def has_body(self) -> bool:
        """Check if robot body is connected."""
        return self._body_connected
        
    @property
    def body_status(self) -> str:
        """Get body connection status for display."""
        if self._body_connected:
            return "🤖 Body connected"
        else:
            return "🧠 Brain only (no body)"
            
    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        log(message, level)
        if self._log_callback:
            self._log_callback(message, level)
            
    def _set_emotion(self, emotion: str):
        """Set the eye emotion."""
        if self._emotion_callback:
            self._emotion_callback(emotion)
            
    async def _speak(self, text: str):
        """Make Rex speak using TTS."""
        if not text:
            self._log("🗣️ _speak called with empty text, skipping", "WARNING")
            return
        
        self._log(f"🗣️ _speak called with: {text}", "INFO")
        
        # Notify UI (this will also log the speech)
        if self._speech_callback:
            self._speech_callback(text)
            
        # Set emotion based on content
        if "!" in text or "super" in text.lower() or "génial" in text.lower():
            self._set_emotion("happy")
        elif "?" in text:
            self._set_emotion("curious")
        elif "désolé" in text.lower() or "pardon" in text.lower():
            self._set_emotion("sad")
        elif "attention" in text.lower() or "stop" in text.lower():
            self._set_emotion("angry")
        else:
            self._set_emotion("neutral")
            
        # Mute microphone while speaking (avoid hearing ourselves)
        if self._audio_processor:
            self._log("🔇 Microphone muted", "INFO")
            self._audio_processor.mute()
        else:
            self._log("⚠️ No audio processor to mute", "WARNING")
            
        # Actually speak using TTS
        if self._speaker:
            self._log("🔊 Calling speaker.speak()...", "INFO")
            try:
                await self._speaker.speak(text)
                self._log("🔊 speaker.speak() completed", "SUCCESS")
            except Exception as e:
                import traceback
                self._log(f"🔊 TTS error: {e}", "ERROR")
                self._log(f"🔊 Traceback: {traceback.format_exc()[:200]}", "ERROR")
        else:
            self._log("⚠️ No speaker available!", "WARNING")
                
        # Unmute microphone after speaking
        if self._audio_processor:
            self._log("🔊 Microphone unmuted", "INFO")
            self._audio_processor.unmute()
                
    async def start_listening(self):
        """Start the audio processor for listening."""
        if self._audio_initialized:
            return
            
        self._log("Starting audio listening...", "INFO")
        
        try:
            from src.perception.audio_processor import AudioProcessor
            
            self._audio_processor = AudioProcessor(
                self.config,
                on_transcription=self._on_transcription,
                on_wake_word=self._on_wake_word,
                log_callback=self._log
            )
            
            await self._audio_processor.start()
            self._audio_initialized = True
            self._listening = True
            self._log("Audio listening started!", "SUCCESS")
            
        except Exception as e:
            self._log(f"Failed to start audio: {e}", "ERROR")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()[:300]}", "ERROR")
            
    def _on_wake_word(self):
        """Called when wake word is detected."""
        self._log("Wake word detected! 👋", "SUCCESS")
        self._in_conversation = True
        self._conversation_start = datetime.now()
        self._set_emotion("excited")
        
    def _on_transcription(self, result):
        """Called when speech is transcribed."""
        text = result.text.strip()
        
        if not text:
            return
            
        # Log all transcriptions (interim and final)
        if result.is_final:
            speaker = f"[Speaker {result.speaker_id}]" if result.speaker_id else ""
            self._log(f"🎤 Entendu: \"{text}\" {speaker}", "INFO")
            # Process in async context
            asyncio.create_task(self.handle_speech(text, result.speaker_id))
        else:
            # Interim result - show in debug
            self._log(f"🎤 (interim): {text}", "DEBUG")
            
    async def tick(self):
        """
        Main loop tick - called periodically by the Kivy app.
        """
        if not self._running or self._emergency_stop:
            return
            
        try:
            # Check conversation timeout
            if self._in_conversation and self._last_speech:
                timeout = self.config.get("behavior", {}).get("conversation_timeout_seconds", 30)
                if (datetime.now() - self._last_speech).total_seconds() > timeout:
                    self._log("Conversation timeout - going idle", "INFO")
                    self._in_conversation = False
                    self._set_emotion("neutral")
                    if self._llm_client:
                        self._llm_client.clear_history()
                        
        except Exception as e:
            self._log(f"Tick error: {e}", "ERROR")
            
    async def handle_speech(self, text: str, speaker_id: Optional[int] = None):
        """
        Handle transcribed speech.
        
        Args:
            text: Transcribed text
            speaker_id: Optional speaker identification
        """
        self._log(f"Heard: {text}", "INFO")
        self._last_speech = datetime.now()
        
        # Check for emergency stop
        robot_name = self.config.get("robot", {}).get("name", "Néon")
        stop_phrase = self.config.get("safety", {}).get("emergency_stop_phrase", "STOP")
        
        if stop_phrase.lower() in text.lower() and robot_name.lower() in text.lower():
            await self.emergency_stop()
            return
            
        # Check if addressed to Rex (wake word or in conversation)
        if not self._in_conversation:
            if robot_name.lower() not in text.lower():
                self._log(f"💤 Ignoré (pas en conversation, wake word '{robot_name}' absent)", "DEBUG")
                return  # Not addressed to us
            self._on_wake_word()
            
        # Show thinking emotion
        self._set_emotion("thinking")
        
        # Check for known commands → create mission
        if self._mission_manager:
            command = self._mission_manager.detect_command(text)
            if command:
                self._log(f"🎯 Commande détectée: {command}", "INFO")
                mission = self._mission_manager.create_mission_from_template(
                    template_name=command,
                    reason=f"L'utilisateur a dit: '{text}'",
                    target="speaker"
                )
                if mission:
                    self._mission_manager.add_mission(mission)
                    # Still get LLM response for speech
            
        # Get response from LLM
        self._log("🤖 Calling LLM...", "INFO")
        response = await self._get_llm_response(text, speaker_id)
        self._log(f"🤖 LLM response received: {response is not None}", "INFO")
        
        if response:
            # Check if LLM wants to create a mission (mission must exist AND not be None)
            mission_data = response.get("mission")
            if mission_data and self._mission_manager:
                self._log(f"🎯 LLM wants to create mission: {mission_data}", "INFO")
                try:
                    mission = self._mission_manager.create_mission_from_llm(
                        mission_data,
                        reason=f"LLM response to: '{text}'"
                    )
                    if mission:
                        self._mission_manager.add_mission(mission)
                except Exception as e:
                    self._log(f"⚠️ Mission creation failed: {e}", "WARNING")
            else:
                # Execute simple actions (backward compatibility)
                actions = response.get("actions", [])
                if actions:
                    self._log(f"🎯 Executing {len(actions)} actions: {actions}", "INFO")
                for action in actions:
                    try:
                        # Handle both formats: "spin" or {"type": "spin", ...}
                        if isinstance(action, str):
                            action_type = action
                            action_params = {}
                        else:
                            action_type = action.get("type", "")
                            action_params = action
                        await self._execute_action(action_type, action_params)
                    except Exception as e:
                        self._log(f"⚠️ Action error: {e}", "WARNING")
                
            # Speak the response
            speech_text = response.get("speech", "")
            self._log(f"🗣️ Speech to say: '{speech_text[:50] if speech_text else '(none)'}...'", "INFO")
            if speech_text:
                await self._speak(speech_text)
            else:
                self._log("⚠️ No speech text in response", "WARNING")
                self._set_emotion("neutral")
                
            # Check if conversation should end
            if response.get("end_conversation", False):
                self._in_conversation = False
                self._set_emotion("neutral")
                if self._llm_client:
                    self._llm_client.clear_history()
                    
    async def _get_llm_response(self, user_text: str, speaker_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get response from LLM.
        """
        if not self._llm_client:
            return {
                "speech": "Mon cerveau n'est pas encore connecté, désolé!",
                "actions": [],
                "end_conversation": False
            }
            
        try:
            # Build context
            context = {}
            if not self._body_connected:
                context["note"] = "Mon corps de robot n'est pas connecté, je ne peux pas bouger"
                
            # Get speaker name if known
            speaker_name = None
            # TODO: Look up speaker in people database
            
            # Call LLM
            response = await self._llm_client.get_response(
                user_text,
                speaker_name=speaker_name,
                additional_context=context
            )
            
            return response
            
        except Exception as e:
            self._log(f"LLM error: {e}", "ERROR")
            return {
                "speech": "Oups, j'ai eu un bug. Tu peux répéter?",
                "actions": [],
                "end_conversation": False
            }
            
    async def _execute_action(self, action_type: str, parameters: Dict[str, Any] = None) -> bool:
        """
        Execute a movement or behavior action.
        
        Args:
            action_type: Type of action (e.g., "walk_to_person", "sit")
            parameters: Action parameters
            
        Returns:
            True if action succeeded, False otherwise
        """
        if parameters is None:
            parameters = {}
            
        if not self._body_connected:
            self._log(f"🤖 Action '{action_type}' - corps non connecté (ignoré)", "DEBUG")
            # No delay - just skip the action
            return True
            
        self._log(f"🤖 Executing: {action_type} {parameters}", "ROBOT")
        
        # TODO: Send to robot controller when connected
        # For now, simulate execution
        try:
            if self._robot_controller:
                # await self._robot_controller.execute(action_type, parameters)
                pass
            await asyncio.sleep(1.0)  # Simulate action duration
            return True
        except Exception as e:
            self._log(f"Action failed: {e}", "ERROR")
            return False
        
    async def emergency_stop(self):
        """Emergency stop - lie down and stop all movement."""
        self._log("🚨 EMERGENCY STOP!", "WARNING")
        self._emergency_stop = True
        self._set_emotion("surprised")
        
        await self._speak("D'accord, je m'arrête!")
        
        # TODO: Send lie down command to robot
        
        self._running = False
        
    async def say_hello(self):
        """Make Rex say hello on startup."""
        robot_name = self.config.get("robot", {}).get("name", "Néo")
        
        # Always speak in FIRST person
        greetings = [
            "Salut! Je suis prêt à discuter!",
            "Hey! Je me suis bien réveillé!",
            "Woof! Je suis là, qu'est-ce qu'on fait?",
            "Me voilà! Alors, quoi de neuf?",
        ]
        
        import random
        greeting = random.choice(greetings)
        
        self._set_emotion("happy")
        await self._speak(greeting)
        self._set_emotion("neutral")
        
    async def connect_body(self) -> bool:
        """Attempt to connect to the robot body."""
        if self._robot_controller is None:
            from src.action.robot_controller import RobotController
            self._robot_controller = RobotController(self.config)
            
        try:
            connected = await self._robot_controller.connect()
            self._body_connected = connected
            if connected:
                self._log("Robot body connected!", "SUCCESS")
            else:
                self._log("Could not connect to robot body", "WARNING")
            return connected
        except Exception as e:
            self._log(f"Body connection error: {e}", "WARNING")
            self._body_connected = False
            return False
            
    async def shutdown(self):
        """Graceful shutdown."""
        self._log("Shutting down...", "WARNING")
        self._running = False
        self._set_emotion("sleeping")
        
        await self._speak("Bonne nuit!")
        
        # Stop audio
        if self._audio_processor:
            await self._audio_processor.stop()
            
        # Disconnect robot
        if self._robot_controller and self._body_connected:
            await self._robot_controller.disconnect()
            
        self._log("Shutdown complete", "INFO")
