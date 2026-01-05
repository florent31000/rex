"""
Short-term memory for Rex-Brain.
Handles recent conversation context and events.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque


@dataclass
class ConversationMessage:
    """A message in a conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    speaker_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Event:
    """An event that happened."""
    event_type: str  # 'person_arrived', 'person_left', 'action', etc.
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    """
    Short-term memory for maintaining conversation context.
    
    Keeps track of:
    - Recent messages in conversation
    - Recent events
    - Current scene state
    - Active speaker
    """
    
    def __init__(self, max_messages: int = 20, max_events: int = 50):
        """
        Initialize short-term memory.
        
        Args:
            max_messages: Maximum messages to retain
            max_events: Maximum events to retain
        """
        self.max_messages = max_messages
        self.max_events = max_events
        
        # Conversation history
        self._messages: deque = deque(maxlen=max_messages)
        
        # Event history
        self._events: deque = deque(maxlen=max_events)
        
        # Current state
        self._current_scene: Optional[str] = None
        self._visible_people: List[str] = []
        self._active_speaker: Optional[str] = None
        self._conversation_active: bool = False
        self._conversation_start: Optional[datetime] = None
        
    def add_message(
        self,
        role: str,
        content: str,
        speaker_name: Optional[str] = None
    ):
        """Add a message to conversation history."""
        message = ConversationMessage(
            role=role,
            content=content,
            speaker_name=speaker_name
        )
        self._messages.append(message)
        
    def add_event(
        self,
        event_type: str,
        description: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Add an event to history."""
        event = Event(
            event_type=event_type,
            description=description,
            data=data or {}
        )
        self._events.append(event)
        
    def get_messages(self, limit: Optional[int] = None) -> List[ConversationMessage]:
        """Get recent messages."""
        messages = list(self._messages)
        if limit:
            messages = messages[-limit:]
        return messages
        
    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """Get messages formatted for LLM API."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self._messages
        ]
        
    def get_events(
        self,
        since: Optional[datetime] = None,
        event_type: Optional[str] = None
    ) -> List[Event]:
        """Get events, optionally filtered."""
        events = list(self._events)
        
        if since:
            events = [e for e in events if e.timestamp >= since]
            
        if event_type:
            events = [e for e in events if e.event_type == event_type]
            
        return events
        
    def set_scene(self, description: str):
        """Update current scene description."""
        self._current_scene = description
        
    def set_visible_people(self, people: List[str]):
        """Update list of visible people."""
        # Check for arrivals
        for person in people:
            if person not in self._visible_people:
                self.add_event(
                    "person_arrived",
                    f"{person} est apparu(e)",
                    {"person": person}
                )
                
        # Check for departures
        for person in self._visible_people:
            if person not in people:
                self.add_event(
                    "person_left",
                    f"{person} est parti(e)",
                    {"person": person}
                )
                
        self._visible_people = people
        
    def set_active_speaker(self, speaker: Optional[str]):
        """Update active speaker."""
        if speaker != self._active_speaker:
            self._active_speaker = speaker
            
    def start_conversation(self):
        """Mark start of a conversation."""
        self._conversation_active = True
        self._conversation_start = datetime.now()
        
    def end_conversation(self):
        """Mark end of a conversation."""
        self._conversation_active = False
        self._conversation_start = None
        
    def is_conversation_active(self) -> bool:
        """Check if in active conversation."""
        return self._conversation_active
        
    def get_conversation_duration(self) -> Optional[timedelta]:
        """Get duration of current conversation."""
        if not self._conversation_active or not self._conversation_start:
            return None
        return datetime.now() - self._conversation_start
        
    def get_context_summary(self) -> str:
        """Get a summary of current context for LLM."""
        parts = []
        
        # Scene
        if self._current_scene:
            parts.append(f"Scène actuelle: {self._current_scene}")
            
        # Visible people
        if self._visible_people:
            parts.append(f"Personnes présentes: {', '.join(self._visible_people)}")
            
        # Active speaker
        if self._active_speaker:
            parts.append(f"Qui parle: {self._active_speaker}")
            
        # Recent events
        recent_events = self.get_events(since=datetime.now() - timedelta(minutes=5))
        if recent_events:
            events_text = "; ".join([e.description for e in recent_events[-5:]])
            parts.append(f"Événements récents: {events_text}")
            
        return "\n".join(parts) if parts else "Aucun contexte particulier."
        
    def clear(self):
        """Clear all short-term memory."""
        self._messages.clear()
        self._events.clear()
        self._current_scene = None
        self._visible_people = []
        self._active_speaker = None
        self._conversation_active = False
        self._conversation_start = None

