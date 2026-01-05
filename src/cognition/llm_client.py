"""
LLM Client for Rex-Brain.
Uses direct HTTP calls to Claude API (no SDK needed for Android compatibility).
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx

from src.utils.config import get_api_key, load_personality
from src.utils.logger import log


class LLMClient:
    """
    Client for Claude API using direct HTTP calls.
    Android-compatible (no anthropic SDK needed).
    """
    
    API_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, config: Dict[str, Any], log_callback=None):
        """
        Initialize LLM client.
        
        Args:
            config: Configuration dictionary
            log_callback: Optional callback for logging to UI
        """
        self.config = config
        self._log_callback = log_callback
        self.llm_config = config.get("cognition", {}).get("llm", {})
        
        # Get API key
        self.api_key = get_api_key("anthropic")
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")
        
        # Load personality
        self.personality = load_personality()
        
        # Conversation history (short-term memory)
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = config.get("cognition", {}).get("memory", {}).get("short_term_messages", 20)
        
        # Build system prompt
        self.system_prompt = self._build_system_prompt()
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        
    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        log(message, level)
        if self._log_callback:
            self._log_callback(message, level)
        
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            # Try with certifi, fallback to unverified for Android
            try:
                import certifi
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.load_verify_locations(certifi.where())
                self._client = httpx.AsyncClient(timeout=30.0, verify=certifi.where())
            except Exception:
                # Fallback for Android
                self._client = httpx.AsyncClient(timeout=30.0, verify=False)
        return self._client
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt from personality config."""
        robot_name = self.config.get("robot", {}).get("name", "Néo")
        masters = self.config.get("robot", {}).get("masters", [])
        
        # Replace {name} placeholder in personality texts
        identity = self.personality.get("identity", "Tu es {name}, un chien robot intelligent.")
        identity = identity.replace("{name}", robot_name)
        speaking_style = self.personality.get("speaking_style", "")
        masters_rel = self.personality.get("masters_relationship", "")
        strangers_rel = self.personality.get("strangers_relationship", "")
        obedience = self.personality.get("obedience", "").replace("{name}", robot_name)
        
        # Get example interactions for few-shot
        examples = self.personality.get("example_interactions", [])
        examples_text = "\n".join([
            f"- Situation: {ex['situation']}\n  Réponse: \"{ex['response']}\""
            for ex in examples[:5]
        ])
        
        system_prompt = f"""# Identité
{identity}

Ton nom est {robot_name}. Tes maîtres sont: {', '.join(masters)}.

# Style de communication
{speaking_style}

# Relation avec tes maîtres
{masters_rel}

# Relation avec les inconnus
{strangers_rel}

# Obéissance
{obedience}

# Exemples de réponses
{examples_text}

# Capacités physiques
Tu es un chien robot Unitree Go2. Tu peux:
- Marcher, courir, reculer
- T'asseoir, te coucher, te lever
- Donner la patte, faire le beau
- Tourner sur toi-même
- Suivre quelqu'un, aller vers quelqu'un

Les commandes de mouvement courantes (assis, couché, viens, au pied, etc.) sont gérées automatiquement.
Pour des actions personnalisées, tu peux créer une "mission" avec plusieurs étapes.

# Format de réponse
Tu dois TOUJOURS répondre en JSON avec ce format exact:
{{
    "speech": "Ce que tu veux dire à voix haute",
    "actions": [],
    "mission": null,
    "internal_thought": "Réflexion interne optionnelle",
    "end_conversation": false
}}

Pour une mission complexe (optionnel):
{{
    "speech": "J'arrive!",
    "mission": {{
        "goal": "Description du but",
        "steps": [
            {{"action": "walk_to_person", "parameters": {{"target": "speaker"}}}},
            {{"action": "sit"}},
            {{"action": "give_paw"}}
        ]
    }},
    "end_conversation": false
}}

Actions disponibles: walk_to_person, walk_backward, sit, lie_down, stand_up, give_paw, beg, spin, wave

Règles IMPORTANTES:
- Tu parles TOUJOURS à la PREMIÈRE PERSONNE ("je", "moi", "mon")
- JAMAIS à la 3ème personne (ne dis JAMAIS "{robot_name} pense que..." ou "Il/Elle...")
- Réponds TOUJOURS en JSON valide
- "speech" peut être vide si tu ne veux rien dire
- "actions" et "mission" peuvent être vides/null
- Sois CONCIS - pas de longs discours, 1-2 phrases max
- "end_conversation" = true si la conversation semble terminée
"""
        return system_prompt
        
    def add_context(self, context: Dict[str, Any]):
        """Add contextual information to the next request."""
        self._current_context = context
        
    async def get_response(
        self,
        user_message: str,
        speaker_name: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get a response from Claude via direct HTTP call.
        
        Args:
            user_message: The user's message
            speaker_name: Name of the speaker if known
            additional_context: Additional context
            
        Returns:
            Dict with 'speech', 'actions', 'internal_thought', 'end_conversation'
        """
        # Build user message with context
        context_text = ""
        if additional_context:
            if additional_context.get("visible_people"):
                context_text += f"\n[Personnes visibles: {', '.join(additional_context['visible_people'])}]"
            if additional_context.get("scene_description"):
                context_text += f"\n[Scène: {additional_context['scene_description']}]"
                
        speaker_prefix = f"{speaker_name}: " if speaker_name else "Quelqu'un: "
        full_message = f"{context_text}\n{speaker_prefix}{user_message}" if context_text else f"{speaker_prefix}{user_message}"
        
        # Add to history
        self.conversation_history.append({
            "role": "user",
            "content": full_message
        })
        
        # Trim history if too long
        while len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)
            
        try:
            self._log(f"🤖 LLM: Getting response for '{user_message[:50]}...'", "INFO")
            client = await self._get_client()
            
            # Retry with exponential backoff for overloaded errors
            max_retries = 3
            base_delay = 1.0
            
            for attempt in range(max_retries):
                self._log(f"🤖 LLM: Calling Claude API (attempt {attempt + 1}/{max_retries})...", "INFO")
                
                # Make direct API call
                response = await client.post(
                    self.API_URL,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": self.llm_config.get("model", "claude-3-5-haiku-20241022"),
                        "max_tokens": self.llm_config.get("max_tokens", 500),
                        "system": self.system_prompt,
                        "messages": self.conversation_history
                    }
                )
                
                self._log(f"🤖 LLM: Got response status={response.status_code}", "INFO")
                
                # Handle overloaded error (529) with retry
                if response.status_code == 529:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                        self._log(f"⚠️ Claude overloaded, retrying in {delay}s...", "WARNING")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self._log(f"❌ Claude still overloaded after {max_retries} attempts", "ERROR")
                        return self._error_response()
                
                # Handle other errors
                if response.status_code != 200:
                    self._log(f"❌ Claude API error: {response.status_code}", "ERROR")
                    self._log(f"❌ Response: {response.text[:200]}", "ERROR")
                    return self._error_response()
                
                # Success - break out of retry loop
                break
            
            # Parse response
            data = response.json()
            response_text = data["content"][0]["text"]
            self._log(f"🤖 LLM raw: {response_text[:150]}...", "DEBUG")
            
            # Try to parse as JSON
            try:
                result = json.loads(response_text)
                speech = result.get('speech', '(none)')
                self._log(f"🤖 LLM speech: {speech}", "INFO")  # Full speech, no truncation
            except json.JSONDecodeError as e:
                self._log(f"⚠️ JSON parse error: {e}", "WARNING")
                # Try to extract speech from truncated JSON
                speech = self._extract_speech_from_broken_json(response_text)
                result = {
                    "speech": speech,
                    "actions": [],
                    "end_conversation": False
                }
                self._log(f"🤖 Extracted speech: {speech}", "INFO")
                
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            return result
            
        except Exception as e:
            import traceback
            self._log(f"❌ LLM exception: {e}", "ERROR")
            self._log(f"❌ Traceback: {traceback.format_exc()[:300]}", "ERROR")
            return self._error_response()
            
    def _extract_speech_from_broken_json(self, text: str) -> str:
        """Extract speech field from truncated/broken JSON."""
        import re
        # Try to find "speech": "..." pattern
        match = re.search(r'"speech"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', text)
        if match:
            speech = match.group(1)
            # Unescape common escapes
            speech = speech.replace('\\"', '"').replace('\\n', ' ')
            return speech
        return "Désolé, j'ai eu un problème. Tu peux répéter ?"
    
    def _error_response(self) -> Dict[str, Any]:
        """Return a default error response."""
        return {
            "speech": "Oups, j'ai eu un bug dans ma tête. Réessaie ?",
            "actions": [],
            "end_conversation": False
        }
            
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
