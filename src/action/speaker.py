"""
Speaker module for Rex-Brain.
Uses direct HTTP calls to OpenAI TTS API (no SDK needed for Android compatibility).
"""

import asyncio
import tempfile
from typing import Any, Dict, Optional
from pathlib import Path

import httpx

from src.utils.config import get_api_key
from src.utils.logger import log


class Speaker:
    """
    Text-to-speech handler using direct HTTP calls to OpenAI TTS API.
    Android-compatible (no openai SDK needed).
    """
    
    API_URL = "https://api.openai.com/v1/audio/speech"
    
    def __init__(self, config: Dict[str, Any], log_callback=None):
        """
        Initialize speaker.
        
        Args:
            config: Configuration dictionary
            log_callback: Optional callback for logging to UI
        """
        self.config = config
        self.tts_config = config.get("action", {}).get("tts", {})
        self._log_callback = log_callback
        
        # Get API key
        self.api_key = get_api_key("openai")
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        # TTS settings
        self.model = self.tts_config.get("model", "tts-1")
        self.voice = self.tts_config.get("voice", "fable")
        self.speed = self.tts_config.get("speed", 0.9)
        
        # State
        self._is_speaking = False
        self._current_task: Optional[asyncio.Task] = None
        # Use synchronous client to avoid event loop issues on Android
        self._client: Optional[httpx.Client] = None
        
    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        log(message, level)
        if self._log_callback:
            self._log_callback(message, level)
        
    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client (synchronous for Android compatibility)."""
        if self._client is None or self._client.is_closed:
            # Try with certifi, fallback to unverified for Android
            try:
                import certifi
                self._client = httpx.Client(timeout=30.0, verify=certifi.where())
            except Exception:
                # Fallback for Android
                self._client = httpx.Client(timeout=30.0, verify=False)
        return self._client
        
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
        
    async def speak(self, text: str, interruptible: bool = True) -> bool:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to speak
            interruptible: Whether this speech can be interrupted
            
        Returns:
            True if speech completed, False if interrupted
        """
        if not text or not text.strip():
            self._log("🔊 TTS: Empty text, skipping", "WARNING")
            return True
            
        self._log(f"🔊 TTS: Generating speech for: {text}", "INFO")
        
        # Interrupt current speech if any
        if self._is_speaking and self._current_task:
            self._log("🔊 TTS: Interrupting current speech", "INFO")
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
                
        self._is_speaking = True
        
        try:
            # Use synchronous client to avoid event loop issues on Android
            client = self._get_client()
            
            self._log(f"🔊 TTS: Calling OpenAI API (voice={self.voice}, speed={self.speed})", "INFO")
            
            # Generate speech using OpenAI TTS API (synchronous call)
            response = client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "voice": self.voice,
                    "input": text,
                    "speed": self.speed,
                    "response_format": "mp3"
                }
            )
            
            if response.status_code != 200:
                self._log(f"🔊 TTS API error: {response.status_code} - {response.text[:100]}", "ERROR")
                self._is_speaking = False
                return False
            
            # Get audio data
            audio_data = response.content
            self._log(f"🔊 TTS: Got {len(audio_data)} bytes from OpenAI", "SUCCESS")
            
            # Play audio
            await self._play_audio(audio_data)
            
            self._is_speaking = False
            return True
            
        except asyncio.CancelledError:
            self._log("🔊 TTS: Speech interrupted", "WARNING")
            self._is_speaking = False
            return False
            
        except Exception as e:
            import traceback
            self._log(f"🔊 TTS error: {e}", "ERROR")
            self._log(f"🔊 TTS traceback: {traceback.format_exc()[:200]}", "ERROR")
            self._is_speaking = False
            return False
            
    async def _play_audio(self, audio_data: bytes):
        """
        Play audio data through device speakers.
        
        Args:
            audio_data: MP3 audio data
        """
        try:
            await self._play_audio_android(audio_data)
        except Exception as e:
            log(f"Android playback failed: {e}, trying desktop", "WARNING")
            await self._play_audio_desktop(audio_data)
            
    async def _play_audio_android(self, audio_data: bytes):
        """Play audio on Android using MediaPlayer."""
        self._log(f"🔊 TTS: Playing audio ({len(audio_data)} bytes)", "INFO")
        from jnius import autoclass
        
        # Get Android cache directory
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity
            cache_dir = context.getCacheDir().getAbsolutePath()
            temp_file = Path(cache_dir) / "rex_speech.mp3"
        except Exception as e:
            self._log(f"🔊 TTS: Using fallback temp dir: {e}", "WARNING")
            temp_file = Path(tempfile.gettempdir()) / "rex_speech.mp3"
        
        # Write audio to temp file
        with open(temp_file, 'wb') as f:
            f.write(audio_data)
            
        # Maximize system volume for STREAM_MUSIC
        try:
            AudioManager = autoclass('android.media.AudioManager')
            audio_manager = context.getSystemService("audio")
            max_volume = audio_manager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            audio_manager.setStreamVolume(AudioManager.STREAM_MUSIC, max_volume, 0)
            self._log(f"🔊 TTS: Volume set to max ({max_volume})", "INFO")
        except Exception as e:
            self._log(f"🔊 TTS: Could not set volume: {e}", "WARNING")
        
        # Play with MediaPlayer
        MediaPlayer = autoclass('android.media.MediaPlayer')
        AudioManager = autoclass('android.media.AudioManager')
        
        player = MediaPlayer()
        player.setDataSource(str(temp_file))
        player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        player.setVolume(1.0, 1.0)
        player.prepare()
        player.start()
        
        self._log("🔊 TTS: Playing...", "INFO")
        
        # Wait for playback to finish (check more frequently for faster response)
        while player.isPlaying():
            await asyncio.sleep(0.05)
            
        self._log("🔊 TTS: Playback finished!", "SUCCESS")
        player.release()
        
        # Clean up temp file
        try:
            temp_file.unlink()
        except Exception:
            pass
            
    async def _play_audio_desktop(self, audio_data: bytes):
        """Play audio on desktop for development/testing."""
        try:
            import io
            import pygame
            pygame.mixer.init()
            
            audio_stream = io.BytesIO(audio_data)
            pygame.mixer.music.load(audio_stream)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
                
        except ImportError:
            log("No audio backend available for playback", "WARNING")
            # Simulate playback delay based on audio size
            await asyncio.sleep(len(audio_data) / 16000)
            
    async def stop(self):
        """Stop current speech."""
        if self._current_task:
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
                
        self._is_speaking = False
        log("Speech stopped", "INFO")
        
    async def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
        
    def estimate_duration(self, text: str) -> float:
        """
        Estimate speech duration for a given text.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated duration in seconds
        """
        words = len(text.split())
        base_duration = words / 150 * 60
        return base_duration / self.speed
