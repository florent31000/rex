"""
Mission Manager for Rex-Brain.
Handles complex multi-step actions with goal tracking.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MissionStatus(Enum):
    """Status of a mission."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Status of a mission step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MissionStep:
    """A single step in a mission."""
    action: str  # e.g., "walk_to_person", "lie_down", "sit", "speak"
    parameters: Dict[str, Any] = field(default_factory=dict)
    done_condition: Optional[str] = None  # e.g., "distance < 0.5", "pose == lying"
    timeout_seconds: float = 30.0
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "parameters": self.parameters,
            "status": self.status.value,
            "error": self.error
        }


@dataclass
class Mission:
    """A mission with a goal and multiple steps."""
    id: str
    goal: str  # High-level description: "Aller au pied de la personne"
    reason: str  # Why: "La personne a dit 'au pied'"
    steps: List[MissionStep] = field(default_factory=list)
    status: MissionStatus = MissionStatus.PENDING
    current_step_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 1  # Higher = more important
    interruptible: bool = True  # Can be interrupted by higher priority mission
    
    @property
    def current_step(self) -> Optional[MissionStep]:
        """Get the current step."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    @property
    def progress(self) -> float:
        """Get mission progress as 0.0-1.0."""
        if not self.steps:
            return 1.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return completed / len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "reason": self.reason,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step.to_dict() if self.current_step else None,
            "steps": [s.to_dict() for s in self.steps]
        }


class MissionManager:
    """
    Manages multi-step missions for Rex.
    
    Handles:
    - Mission queuing and prioritization
    - Step-by-step execution
    - Progress tracking
    - Interruption handling
    """
    
    # Predefined action templates
    ACTION_TEMPLATES = {
        "au_pied": {
            "goal": "Aller au pied de {target}",
            "steps": [
                {"action": "walk_to_person", "parameters": {"target": "{target}"}, "done_condition": "distance < 0.5"},
                {"action": "lie_down", "done_condition": "pose == lying"}
            ]
        },
        "viens_ici": {
            "goal": "Aller vers {target}",
            "steps": [
                {"action": "walk_to_person", "parameters": {"target": "{target}"}, "done_condition": "distance < 1.0"}
            ]
        },
        "assis": {
            "goal": "S'asseoir",
            "steps": [
                {"action": "sit", "done_condition": "pose == sitting"}
            ]
        },
        "couché": {
            "goal": "Se coucher",
            "steps": [
                {"action": "lie_down", "done_condition": "pose == lying"}
            ]
        },
        "debout": {
            "goal": "Se lever",
            "steps": [
                {"action": "stand_up", "done_condition": "pose == standing"}
            ]
        },
        "donne_la_patte": {
            "goal": "Donner la patte",
            "steps": [
                {"action": "sit", "done_condition": "pose == sitting"},
                {"action": "give_paw", "parameters": {"paw": "right"}, "timeout_seconds": 5.0}
            ]
        },
        "fais_le_beau": {
            "goal": "Faire le beau",
            "steps": [
                {"action": "sit", "done_condition": "pose == sitting"},
                {"action": "beg", "timeout_seconds": 5.0}
            ]
        },
        "tourne": {
            "goal": "Faire un tour sur soi-même",
            "steps": [
                {"action": "spin", "parameters": {"direction": "right", "degrees": 360}}
            ]
        },
        "recule": {
            "goal": "Reculer",
            "steps": [
                {"action": "walk_backward", "parameters": {"distance": 1.0}}
            ]
        },
        "salue": {
            "goal": "Saluer",
            "steps": [
                {"action": "wave", "parameters": {"paw": "right"}}
            ]
        }
    }
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        Initialize mission manager.
        
        Args:
            log_callback: Callback for logging
        """
        self._log_callback = log_callback
        self._mission_queue: List[Mission] = []
        self._current_mission: Optional[Mission] = None
        self._mission_counter = 0
        self._robot_state: Dict[str, Any] = {}  # Current robot state for condition checking
        
        # Action executor callback (will be set by brain)
        self._action_executor: Optional[Callable] = None
        
    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if self._log_callback:
            self._log_callback(message, level)
            
    def set_action_executor(self, executor: Callable):
        """Set the callback that executes individual actions."""
        self._action_executor = executor
        
    def update_robot_state(self, state: Dict[str, Any]):
        """Update current robot state for condition checking."""
        self._robot_state.update(state)
        
    @property
    def current_mission(self) -> Optional[Mission]:
        """Get the current mission."""
        return self._current_mission
    
    @property
    def has_active_mission(self) -> bool:
        """Check if there's an active mission."""
        return self._current_mission is not None and self._current_mission.status == MissionStatus.IN_PROGRESS
    
    @property
    def queue_size(self) -> int:
        """Get number of pending missions."""
        return len(self._mission_queue)
    
    def create_mission_from_template(
        self,
        template_name: str,
        reason: str,
        target: str = "speaker",
        priority: int = 1
    ) -> Optional[Mission]:
        """
        Create a mission from a predefined template.
        
        Args:
            template_name: Name of the template (e.g., "au_pied")
            reason: Why this mission was created
            target: Target person (default: "speaker")
            priority: Mission priority
            
        Returns:
            Created mission or None if template not found
        """
        template = self.ACTION_TEMPLATES.get(template_name)
        if not template:
            self._log(f"Unknown template: {template_name}", "WARNING")
            return None
            
        # Generate mission ID
        self._mission_counter += 1
        mission_id = f"mission_{self._mission_counter}"
        
        # Create steps from template
        steps = []
        for step_template in template["steps"]:
            # Replace {target} in parameters
            params = {}
            for key, value in step_template.get("parameters", {}).items():
                if isinstance(value, str) and "{target}" in value:
                    params[key] = value.replace("{target}", target)
                else:
                    params[key] = value
                    
            step = MissionStep(
                action=step_template["action"],
                parameters=params,
                done_condition=step_template.get("done_condition"),
                timeout_seconds=step_template.get("timeout_seconds", 30.0)
            )
            steps.append(step)
            
        # Create mission
        goal = template["goal"].replace("{target}", target)
        mission = Mission(
            id=mission_id,
            goal=goal,
            reason=reason,
            steps=steps,
            priority=priority
        )
        
        self._log(f"📋 Mission créée: {goal} ({len(steps)} étapes)", "INFO")
        return mission
    
    def create_mission_from_llm(self, mission_data: Dict[str, Any], reason: str) -> Mission:
        """
        Create a mission from LLM response.
        
        Args:
            mission_data: Mission data from LLM
            reason: Why this mission was created
            
        Returns:
            Created mission
        """
        self._mission_counter += 1
        mission_id = f"mission_{self._mission_counter}"
        
        steps = []
        for step_data in mission_data.get("steps", []):
            step = MissionStep(
                action=step_data.get("action", "unknown"),
                parameters=step_data.get("parameters", {}),
                done_condition=step_data.get("done_when"),
                timeout_seconds=step_data.get("timeout", 30.0)
            )
            steps.append(step)
            
        mission = Mission(
            id=mission_id,
            goal=mission_data.get("goal", "Mission sans nom"),
            reason=reason,
            steps=steps,
            priority=mission_data.get("priority", 1),
            interruptible=mission_data.get("interruptible", True)
        )
        
        self._log(f"📋 Mission LLM: {mission.goal} ({len(steps)} étapes)", "INFO")
        return mission
    
    def add_mission(self, mission: Mission) -> bool:
        """
        Add a mission to the queue.
        
        Args:
            mission: Mission to add
            
        Returns:
            True if added, False if rejected
        """
        # Check if we should interrupt current mission
        if self._current_mission:
            if mission.priority > self._current_mission.priority and self._current_mission.interruptible:
                self._log(f"⚡ Interruption: {mission.goal} > {self._current_mission.goal}", "INFO")
                self._interrupt_current_mission()
            else:
                # Add to queue
                self._mission_queue.append(mission)
                self._mission_queue.sort(key=lambda m: -m.priority)
                self._log(f"📥 Mission en queue: {mission.goal} (#{len(self._mission_queue)})", "INFO")
                return True
                
        # Start immediately if no current mission
        self._start_mission(mission)
        return True
    
    def _start_mission(self, mission: Mission):
        """Start a mission."""
        self._current_mission = mission
        mission.status = MissionStatus.IN_PROGRESS
        mission.started_at = datetime.now()
        
        self._log(f"🚀 Mission démarrée: {mission.goal}", "SUCCESS")
        
        # Start first step
        if mission.steps:
            self._start_step(mission.steps[0])
            
    def _start_step(self, step: MissionStep):
        """Start a mission step."""
        step.status = StepStatus.IN_PROGRESS
        step.started_at = datetime.now()
        
        mission = self._current_mission
        step_num = mission.current_step_index + 1 if mission else "?"
        total_steps = len(mission.steps) if mission else "?"
        
        self._log(f"▶️ Étape {step_num}/{total_steps}: {step.action}", "INFO")
        
        # Execute the action
        if self._action_executor:
            asyncio.create_task(self._execute_step(step))
            
    async def _execute_step(self, step: MissionStep):
        """Execute a step and handle completion."""
        try:
            if self._action_executor:
                success = await self._action_executor(step.action, step.parameters)
                
                if success:
                    self._complete_step(step)
                else:
                    self._fail_step(step, "Action failed")
        except asyncio.TimeoutError:
            self._fail_step(step, "Timeout")
        except Exception as e:
            self._fail_step(step, str(e))
            
    def _complete_step(self, step: MissionStep):
        """Mark a step as completed and move to next."""
        step.status = StepStatus.COMPLETED
        step.completed_at = datetime.now()
        
        self._log(f"✅ Étape terminée: {step.action}", "SUCCESS")
        
        if not self._current_mission:
            return
            
        # Move to next step
        self._current_mission.current_step_index += 1
        
        if self._current_mission.current_step_index >= len(self._current_mission.steps):
            # Mission completed
            self._complete_mission()
        else:
            # Start next step
            next_step = self._current_mission.current_step
            if next_step:
                self._start_step(next_step)
                
    def _fail_step(self, step: MissionStep, error: str):
        """Handle step failure."""
        step.status = StepStatus.FAILED
        step.error = error
        
        self._log(f"❌ Étape échouée: {step.action} - {error}", "ERROR")
        
        # For now, fail the whole mission
        # TODO: Add retry logic or alternative paths
        if self._current_mission:
            self._current_mission.status = MissionStatus.FAILED
            self._log(f"❌ Mission échouée: {self._current_mission.goal}", "ERROR")
            self._current_mission = None
            self._start_next_mission()
            
    def _complete_mission(self):
        """Mark current mission as completed."""
        if not self._current_mission:
            return
            
        self._current_mission.status = MissionStatus.COMPLETED
        self._current_mission.completed_at = datetime.now()
        
        self._log(f"🎉 Mission accomplie: {self._current_mission.goal}", "SUCCESS")
        
        self._current_mission = None
        self._start_next_mission()
        
    def _interrupt_current_mission(self):
        """Interrupt the current mission."""
        if not self._current_mission:
            return
            
        self._current_mission.status = MissionStatus.CANCELLED
        self._log(f"⏸️ Mission interrompue: {self._current_mission.goal}", "WARNING")
        
        # Put back in queue with lower priority
        self._current_mission.priority -= 1
        self._mission_queue.append(self._current_mission)
        self._current_mission = None
        
    def _start_next_mission(self):
        """Start the next mission from queue."""
        if not self._mission_queue:
            self._log("📭 Plus de missions en attente", "INFO")
            return
            
        next_mission = self._mission_queue.pop(0)
        self._start_mission(next_mission)
        
    def cancel_all(self):
        """Cancel current mission and clear queue."""
        if self._current_mission:
            self._current_mission.status = MissionStatus.CANCELLED
            self._log(f"🛑 Mission annulée: {self._current_mission.goal}", "WARNING")
            self._current_mission = None
            
        count = len(self._mission_queue)
        self._mission_queue.clear()
        
        if count > 0:
            self._log(f"🛑 {count} missions en queue annulées", "WARNING")
            
    def get_status(self) -> Dict[str, Any]:
        """Get current status for display."""
        return {
            "current_mission": self._current_mission.to_dict() if self._current_mission else None,
            "queue_size": len(self._mission_queue),
            "queue": [m.to_dict() for m in self._mission_queue[:3]]  # Show first 3
        }
    
    def detect_command(self, text: str) -> Optional[str]:
        """
        Detect if text contains a known command.
        
        Args:
            text: Input text
            
        Returns:
            Template name if found, None otherwise
        """
        text_lower = text.lower()
        
        # Command detection patterns
        patterns = {
            "au_pied": ["au pied", "aux pieds", "à mes pieds"],
            "viens_ici": ["viens ici", "viens là", "approche", "viens"],
            "assis": ["assis", "assied", "assois"],
            "couché": ["couché", "couche", "allonge"],
            "debout": ["debout", "lève", "relève"],
            "donne_la_patte": ["donne la patte", "la patte", "ta patte"],
            "fais_le_beau": ["fais le beau", "le beau", "supplie"],
            "tourne": ["tourne", "fais un tour", "pirouette"],
            "recule": ["recule", "en arrière", "va en arrière"],
            "salue": ["salue", "dis bonjour", "fais coucou"]
        }
        
        for template_name, keywords in patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return template_name
                    
        return None

