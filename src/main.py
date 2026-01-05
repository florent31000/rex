"""
Rex-Brain Main Entry Point
Kivy Android Application for Unitree Go2 Robot Control
"""

import os
import sys

# Set environment before importing Kivy
os.environ['KIVY_LOG_LEVEL'] = 'info'

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.properties import StringProperty, BooleanProperty
from kivy.graphics import Color, Rectangle
from kivy.utils import platform

import asyncio
from datetime import datetime
import random

# Import our modules
from src.utils.config import load_config
from src.utils.logger import setup_logger, log
from src.cognition.brain import RexBrain
from src.ui.eyes_display import EyesDisplay

# Android permissions handling
def request_android_permissions():
    """Request required permissions on Android."""
    if platform != 'android':
        return True
    
    from android.permissions import request_permissions, Permission, check_permission
    
    permissions_needed = [
        Permission.RECORD_AUDIO,
        Permission.CAMERA,
        Permission.INTERNET,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE,
    ]
    
    # Check which permissions we don't have yet
    missing = [p for p in permissions_needed if not check_permission(p)]
    
    if missing:
        request_permissions(missing)
        return False  # Permissions being requested
    return True  # All permissions granted


class LogDisplay(BoxLayout):
    """Selectable log display widget using TextInput."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        
        # TextInput for selectable/copyable logs
        self.text_input = TextInput(
            text="",
            readonly=True,  # Can select but not edit
            multiline=True,
            font_size='11sp',
            background_color=(0, 0, 0, 0.9),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            selection_color=(0.3, 0.5, 0.8, 0.8),
            padding=[10, 10],
            size_hint=(1, 1)
        )
        self.add_widget(self.text_input)
        self.max_lines = 100
        self._lines = []
        
    def add_log(self, message: str, level: str = "INFO"):
        """Add a log message to the display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Level indicator
        indicators = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅",
            "SPEECH": "🗣️",
            "ROBOT": "🤖",
        }
        indicator = indicators.get(level, "•")
        
        line = f"[{timestamp}] {indicator} {message}"
        self._lines.append(line)
        
        # Keep only last N lines
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]
            
        # Update text
        self.text_input.text = "\n".join(self._lines)
        
        # Scroll to bottom
        self.text_input.cursor = (0, len(self.text_input.text))


class RexBrainApp(App):
    """Main Kivy Application for Rex-Brain."""
    
    status_text = StringProperty("Initializing...")
    body_connected = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.brain = None
        self.config = None
        self.log_display = None
        self.eyes_display = None
        self.status_label = None
        self.connection_label = None
        self._tick_count = 0
        
    def build(self):
        """Build the UI."""
        # Full black background
        Window.clearcolor = (0, 0, 0, 1)
        
        # Main layout
        root = FloatLayout()
        
        # Eyes display (full screen behind everything)
        self.eyes_display = EyesDisplay(
            pos_hint={'x': 0, 'y': 0},
            size_hint=(1, 1)
        )
        root.add_widget(self.eyes_display)
        
        # Overlay for status and logs (semi-transparent)
        overlay = BoxLayout(
            orientation='vertical',
            padding=10,
            spacing=5,
            pos_hint={'x': 0, 'y': 0},
            size_hint=(1, 1)
        )
        
        # Status bar at top
        status_bar = BoxLayout(size_hint_y=0.08, spacing=10)
        
        # Add semi-transparent background to status bar
        with status_bar.canvas.before:
            Color(0, 0, 0, 0.7)
            self._status_bg = Rectangle(pos=status_bar.pos, size=status_bar.size)
        status_bar.bind(pos=self._update_status_bg, size=self._update_status_bg)
        
        self.status_label = Label(
            text=self.status_text,
            size_hint_x=0.7,
            halign='left',
            font_size='14sp',
            color=(1, 1, 1, 1)
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        
        self.connection_label = Label(
            text="🧠 Brain only",
            size_hint_x=0.3,
            font_size='12sp',
            color=(1, 0.8, 0.3, 1)
        )
        
        status_bar.add_widget(self.status_label)
        status_bar.add_widget(self.connection_label)
        overlay.add_widget(status_bar)
        
        # Log display takes rest of screen (semi-transparent, OVER the eyes)
        log_container = BoxLayout(size_hint_y=0.92)
        with log_container.canvas.before:
            Color(0, 0, 0, 0.5)  # 50% transparent so eyes show through
            self._log_bg = Rectangle(pos=log_container.pos, size=log_container.size)
        log_container.bind(pos=self._update_log_bg, size=self._update_log_bg)
        
        self.log_display = LogDisplay()
        log_container.add_widget(self.log_display)
        overlay.add_widget(log_container)
        
        root.add_widget(overlay)
        
        return root
    
    def _update_status_bg(self, instance, value):
        self._status_bg.pos = instance.pos
        self._status_bg.size = instance.size
        
    def _update_log_bg(self, instance, value):
        self._log_bg.pos = instance.pos
        self._log_bg.size = instance.size
    
    def on_start(self):
        """Called when app starts."""
        self.log("🐕 Rex-Brain starting...", "INFO")
        self.log("💡 Tip: Long-press logs to select & copy", "INFO")
        
        # Request Android permissions FIRST
        if platform == 'android':
            self.log("📱 Requesting Android permissions...", "INFO")
            self._permissions_granted = False
            Clock.schedule_once(self._request_permissions, 0.1)
        else:
            self._permissions_granted = True
            self._continue_startup()
    
    def _request_permissions(self, dt):
        """Request permissions on Android."""
        from android.permissions import request_permissions, Permission
        
        def callback(permissions, grants):
            # IMPORTANT: This callback runs on Android thread, not Kivy main thread!
            # Must use Clock.schedule_once to update UI safely
            def on_main_thread(dt):
                self.log(f"📱 Permissions result: {grants}", "INFO")
                if all(grants):
                    self._permissions_granted = True
                    self.log("✅ All permissions granted!", "SUCCESS")
                else:
                    self.log("⚠️ Some permissions denied!", "WARNING")
                    self._permissions_granted = True  # Continue anyway
                self._continue_startup()
            
            Clock.schedule_once(on_main_thread, 0)
        
        request_permissions([
            Permission.RECORD_AUDIO,
            Permission.CAMERA,
            Permission.INTERNET,
        ], callback)
    
    def _continue_startup(self):
        """Continue startup after permissions."""
        # Load configuration
        try:
            self.config = load_config()
            robot_name = self.config.get('robot', {}).get('name', 'Néo')
            self.log(f"Configuration loaded. Robot: {robot_name}", "SUCCESS")
        except Exception as e:
            self.log(f"Config error: {e}", "ERROR")
            self.config = {"robot": {"name": "Néo"}}
            
        # Initialize brain
        Clock.schedule_once(self._init_brain, 0.5)
        
    def _init_brain(self, dt):
        """Initialize the Rex Brain."""
        self.log("Initializing Rex Brain...", "INFO")
        
        try:
            # Create brain instance with all callbacks
            self.brain = RexBrain(
                self.config, 
                log_callback=self._on_log, 
                speech_callback=self._on_speech,
                emotion_callback=self._on_emotion
            )
            
            # Update UI based on brain state
            self.body_connected = self.brain.has_body
            self._update_connection_display()
            
            robot_name = self.config.get('robot', {}).get('name', 'Néo')
            self.status_text = f"{robot_name} is awake!"
            self.status_label.text = self.status_text
            
            self.log("Rex Brain initialized!", "SUCCESS")
            
            # Start the main loop
            Clock.schedule_interval(self._main_loop, 0.5)
            
            # Start eye blink timer
            Clock.schedule_interval(self._random_blink, 4.0)
            
            # Start audio listening
            Clock.schedule_once(self._start_audio, 2.0)
            
            # Say hello
            Clock.schedule_once(self._say_hello, 3.0)
            
        except Exception as e:
            self.log(f"Brain init error: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            
    def _update_connection_display(self):
        """Update the connection status display."""
        if self.connection_label:
            if self.body_connected:
                self.connection_label.text = "🤖 Body connected"
                self.connection_label.color = (0.3, 1, 0.3, 1)
            else:
                self.connection_label.text = "🧠 Brain only"
                self.connection_label.color = (1, 0.8, 0.3, 1)
    
    def _main_loop(self, dt):
        """Main loop - runs periodically."""
        self._tick_count += 1
        
        # Log heartbeat every 10 ticks (5 seconds)
        if self._tick_count % 10 == 0:
            self.log(f"♥ Tick {self._tick_count} - Rex is alive", "DEBUG")
            
        # Run brain tick
        if self.brain:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.brain.tick())
                loop.close()
            except Exception as e:
                if "no running event loop" not in str(e):
                    self.log(f"Tick error: {e}", "DEBUG")
                    
    def _random_blink(self, dt):
        """Make eyes blink randomly."""
        if self.eyes_display and random.random() < 0.3:  # 30% chance to blink
            self.eyes_display.blink()
            
    def _on_log(self, message: str, level: str = "INFO"):
        """Callback for brain logging."""
        Clock.schedule_once(lambda dt: self.log(message, level), 0)
        
    def _on_speech(self, text: str):
        """Callback when Rex speaks (may be called from any thread)."""
        Clock.schedule_once(lambda dt: self.log(f"🗣️ Rex: {text}", "SPEECH"), 0)
        
    def _on_emotion(self, emotion: str):
        """Callback to change eye emotion (may be called from any thread)."""
        def update_emotion(dt):
            if self.eyes_display:
                self.eyes_display.set_emotion(emotion)
        Clock.schedule_once(update_emotion, 0)
            
    def _start_audio(self, dt):
        """Start audio listening."""
        self.log("🎤 Starting audio capture...", "INFO")
        
        # Check permissions on Android
        if platform == 'android':
            from android.permissions import check_permission, Permission
            has_mic = check_permission(Permission.RECORD_AUDIO)
            self.log(f"📱 RECORD_AUDIO permission: {has_mic}", "INFO")
            if not has_mic:
                self.log("❌ Microphone permission not granted!", "ERROR")
                return
        
        if self.brain:
            try:
                # Start audio in a separate thread with its own persistent event loop
                import threading
                def run_audio():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.brain.start_listening())
                        # Keep the loop running for the async tasks
                        loop.run_forever()
                    except Exception as e:
                        # Use Clock.schedule_once for thread-safe UI update
                        Clock.schedule_once(lambda dt, err=e: self.log(f"Audio thread error: {err}", "ERROR"), 0)
                    finally:
                        loop.close()
                
                self._audio_thread = threading.Thread(target=run_audio, daemon=True)
                self._audio_thread.start()
                self.log("🎤 Audio thread started!", "SUCCESS")
                
            except Exception as e:
                self.log(f"Audio start error: {e}", "ERROR")
                import traceback
                self.log(traceback.format_exc()[:200], "ERROR")
                
    def _say_hello(self, dt):
        """Make Rex say hello."""
        if self.brain:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.brain.say_hello())
                loop.close()
            except Exception as e:
                self.log(f"Hello error: {e}", "ERROR")
    
    def log(self, message: str, level: str = "INFO"):
        """Add log message to display (selectable text)."""
        if self.log_display:
            self.log_display.add_log(message, level)
        print(f"[{level}] {message}")
        
    def on_stop(self):
        """Called when app stops."""
        self.log("Shutting down...", "WARNING")
        
        if self.eyes_display:
            self.eyes_display.set_emotion("sleeping")
            
        if self.brain:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.brain.shutdown())
                loop.close()
            except:
                pass


def main():
    """Main entry point."""
    setup_logger()
    RexBrainApp().run()


if __name__ == '__main__':
    main()
