"""
Long-term memory for Rex-Brain.
Persistent storage for people, conversations, and events.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import sqlite3
import asyncio
from contextlib import contextmanager

from src.utils.logger import log


class LongTermMemory:
    """
    Long-term persistent memory using SQLite.
    
    Stores:
    - People profiles (linked to face embeddings)
    - Important conversation summaries
    - Key events and facts
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize long-term memory.
        
        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            # Default path
            data_dir = Path(__file__).parent.parent.parent.parent / "data" / "memories"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "memory.db")
            
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # People table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_master BOOLEAN DEFAULT FALSE,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP,
                    notes TEXT,
                    metadata TEXT
                )
            """)
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id TEXT,
                    summary TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    full_transcript TEXT,
                    FOREIGN KEY (person_id) REFERENCES people(id)
                )
            """)
            
            # Facts table (things learned about people/world)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    source TEXT,
                    confidence REAL DEFAULT 1.0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Events table (important happenings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    participants TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    importance INTEGER DEFAULT 5
                )
            """)
            
            conn.commit()
            
    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
            
    # ============ PEOPLE ============
    
    def add_person(
        self,
        person_id: str,
        name: str,
        is_master: bool = False,
        notes: Optional[str] = None
    ):
        """Add a new person to memory."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO people (id, name, is_master, notes, last_seen)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (person_id, name, is_master, notes))
            conn.commit()
            
        log(f"Added person to memory: {name}", "INFO")
        
    def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Get a person by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM people WHERE id = ?", (person_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
            
    def get_person_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Get people by name (may return multiple)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM people WHERE LOWER(name) = LOWER(?)",
                (name,)
            )
            return [dict(row) for row in cursor.fetchall()]
            
    def update_person_seen(self, person_id: str):
        """Update last seen timestamp for a person."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE people SET last_seen = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (person_id,))
            conn.commit()
            
    def get_all_people(self) -> List[Dict[str, Any]]:
        """Get all known people."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM people ORDER BY last_seen DESC")
            return [dict(row) for row in cursor.fetchall()]
            
    # ============ CONVERSATIONS ============
    
    def save_conversation(
        self,
        summary: str,
        person_id: Optional[str] = None,
        full_transcript: Optional[str] = None
    ):
        """Save a conversation summary."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (person_id, summary, full_transcript)
                VALUES (?, ?, ?)
            """, (person_id, summary, full_transcript))
            conn.commit()
            
    def get_conversations_with(
        self,
        person_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversations with a person."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversations
                WHERE person_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (person_id, limit))
            return [dict(row) for row in cursor.fetchall()]
            
    # ============ FACTS ============
    
    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        source: Optional[str] = None,
        confidence: float = 1.0
    ):
        """
        Add a fact (subject-predicate-object triple).
        
        Examples:
        - ("Florent", "aime", "le café")
        - ("Caroline", "travaille à", "Paris")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO facts (subject, predicate, object, source, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (subject, predicate, obj, source, confidence))
            conn.commit()
            
    def get_facts_about(self, subject: str) -> List[Dict[str, Any]]:
        """Get all facts about a subject."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM facts
                WHERE LOWER(subject) = LOWER(?)
                ORDER BY confidence DESC, timestamp DESC
            """, (subject,))
            return [dict(row) for row in cursor.fetchall()]
            
    def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search facts by any field."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM facts
                WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ?
                ORDER BY confidence DESC, timestamp DESC
                LIMIT 20
            """, (pattern, pattern, pattern))
            return [dict(row) for row in cursor.fetchall()]
            
    # ============ EVENTS ============
    
    def save_event(
        self,
        event_type: str,
        description: str,
        participants: Optional[List[str]] = None,
        importance: int = 5
    ):
        """Save an important event."""
        participants_str = ",".join(participants) if participants else None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (event_type, description, participants, importance)
                VALUES (?, ?, ?, ?)
            """, (event_type, description, participants_str, importance))
            conn.commit()
            
    def get_recent_events(
        self,
        limit: int = 20,
        min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """Get recent important events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events
                WHERE importance >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (min_importance, limit))
            return [dict(row) for row in cursor.fetchall()]
            
    # ============ CONTEXT BUILDING ============
    
    def get_context_for_person(self, person_id: str) -> str:
        """
        Get contextual information about a person for LLM.
        """
        person = self.get_person(person_id)
        if not person:
            return ""
            
        parts = [f"À propos de {person['name']}:"]
        
        # Master status
        if person.get('is_master'):
            parts.append(f"- C'est un de tes maîtres")
            
        # Notes
        if person.get('notes'):
            parts.append(f"- Notes: {person['notes']}")
            
        # Facts
        facts = self.get_facts_about(person['name'])
        if facts:
            facts_text = "; ".join([f"{f['predicate']} {f['object']}" for f in facts[:5]])
            parts.append(f"- Tu sais que: {facts_text}")
            
        # Recent conversations
        convos = self.get_conversations_with(person_id, limit=3)
        if convos:
            parts.append("- Conversations récentes:")
            for c in convos:
                parts.append(f"  * {c['summary']}")
                
        return "\n".join(parts)

