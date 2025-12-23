import os
import yaml
from typing import Dict, Optional

class ContextLoader:
    """
    Loads markdown-based persona contexts to inject into LLM prompts.
    """
    def __init__(self, personas_dir: str = "personas"):
        self.personas_dir = personas_dir

    def load_persona(self, persona_name: str) -> str:
        """
        Load a specific persona's markdown context.
        
        Args:
            persona_name: The name of the persona file (without .md extension).
            
        Returns:
            String content of the persona file, or a default fallback if not found.
        """
        file_path = os.path.join(self.personas_dir, f"{persona_name}.md")
        
        if not os.path.exists(file_path):
            print(f"WARN: Persona file '{file_path}' not found. Using default context.")
            return self._get_default_context()
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Optionally parse frontmatter if needed later
                # _, body = self._parse_frontmatter(content)
                return content
        except Exception as e:
            print(f"ERROR: Failed to load persona '{persona_name}': {e}")
            return self._get_default_context()

    def _get_default_context(self) -> str:
        """Fallback context if no persona is specified or found."""
        return """
# 🤖 General Professional Persona
Act as a senior software engineer. 
- Write clean, maintainable, and well-documented code.
- Verify your assumptions before execution.
- Always check for existing solutions before implementing new ones.
"""

    def list_available_personas(self) -> list:
        """List all available persona names."""
        if not os.path.exists(self.personas_dir):
            return []
        return [f.replace('.md', '') for f in os.listdir(self.personas_dir) if f.endswith('.md')]
