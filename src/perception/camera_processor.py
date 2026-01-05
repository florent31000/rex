"""
Camera Processor for Rex-Brain.
Handles camera capture, face detection, and scene analysis.
"""

import asyncio
import base64
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from PIL import Image

from src.utils.config import get_api_key
from src.utils.logger import log


@dataclass
class DetectedFace:
    """A detected face in the camera frame."""
    # Bounding box (normalized 0-1)
    x: float
    y: float
    width: float
    height: float
    # Center position for tracking
    center_x: float
    center_y: float
    # Confidence score
    confidence: float
    # Face embedding for recognition (optional)
    embedding: Optional[np.ndarray] = None
    # Recognized person name (if known)
    person_name: Optional[str] = None
    person_id: Optional[str] = None


@dataclass
class SceneAnalysis:
    """Analysis of the current scene."""
    description: str
    people_count: int
    people_descriptions: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    activities: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class CameraProcessor:
    """
    Camera processor for face detection and scene analysis.
    
    Uses:
    - MediaPipe for local face detection (lightweight)
    - Claude Vision for scene analysis (cloud)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        on_faces_detected: Optional[Callable[[List[DetectedFace]], None]] = None,
        on_scene_analyzed: Optional[Callable[[SceneAnalysis], None]] = None
    ):
        """
        Initialize camera processor.
        
        Args:
            config: Configuration dictionary
            on_faces_detected: Callback when faces are detected
            on_scene_analyzed: Callback when scene is analyzed
        """
        self.config = config
        self._on_faces_detected = on_faces_detected
        self._on_scene_analyzed = on_scene_analyzed
        
        # Camera config
        cam_config = config.get("perception", {}).get("camera", {})
        self.use_front_camera = cam_config.get("use_front_camera", True)
        self.resolution = tuple(cam_config.get("resolution", [640, 480]))
        self.fps = cam_config.get("fps", 10)
        
        # Face detection config
        face_config = config.get("perception", {}).get("face_detection", {})
        self.face_detection_enabled = face_config.get("enabled", True)
        self.min_detection_confidence = face_config.get("min_detection_confidence", 0.7)
        
        # Scene analysis config
        scene_config = config.get("perception", {}).get("scene_analysis", {})
        self.scene_analysis_enabled = scene_config.get("enabled", True)
        self.scene_analysis_interval = scene_config.get("interval_seconds", 2.5)
        
        # Vision API (Claude)
        vision_config = config.get("cognition", {}).get("vision", {})
        self.vision_model = vision_config.get("model", "claude-3-5-sonnet-20241022")
        
        # State
        self._running = False
        self._current_frame: Optional[np.ndarray] = None
        self._detected_faces: List[DetectedFace] = []
        self._last_scene_analysis: Optional[datetime] = None
        
        # MediaPipe face detector (initialized lazily)
        self._face_detector = None
        
        # Claude client for vision
        self._anthropic_client = None
        
    @property
    def detected_faces(self) -> List[DetectedFace]:
        return self._detected_faces
        
    async def start(self):
        """Start camera capture and processing."""
        log("Starting camera processor...", "INFO")
        
        # Initialize face detector
        if self.face_detection_enabled:
            await self._init_face_detector()
            
        # Initialize Claude client for vision
        if self.scene_analysis_enabled:
            await self._init_vision_client()
            
        self._running = True
        
        # Start capture loop
        asyncio.create_task(self._capture_loop())
        
        log("Camera processor started", "SUCCESS")
        
    async def stop(self):
        """Stop camera capture."""
        self._running = False
        log("Camera processor stopped", "INFO")
        
    async def _init_face_detector(self):
        """Initialize MediaPipe face detector."""
        try:
            import mediapipe as mp
            
            self._mp_face_detection = mp.solutions.face_detection
            self._face_detector = self._mp_face_detection.FaceDetection(
                model_selection=0,  # 0 for short-range (< 2m), 1 for full-range
                min_detection_confidence=self.min_detection_confidence
            )
            
            log("MediaPipe face detector initialized", "SUCCESS")
            
        except ImportError:
            log("MediaPipe not available, face detection disabled", "WARNING")
            self.face_detection_enabled = False
            
    async def _init_vision_client(self):
        """Initialize Claude vision client."""
        try:
            from anthropic import AsyncAnthropic
            
            api_key = get_api_key("anthropic")
            if api_key:
                self._anthropic_client = AsyncAnthropic(api_key=api_key)
                log("Claude vision client initialized", "SUCCESS")
            else:
                log("Anthropic API key not configured, scene analysis disabled", "WARNING")
                self.scene_analysis_enabled = False
                
        except ImportError:
            log("Anthropic library not available", "WARNING")
            self.scene_analysis_enabled = False
            
    async def _capture_loop(self):
        """Main loop to capture and process camera frames."""
        log("Starting camera capture...", "INFO")
        
        try:
            # Try Android-specific capture
            await self._capture_android()
        except Exception as e:
            log(f"Android camera failed: {e}", "WARNING")
            # Fallback for desktop
            await self._capture_desktop()
            
    async def _capture_android(self):
        """Capture camera on Android."""
        from jnius import autoclass
        
        # Get camera using Plyer
        from plyer import camera
        
        log("Android camera capture started", "SUCCESS")
        
        frame_interval = 1.0 / self.fps
        
        while self._running:
            try:
                # Capture frame using plyer
                # Note: This is a simplified approach
                # In production, use Camera2 API directly via pyjnius
                
                await asyncio.sleep(frame_interval)
                
                # Process current frame
                if self._current_frame is not None:
                    await self._process_frame(self._current_frame)
                    
            except Exception as e:
                log(f"Frame capture error: {e}", "ERROR")
                await asyncio.sleep(1)
                
    async def _capture_desktop(self):
        """Capture camera on desktop for development."""
        try:
            import cv2
            
            # Open camera
            cap = cv2.VideoCapture(0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            frame_interval = 1.0 / self.fps
            
            while self._running:
                ret, frame = cap.read()
                
                if ret:
                    # Convert BGR to RGB
                    self._current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Process frame
                    await self._process_frame(self._current_frame)
                    
                await asyncio.sleep(frame_interval)
                
            cap.release()
            
        except ImportError:
            log("OpenCV not available, camera disabled", "WARNING")
            while self._running:
                await asyncio.sleep(1)
                
    async def _process_frame(self, frame: np.ndarray):
        """Process a camera frame."""
        # Face detection
        if self.face_detection_enabled and self._face_detector:
            await self._detect_faces(frame)
            
        # Scene analysis (at configured interval)
        if self.scene_analysis_enabled:
            now = datetime.now()
            if self._last_scene_analysis is None or \
               (now - self._last_scene_analysis).total_seconds() > self.scene_analysis_interval:
                self._last_scene_analysis = now
                asyncio.create_task(self._analyze_scene(frame))
                
    async def _detect_faces(self, frame: np.ndarray):
        """Detect faces in frame using MediaPipe."""
        try:
            results = self._face_detector.process(frame)
            
            faces = []
            if results.detections:
                h, w = frame.shape[:2]
                
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    
                    face = DetectedFace(
                        x=bbox.xmin,
                        y=bbox.ymin,
                        width=bbox.width,
                        height=bbox.height,
                        center_x=bbox.xmin + bbox.width / 2,
                        center_y=bbox.ymin + bbox.height / 2,
                        confidence=detection.score[0]
                    )
                    faces.append(face)
                    
            self._detected_faces = faces
            
            if faces and self._on_faces_detected:
                self._on_faces_detected(faces)
                
        except Exception as e:
            log(f"Face detection error: {e}", "ERROR")
            
    async def _analyze_scene(self, frame: np.ndarray):
        """Analyze scene using Claude Vision."""
        if not self._anthropic_client:
            return
            
        try:
            # Convert frame to JPEG
            image = Image.fromarray(frame)
            
            # Resize for API (save bandwidth)
            max_size = 512
            image.thumbnail((max_size, max_size))
            
            # Convert to base64
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=80)
            base64_image = base64.b64encode(buffer.getvalue()).decode()
            
            # Call Claude Vision
            response = await self._anthropic_client.messages.create(
                model=self.vision_model,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_image
                            }
                        },
                        {
                            "type": "text",
                            "text": """Analyse cette image en quelques phrases courtes. Réponds en JSON:
{
    "description": "Description courte de la scène",
    "people_count": 0,
    "people_descriptions": ["description de chaque personne visible"],
    "objects": ["objets importants"],
    "activities": ["actions en cours"]
}"""
                        }
                    ]
                }]
            )
            
            # Parse response
            import json
            response_text = response.content[0].text
            
            try:
                data = json.loads(response_text)
                analysis = SceneAnalysis(
                    description=data.get("description", ""),
                    people_count=data.get("people_count", 0),
                    people_descriptions=data.get("people_descriptions", []),
                    objects=data.get("objects", []),
                    activities=data.get("activities", [])
                )
            except json.JSONDecodeError:
                analysis = SceneAnalysis(
                    description=response_text,
                    people_count=len(self._detected_faces)
                )
                
            log(f"Scene: {analysis.description}", "INFO")
            
            if self._on_scene_analyzed:
                self._on_scene_analyzed(analysis)
                
        except Exception as e:
            log(f"Scene analysis error: {e}", "ERROR")
            
    def get_main_face_offset(self) -> Optional[Tuple[float, float]]:
        """
        Get the offset of the main face from center of frame.
        Used for face tracking (looking at speaker).
        
        Returns:
            (x_offset, y_offset) where 0 is center, -1/1 are edges
            None if no faces detected
        """
        if not self._detected_faces:
            return None
            
        # Find largest face (assumed to be main speaker)
        main_face = max(self._detected_faces, key=lambda f: f.width * f.height)
        
        # Calculate offset from center (0.5, 0.5)
        x_offset = (main_face.center_x - 0.5) * 2  # -1 to 1
        y_offset = (main_face.center_y - 0.5) * 2  # -1 to 1
        
        return (x_offset, y_offset)

