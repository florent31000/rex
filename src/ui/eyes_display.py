"""
Eyes Display for Rex-Brain.
Shows emotional eyes on the phone screen.
"""

from pathlib import Path
from typing import Optional

from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.animation import Animation

from src.utils.logger import log


class EyesDisplay(Widget):
    """
    Widget to display Rex's emotional eyes.
    
    Shows different eye images based on current emotion.
    Background is always black.
    """
    
    # Available emotions (must match image filenames)
    EMOTIONS = [
        "neutral",
        "happy", 
        "excited",
        "curious",
        "sarcastic",
        "annoyed",
        "tired",
        "sad",
        "angry",
        "thinking",
        "sleeping",
        "love",
        "surprised",
        "mischievous"
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Assets path
        self.assets_path = Path(__file__).parent.parent.parent / "assets" / "eyes"
        
        # Current emotion
        self._current_emotion = "neutral"
        
        # Image widget
        self._eye_image: Optional[Image] = None
        
        # Black background
        with self.canvas.before:
            Color(0, 0, 0, 1)  # Pure black
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # Load initial emotion
        self._load_emotion("neutral")
        
    def _update_bg(self, *args):
        """Update background rectangle."""
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        
    def _get_image_path(self, emotion: str) -> Optional[Path]:
        """Get path to emotion image."""
        # Try PNG first, then JPG
        for ext in [".png", ".jpg", ".jpeg"]:
            path = self.assets_path / f"{emotion}{ext}"
            if path.exists():
                return path
        return None
        
    def _load_emotion(self, emotion: str):
        """Load and display an emotion image."""
        image_path = self._get_image_path(emotion)
        
        if image_path is None:
            log(f"Eye image not found for emotion: {emotion}", "WARNING")
            # Fallback to neutral
            if emotion != "neutral":
                image_path = self._get_image_path("neutral")
            if image_path is None:
                return
                
        # Remove old image
        if self._eye_image:
            self.remove_widget(self._eye_image)
            
        # Create new image
        self._eye_image = Image(
            source=str(image_path),
            fit_mode="contain",
            pos=self.pos,
            size=self.size
        )
        
        # Bind size/pos
        self.bind(pos=self._update_image, size=self._update_image)
        
        self.add_widget(self._eye_image)
        self._current_emotion = emotion
        
    def _update_image(self, *args):
        """Update image position and size."""
        if self._eye_image:
            self._eye_image.pos = self.pos
            self._eye_image.size = self.size
            
    def set_emotion(self, emotion: str, transition_duration: float = 0.3):
        """
        Change the displayed emotion.
        
        Args:
            emotion: Emotion name (must be in EMOTIONS list)
            transition_duration: Fade transition duration in seconds
        """
        if emotion not in self.EMOTIONS:
            log(f"Unknown emotion: {emotion}, using neutral", "WARNING")
            emotion = "neutral"
            
        if emotion == self._current_emotion:
            return
            
        log(f"Changing emotion to: {emotion}", "INFO")
        
        # Simple transition: fade out, change, fade in
        if self._eye_image and transition_duration > 0:
            # Fade out
            anim = Animation(opacity=0, duration=transition_duration / 2)
            anim.bind(on_complete=lambda *args: self._on_fade_out_complete(emotion, transition_duration))
            anim.start(self._eye_image)
        else:
            self._load_emotion(emotion)
            
    def _on_fade_out_complete(self, emotion: str, transition_duration: float):
        """Called when fade out is complete."""
        self._load_emotion(emotion)
        
        if self._eye_image:
            self._eye_image.opacity = 0
            # Fade in
            anim = Animation(opacity=1, duration=transition_duration / 2)
            anim.start(self._eye_image)
            
    @property
    def current_emotion(self) -> str:
        """Get current emotion."""
        return self._current_emotion
        
    def blink(self):
        """Make the eyes blink."""
        # Quick close-open animation
        if self._eye_image:
            original_emotion = self._current_emotion
            self.set_emotion("sleeping", transition_duration=0.1)
            Clock.schedule_once(
                lambda dt: self.set_emotion(original_emotion, transition_duration=0.1),
                0.15
            )


