import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from difflib import SequenceMatcher

class ReflexionMemory:
    """
    Reflexion Memory system to store and retrieve structured error-solution pairs.
    Inspired by SuperClaude's evidence-based learning.
    """
    def __init__(self, memory_path: str = ".night_shift/reflexion.jsonl"):
        self.memory_path = memory_path
        self._ensure_memory_file()

    def _ensure_memory_file(self):
        """Ensure the memory file and directory exist."""
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                pass

    def add_entry(self, error_signature: str, root_cause: str, fix: str, status: str = "adopted"):
        """
        Add a new reflection entry.
        
        Args:
            error_signature: The error message or key parts of a traceback.
            root_cause: Analysis of why the error occurred.
            fix: The specific action or command that fixed it.
            status: Status of the fix (adopted/deprecated).
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "error_signature": error_signature,
            "root_cause": root_cause,
            "fix": fix,
            "status": status
        }
        
        with open(self.memory_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def find_similar_error(self, current_error: str, threshold: float = 0.7) -> Optional[Dict]:
        """
        Search past memories for a fuzzy-matched error signature.
        """
        best_match = None
        highest_ratio = 0.0

        if not os.path.exists(self.memory_path):
            return None

        with open(self.memory_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("status") != "adopted":
                        continue
                        
                    stored_error = entry.get("error_signature", "")
                    # Fuzzy matching to account for varying paths or line numbers
                    ratio = SequenceMatcher(None, current_error, stored_error).ratio()
                    
                    if ratio > highest_ratio:
                        highest_ratio = ratio
                        best_match = entry
                except json.JSONDecodeError:
                    continue

        if highest_ratio >= threshold:
            print(f"DEBUG: Found similar error in memory (Confidence: {highest_ratio:.2f})")
            return best_match
        
        return None

    def get_all_adopted_fixes(self) -> List[str]:
        """Format all adopted fixes for LLM context."""
        fixes = []
        if not os.path.exists(self.memory_path):
            return []
            
        with open(self.memory_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "adopted":
                        fixes.append(f"Error: {entry['error_signature']}\nFix: {entry['fix']}")
                except:
                    continue
        return fixes
