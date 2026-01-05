"""
Configuration loader for Rex-Brain.
Loads settings from YAML files.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    # Try different locations
    possible_paths = [
        Path(__file__).parent.parent.parent / "config",  # Development
        Path("/data/data/com.rexrobot.rexbrain/files/config"),  # Android app
        Path.home() / ".rex-brain" / "config",  # User home
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
            
    # Default to first option and create if needed
    default_path = possible_paths[0]
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path


def load_yaml(filename: str) -> Dict[str, Any]:
    """Load a YAML configuration file."""
    config_dir = get_config_dir()
    filepath = config_dir / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
        
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_config() -> Dict[str, Any]:
    """Load the main settings configuration."""
    return load_yaml("settings.yaml")


def load_personality() -> Dict[str, Any]:
    """Load the personality configuration."""
    return load_yaml("personality.yaml")


def get_api_key(service: str) -> Optional[str]:
    """Get an API key from configuration."""
    config = load_config()
    api_keys = config.get("api_keys", {})
    key = api_keys.get(service)
    
    if key and key.startswith("YOUR_"):
        return None  # Placeholder not replaced
        
    return key


def get_robot_name() -> str:
    """Get the robot's name from configuration."""
    config = load_config()
    return config.get("robot", {}).get("name", "Néo")


def get_masters() -> list:
    """Get the list of master names."""
    config = load_config()
    return config.get("robot", {}).get("masters", [])


class Settings:
    """Settings singleton for easy access throughout the app."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    _personality: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _load(self):
        """Load all configuration files."""
        try:
            self._config = load_config()
        except FileNotFoundError:
            self._config = {}
            
        try:
            self._personality = load_personality()
        except FileNotFoundError:
            self._personality = {}
    
    def reload(self):
        """Reload configuration from files."""
        self._load()
    
    @property
    def config(self) -> Dict[str, Any]:
        return self._config
    
    @property
    def personality(self) -> Dict[str, Any]:
        return self._personality
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation (e.g., 'robot.name')."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
                
            if value is None:
                return default
                
        return value

