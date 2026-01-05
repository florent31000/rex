"""
People Database for Rex-Brain.
Handles face recognition and person identification.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import numpy as np

from src.utils.logger import log


class PeopleDatabase:
    """
    Database for managing known people and their face embeddings.
    
    Uses face embeddings for recognition:
    - Stores embeddings locally
    - Matches new faces against known people
    - Tracks multiple embeddings per person (different angles/lighting)
    """
    
    SIMILARITY_THRESHOLD = 0.6  # Cosine similarity threshold for recognition
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize people database.
        
        Args:
            data_dir: Directory to store face data
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent.parent / "data" / "faces"
        else:
            data_dir = Path(data_dir)
            
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing data
        self._people: Dict[str, Dict[str, Any]] = {}
        self._embeddings: Dict[str, List[np.ndarray]] = {}  # person_id -> list of embeddings
        
        self._load_data()
        
    def _load_data(self):
        """Load existing people data from disk."""
        people_file = self.data_dir / "people.json"
        
        if people_file.exists():
            try:
                with open(people_file, 'r', encoding='utf-8') as f:
                    self._people = json.load(f)
                log(f"Loaded {len(self._people)} known people", "INFO")
            except Exception as e:
                log(f"Error loading people data: {e}", "ERROR")
                self._people = {}
                
        # Load embeddings
        embeddings_dir = self.data_dir / "embeddings"
        if embeddings_dir.exists():
            for person_id in self._people:
                emb_file = embeddings_dir / f"{person_id}.npy"
                if emb_file.exists():
                    try:
                        embeddings = np.load(emb_file, allow_pickle=True)
                        self._embeddings[person_id] = list(embeddings)
                    except Exception as e:
                        log(f"Error loading embeddings for {person_id}: {e}", "WARNING")
                        
    def _save_data(self):
        """Save people data to disk."""
        # Save people info
        people_file = self.data_dir / "people.json"
        with open(people_file, 'w', encoding='utf-8') as f:
            json.dump(self._people, f, indent=2, default=str)
            
        # Save embeddings
        embeddings_dir = self.data_dir / "embeddings"
        embeddings_dir.mkdir(exist_ok=True)
        
        for person_id, embeddings in self._embeddings.items():
            if embeddings:
                emb_file = embeddings_dir / f"{person_id}.npy"
                np.save(emb_file, np.array(embeddings))
                
    def add_person(
        self,
        name: str,
        is_master: bool = False,
        embedding: Optional[np.ndarray] = None
    ) -> str:
        """
        Add a new person to the database.
        
        Args:
            name: Person's name
            is_master: Whether this is a master (owner)
            embedding: Optional initial face embedding
            
        Returns:
            Person ID
        """
        person_id = str(uuid.uuid4())[:8]
        
        self._people[person_id] = {
            "name": name,
            "is_master": is_master,
            "created": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        
        if embedding is not None:
            self._embeddings[person_id] = [embedding]
        else:
            self._embeddings[person_id] = []
            
        self._save_data()
        log(f"Added new person: {name} (ID: {person_id})", "SUCCESS")
        
        return person_id
        
    def add_embedding(self, person_id: str, embedding: np.ndarray):
        """
        Add a face embedding for an existing person.
        
        Args:
            person_id: Person's ID
            embedding: Face embedding to add
        """
        if person_id not in self._people:
            log(f"Person {person_id} not found", "WARNING")
            return
            
        if person_id not in self._embeddings:
            self._embeddings[person_id] = []
            
        # Limit number of embeddings per person
        max_embeddings = 10
        if len(self._embeddings[person_id]) >= max_embeddings:
            # Remove oldest
            self._embeddings[person_id].pop(0)
            
        self._embeddings[person_id].append(embedding)
        self._save_data()
        
    def identify(self, embedding: np.ndarray) -> Optional[Tuple[str, str, float]]:
        """
        Identify a person from a face embedding.
        
        Args:
            embedding: Face embedding to match
            
        Returns:
            (person_id, name, confidence) or None if no match
        """
        best_match = None
        best_score = 0.0
        
        for person_id, stored_embeddings in self._embeddings.items():
            if not stored_embeddings:
                continue
                
            # Calculate similarity with each stored embedding
            for stored_emb in stored_embeddings:
                similarity = self._cosine_similarity(embedding, stored_emb)
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = person_id
                    
        if best_match and best_score >= self.SIMILARITY_THRESHOLD:
            name = self._people[best_match]["name"]
            
            # Update last seen
            self._people[best_match]["last_seen"] = datetime.now().isoformat()
            self._save_data()
            
            return (best_match, name, best_score)
            
        return None
        
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        a = a.flatten()
        b = b.flatten()
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        return dot_product / (norm_a * norm_b)
        
    def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Get person info by ID."""
        return self._people.get(person_id)
        
    def get_all_people(self) -> Dict[str, Dict[str, Any]]:
        """Get all known people."""
        return self._people.copy()
        
    def get_masters(self) -> List[Tuple[str, str]]:
        """Get all masters (owners)."""
        return [
            (pid, info["name"])
            for pid, info in self._people.items()
            if info.get("is_master", False)
        ]
        
    def update_person(self, person_id: str, **kwargs):
        """Update person info."""
        if person_id not in self._people:
            return
            
        for key, value in kwargs.items():
            if key in ["name", "is_master", "notes"]:
                self._people[person_id][key] = value
                
        self._save_data()
        
    def delete_person(self, person_id: str):
        """Delete a person from the database."""
        if person_id in self._people:
            name = self._people[person_id]["name"]
            del self._people[person_id]
            
        if person_id in self._embeddings:
            del self._embeddings[person_id]
            
            # Delete embedding file
            emb_file = self.data_dir / "embeddings" / f"{person_id}.npy"
            if emb_file.exists():
                emb_file.unlink()
                
        self._save_data()
        log(f"Deleted person: {name}", "INFO")

