"""
Audio Processor for Rex-Brain.
Uses websocket-client for Deepgram STT (Android compatible).
"""

import asyncio
import json
import ssl
import threading
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from src.utils.config import get_api_key
from src.utils.logger import log


@dataclass
class TranscriptionResult:
    """Result from speech transcription."""
    text: str
    is_final: bool
    confidence: float
    speaker_id: Optional[int] = None
    start_time: float = 0.0
    end_time: float = 0.0


@dataclass
class SpeechSegment:
    """A segment of speech from one speaker."""
    text: str
    speaker_id: int
    timestamp: datetime
    duration: float


class AudioProcessor:
    """
    Audio processor using Deepgram WebSocket API.
    Uses websocket-client library for better header support on Android.
    """
    
    WS_URL = "wss://api.deepgram.com/v1/listen"
    
    def __init__(
        self,
        config: Dict[str, Any],
        on_transcription: Optional[Callable[[TranscriptionResult], None]] = None,
        on_wake_word: Optional[Callable[[], None]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        self.config = config
        self._on_transcription = on_transcription
        self._on_wake_word = on_wake_word
        self._log_callback = log_callback
        
        # Audio config
        audio_config = config.get("perception", {}).get("audio", {})
        self.sample_rate = audio_config.get("sample_rate", 16000)
        self.chunk_duration_ms = audio_config.get("chunk_duration_ms", 100)
        
        # Transcription config
        trans_config = config.get("perception", {}).get("transcription", {})
        self.language = trans_config.get("language", "fr")
        self.enable_diarization = trans_config.get("enable_diarization", True)
        
        # Wake word = robot name (dynamic)
        robot_config = config.get("robot", {})
        self.wake_word = robot_config.get("name", "Néon").lower()
        
        # Get API key
        self.api_key = get_api_key("deepgram")
        if not self.api_key:
            raise ValueError("Deepgram API key not configured")
        
        self._log(f"📍 API key loaded (len={len(self.api_key)})", "INFO")
        
        # State
        self._running = False
        self._muted = False  # Mute mic while robot is speaking
        self._wake_word_triggered = False  # Avoid multiple wake word triggers
        self._ws = None
        self._ws_thread = None
        self._is_listening = False
        self._speech_buffer: List[SpeechSegment] = []
        self._loop = None
        self._audio_chunks_sent = 0
        self._socket_error_logged = False  # Avoid spamming socket errors
        self._reconnecting = False  # Flag to prevent multiple reconnection attempts
        
    def _log(self, message: str, level: str = "INFO"):
        """Log a message - both to console and to UI callback if available."""
        log(message, level)
        if self._log_callback:
            try:
                self._log_callback(message, level)
            except:
                pass  # Don't crash on logging errors
        
    @property
    def is_listening(self) -> bool:
        return self._is_listening
        
    async def start(self):
        """Start audio capture and transcription."""
        self._log("📍 AudioProcessor.start() called", "INFO")
        
        try:
            self._log("📍 Importing websocket...", "INFO")
            import websocket
            self._log("📍 Importing certifi...", "INFO")
            import certifi
            self._log("📍 Imports OK", "SUCCESS")
            
            self._loop = asyncio.get_event_loop()
            self._log("📍 Got event loop", "INFO")
            
            # Build URL with parameters
            params = [
                f"language={self.language}",
                "model=nova-2",
                "smart_format=true",
                "interim_results=true",
                "punctuate=true",
                f"sample_rate={self.sample_rate}",
                "channels=1",
                "encoding=linear16",
                # Wait before considering utterance complete
                "endpointing=500"  # Wait 500ms of silence before finalizing
            ]
            if self.enable_diarization:
                params.append("diarize=true")
                
            ws_url = f"{self.WS_URL}?{'&'.join(params)}"
            self._log(f"📍 WS URL built: {ws_url[:60]}...", "INFO")
            
            self._log("📍 Creating WebSocket object...", "INFO")
            self._ws = websocket.WebSocket(sslopt={
                "cert_reqs": ssl.CERT_REQUIRED,
                "ca_certs": certifi.where()
            })
            self._log("📍 WebSocket object created", "SUCCESS")
            
            self._log("📍 Connecting to Deepgram...", "INFO")
            self._ws.connect(
                ws_url,
                header=[f"Authorization: Token {self.api_key}"]
            )
            self._log("📍 WebSocket connected!", "SUCCESS")
            
            self._running = True
            self._is_listening = True
            
            self._log("📍 Starting receive thread...", "INFO")
            self._ws_thread = threading.Thread(target=self._receive_loop_sync, daemon=True)
            self._ws_thread.start()
            self._log("📍 Receive thread started", "SUCCESS")
            
            self._log("📍 Starting audio capture task...", "INFO")
            asyncio.create_task(self._capture_audio_loop())
            self._log("📍 Audio capture task created", "SUCCESS")
            
            self._log("✅ Audio processor fully started!", "SUCCESS")
            
        except Exception as e:
            self._log(f"❌ AudioProcessor.start() FAILED: {e}", "ERROR")
            import traceback
            self._log(f"❌ Traceback: {traceback.format_exc()}", "ERROR")
            self._is_listening = False
            raise
            
    async def stop(self):
        """Stop audio capture and transcription."""
        self._log("📍 AudioProcessor.stop() called", "INFO")
        self._running = False
        self._is_listening = False
        
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
            self._ws = None
            
        self._log("Audio processor stopped", "INFO")
        
    def _receive_loop_sync(self):
        """Synchronous receive loop running in separate thread."""
        self._log("🎧 RECEIVE THREAD: Started!", "INFO")
        msg_count = 0
        try:
            while self._running and self._ws:
                try:
                    if msg_count < 3:
                        self._log("🎧 RECEIVE: Waiting for message...", "INFO")
                    message = self._ws.recv()
                    msg_count += 1
                    self._log(f"🎧 RECEIVE: Got msg #{msg_count} (len={len(message) if message else 0})", "INFO")
                    
                    if message:
                        self._handle_message_sync(message)
                except Exception as e:
                    if self._running:
                        self._log(f"🎧 RECEIVE ERROR: {e}", "ERROR")
                    break
        except Exception as e:
            self._log(f"🎧 RECEIVE LOOP CRASH: {e}", "ERROR")
        finally:
            self._log(f"🎧 RECEIVE THREAD ENDED: {msg_count} messages received", "WARNING")
            self._is_listening = False
            
    def _handle_message_sync(self, message: str):
        """Handle a message from Deepgram (sync, called from thread)."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            self._log(f"🎧 MSG TYPE: {msg_type}", "INFO")
            
            if msg_type == "Results":
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])
                
                if alternatives:
                    transcript = alternatives[0]
                    text = transcript.get("transcript", "")
                    is_final = data.get("is_final", False)
                    
                    self._log(f"🎧 TRANSCRIPT: '{text}' (final={is_final})", "INFO")
                    
                    if text:
                        confidence = transcript.get("confidence", 1.0)
                        
                        speaker_id = None
                        words = transcript.get("words", [])
                        if words and "speaker" in words[0]:
                            speaker_id = words[0]["speaker"]
                        
                        result = TranscriptionResult(
                            text=text,
                            is_final=is_final,
                            confidence=confidence,
                            speaker_id=speaker_id
                        )
                        
                        # Wake word: trigger once per utterance (on first detection)
                        if self.wake_word in text.lower() and not self._wake_word_triggered:
                            self._log(f"🎉 WAKE WORD DETECTED: {text}", "SUCCESS")
                            self._wake_word_triggered = True
                            if self._on_wake_word and self._loop:
                                self._loop.call_soon_threadsafe(self._on_wake_word)
                        
                        # Only send FINAL transcriptions to brain (not interim)
                        if is_final and self._on_transcription and self._loop:
                            self._log(f"🎧 Sending final transcription to brain...", "INFO")
                            self._loop.call_soon_threadsafe(
                                self._on_transcription, result
                            )
                            # Reset wake word flag after final result
                            self._wake_word_triggered = False
                else:
                    self._log("🎧 Results but no alternatives", "WARNING")
            elif msg_type == "Metadata":
                self._log(f"🎧 Got Metadata from Deepgram", "INFO")
            elif msg_type == "SpeechStarted":
                self._log(f"🎧 Speech started detected!", "INFO")
            elif msg_type == "UtteranceEnd":
                self._log(f"🎧 Utterance end detected", "INFO")
            else:
                self._log(f"🎧 Unknown msg type: {msg_type}", "WARNING")
                            
        except json.JSONDecodeError as e:
            self._log(f"🎧 JSON ERROR: {e}", "WARNING")
        except Exception as e:
            self._log(f"🎧 HANDLE MSG ERROR: {e}", "ERROR")
    
    def mute(self):
        """Mute the microphone (stop sending audio to Deepgram)."""
        self._muted = True
        self._log("🔇 Microphone muted", "INFO")
        
    def unmute(self):
        """Unmute the microphone."""
        self._muted = False
        self._log("🔊 Microphone unmuted", "INFO")
        
    def _trigger_reconnect(self):
        """Trigger WebSocket reconnection in background."""
        if self._reconnecting:
            return  # Already reconnecting
            
        self._reconnecting = True
        
        def reconnect():
            try:
                import time
                time.sleep(1)  # Wait a bit before reconnecting
                
                self._log("🔄 Attempting WebSocket reconnection...", "WARNING")
                
                # Close old socket
                if self._ws:
                    try:
                        self._ws.close()
                    except:
                        pass
                
                # Reimport and create new socket
                import websocket
                import certifi
                import ssl
                
                # Build URL with parameters
                params = [
                    f"language={self.language}",
                    "model=nova-2",
                    "smart_format=true",
                    "interim_results=true",
                    "punctuate=true",
                    f"sample_rate={self.sample_rate}",
                    "channels=1",
                    "encoding=linear16",
                    "endpointing=500"
                ]
                if self.enable_diarization:
                    params.append("diarize=true")
                    
                ws_url = f"{self.WS_URL}?{'&'.join(params)}"
                
                self._ws = websocket.WebSocket(sslopt={
                    "cert_reqs": ssl.CERT_REQUIRED,
                    "ca_certs": certifi.where()
                })
                
                self._ws.connect(
                    ws_url,
                    header=[f"Authorization: Token {self.api_key}"]
                )
                
                self._log("🔄 WebSocket reconnected!", "SUCCESS")
                self._socket_error_logged = False
                self._audio_chunks_sent = 0
                
                # Restart receive thread
                self._ws_thread = threading.Thread(target=self._receive_loop_sync, daemon=True)
                self._ws_thread.start()
                
            except Exception as e:
                self._log(f"🔄 Reconnection failed: {e}", "ERROR")
            finally:
                self._reconnecting = False
        
        # Run in background thread
        threading.Thread(target=reconnect, daemon=True).start()
        
    def _send_audio(self, audio_bytes: bytes):
        """Send audio data to Deepgram (thread-safe)."""
        # Don't send audio when muted (robot is speaking)
        if self._muted:
            return
            
        if self._ws and self._running:
            try:
                self._ws.send_binary(audio_bytes)
                self._audio_chunks_sent += 1
                self._socket_error_logged = False  # Reset error flag on success
                
                if self._audio_chunks_sent == 1:
                    self._log("🎤 AUDIO: First chunk sent!", "SUCCESS")
                elif self._audio_chunks_sent == 10:
                    self._log("🎤 AUDIO: 10 chunks sent", "INFO")
                elif self._audio_chunks_sent == 50:
                    self._log("🎤 AUDIO: 50 chunks (streaming OK)", "SUCCESS")
                elif self._audio_chunks_sent % 200 == 0:
                    self._log(f"🎤 AUDIO: {self._audio_chunks_sent} chunks", "INFO")
            except Exception as e:
                # Only log once to avoid spam
                if not self._socket_error_logged:
                    self._log(f"🎤 SEND ERROR: {e}", "ERROR")
                    self._log("🔄 WebSocket closed, attempting reconnection...", "WARNING")
                    self._socket_error_logged = True
                    # Trigger reconnection in background
                    self._trigger_reconnect()
            
    async def _capture_audio_loop(self):
        """Main loop to capture audio from microphone."""
        self._log("🎤 CAPTURE: Starting audio capture loop...", "INFO")
        
        try:
            self._log("🎤 CAPTURE: Trying Android AudioRecord...", "INFO")
            await self._capture_audio_android()
        except Exception as e:
            self._log(f"🎤 CAPTURE: Android failed: {e}", "WARNING")
            self._log("🎤 CAPTURE: Trying desktop fallback...", "INFO")
            await self._capture_audio_desktop()
            
    async def _capture_audio_android(self):
        """Capture audio on Android using AudioRecord."""
        self._log("🎤 ANDROID: Importing jnius...", "INFO")
        from jnius import autoclass
        self._log("🎤 ANDROID: jnius imported OK", "SUCCESS")
        
        self._log("🎤 ANDROID: Getting AudioRecord class...", "INFO")
        AudioRecord = autoclass('android.media.AudioRecord')
        AudioFormat = autoclass('android.media.AudioFormat')
        # AudioSource is a nested class, access it directly
        AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
        self._log("🎤 ANDROID: Classes loaded OK", "SUCCESS")
        
        channel_config = AudioFormat.CHANNEL_IN_MONO
        audio_format = AudioFormat.ENCODING_PCM_16BIT
        
        self._log(f"🎤 ANDROID: Getting min buffer size (rate={self.sample_rate})...", "INFO")
        buffer_size = AudioRecord.getMinBufferSize(
            self.sample_rate,
            channel_config,
            audio_format
        )
        self._log(f"🎤 ANDROID: Buffer size = {buffer_size}", "INFO")
        
        self._log("🎤 ANDROID: Creating AudioRecord...", "INFO")
        # Use AudioSource.MIC (value is 1)
        recorder = AudioRecord(
            AudioSource.MIC,
            self.sample_rate,
            channel_config,
            audio_format,
            buffer_size
        )
        self._log("🎤 ANDROID: AudioRecord created OK", "SUCCESS")
        
        self._log("🎤 ANDROID: Starting recording...", "INFO")
        recorder.startRecording()
        self._log("🎤 ANDROID: Recording started!", "SUCCESS")
        
        try:
            read_count = 0
            while self._running:
                buffer = bytearray(buffer_size)
                bytes_read = recorder.read(buffer, 0, buffer_size)
                read_count += 1
                
                if read_count == 1:
                    self._log(f"🎤 ANDROID: First read ({bytes_read} bytes)", "INFO")
                elif read_count == 10:
                    self._log(f"🎤 ANDROID: 10 reads done", "INFO")
                
                self._send_audio(bytes(buffer))
                await asyncio.sleep(0.01)
                
        finally:
            self._log("🎤 ANDROID: Stopping recorder...", "INFO")
            recorder.stop()
            recorder.release()
            self._log("🎤 ANDROID: Recorder stopped", "INFO")
            
    async def _capture_audio_desktop(self):
        """Capture audio on desktop for development/testing."""
        self._log("🎤 DESKTOP: Trying sounddevice...", "INFO")
        try:
            import sounddevice as sd
            import numpy as np
            self._log("🎤 DESKTOP: sounddevice imported OK", "SUCCESS")
            
            chunk_size = int(self.sample_rate * self.chunk_duration_ms / 1000)
            
            def audio_callback(indata, frames, time, status):
                if status:
                    self._log(f"🎤 DESKTOP status: {status}", "WARNING")
                if self._running:
                    audio_bytes = (indata * 32767).astype(np.int16).tobytes()
                    self._send_audio(audio_bytes)
                    
            self._log("🎤 DESKTOP: Opening input stream...", "INFO")
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                blocksize=chunk_size,
                callback=audio_callback
            ):
                self._log("🎤 DESKTOP: Stream opened, recording...", "SUCCESS")
                while self._running:
                    await asyncio.sleep(0.1)
                    
        except ImportError:
            self._log("🎤 DESKTOP: sounddevice not available!", "WARNING")
            self._log("🎤 NO AUDIO CAPTURE AVAILABLE!", "ERROR")
            while self._running:
                await asyncio.sleep(1)
                
    def get_recent_speech(self, seconds: float = 30.0) -> List[SpeechSegment]:
        """Get recent speech segments."""
        now = datetime.now()
        cutoff = now.timestamp() - seconds
        
        return [
            seg for seg in self._speech_buffer
            if seg.timestamp.timestamp() > cutoff
        ]
