import os
import fnmatch
import re
from typing import List, Dict, Optional

class ContextCompressor:
    """
    Hierarchically compresses conversation history to preserve critical info.
    Prevents information loss during long-running tasks.
    """
    def __init__(self, max_chars=2000):
        self.max_chars = max_chars

    def compress(self, history: str, current_task: str) -> str:
        if len(history) <= self.max_chars:
            return history

        # Split history into logical turns
        # We look for common markers in the task history
        markers = [r'\n=== TASK \d+ START ===', r'\n--- 🧠 DIRECTOR DECISION ---', r'\n--- 🦾 HASSAN OUTPUT ---', r'\n--- 🔍 DIRECT OUTPUT ---']
        pattern = '|'.join(f'({m})' for m in markers)
        
        parts = re.split(pattern, history)
        if len(parts) <= 1:
            return history[-self.max_chars:]

        # Reconstruct sections (marker + content)
        sections = []
        i = 1
        while i < len(parts):
            marker = parts[i]
            # Find which marker was matched (re.split with groups returns many Nones)
            while marker is None and i < len(parts) - 1:
                i += 1
                marker = parts[i]
            
            content = parts[i+1] if i + 1 < len(parts) else ""
            if marker:
                sections.append(marker + content)
            i += 2

        # 1. Critical Content: Current Task Block
        critical_header = f"\n[STRATEGIC CONTEXT]\nACTIVE TASK: {current_task[:500]}\n"
        
        # 2. Recent History: Last 4 turn segments
        recent_count = 6
        recent_sections = sections[-recent_count:]
        recent_text = "".join(recent_sections)
        
        # 3. Middle History Summary: Extract commands
        summary_text = ""
        middle_sections = sections[:-recent_count]
        if middle_sections:
            past_actions = []
            for sec in middle_sections:
                if "DIRECTOR DECISION" in sec:
                    lines = sec.strip().splitlines()
                    for j, line in enumerate(lines):
                        if "DIRECTOR DECISION" in line and j + 1 < len(lines):
                            cmd = lines[j+1].strip()
                            if cmd and cmd != "MISSION_COMPLETED":
                                past_actions.append(cmd)
            
            if past_actions:
                # Keep only unique consecutive or significant actions
                summary_text = "\n[EXECUTION PATH SUMMARY]\n" + " -> ".join(past_actions[-12:]) + "\n"

        compressed = f"{critical_header}{summary_text}\n...[middle history compressed for token efficiency]...\n{recent_text}"
        
        # Final safety truncation if still too long
        if len(compressed) > self.max_chars + 500:
            return compressed[:500] + "\n...(truncated)...\n" + compressed[-(self.max_chars-500):]
        
        return compressed

class TokenOptimizer:
    """
    Optimizes context loading to save tokens and handle large projects.
    Implements Layer 0 Bootstrap and Progressive Loading.
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.ignore_patterns = [".git*", "__pycache__", "venv", "node_modules", ".DS_Store"]

    def check_readme(self) -> Optional[str]:
        """Checks if README.md exists and returns its absolute path if it does."""
        readme_path = os.path.join(self.project_root, "README.md")
        if os.path.exists(readme_path):
            return os.path.abspath(readme_path)
        return None

    def get_layer0_summary(self) -> str:
        """Returns a brief summary of the project context loading."""
        readme_path = self.check_readme()
        if readme_path:
            return "✅ Project context loaded (File tree + README.md)"
        else:
            return f"⚠️ Warning: No README.md found in {os.path.abspath(self.project_root)}. Brain may lack project overview."

    def get_layer0_context(self) -> str:
        """
        Layer 0: Bootstrap Context.
        Returns ONLY the file tree and README content.
        Lightweight start for any agent.
        """
        tree = self._get_file_tree()
        readme = self._get_readme_content()
        
        return f"""
# 📂 Project Structure (Layer 0)
{tree}

# 📄 README.md
{readme}
"""

    def classify_intent(self, task_description: str) -> str:
        """
        Heuristic intent classification to decide loading strategy.
        Returns: 'targeted' | 'scan' | 'architectural'
        """
        task = task_description.lower()
        
        if any(w in task for w in ["refactor", "restructure", "architecture", "migrate"]):
            return "architectural"
        elif any(w in task for w in ["find", "search", "audit", "review"]):
            return "scan"
        else:
            return "targeted"

    def progressive_load(self, target_files: List[str]) -> str:
        """
        Load content of specific files only.
        """
        context = []
        for file_path in target_files:
            full_path = os.path.join(self.project_root, file_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        context.append(f"--- File: {file_path} ---\n{content}\n")
                except Exception as e:
                    context.append(f"--- File: {file_path} (Error reading: {e}) ---\n")
        
        return "\n".join(context)

    def _get_file_tree(self, max_depth: int = 2) -> str:
        """Generates a visual tree structure of the project."""
        tree_lines = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Filtering
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, p) for p in self.ignore_patterns)]
            files = [f for f in files if not any(fnmatch.fnmatch(f, p) for p in self.ignore_patterns)]
            
            level = root.replace(self.project_root, '').count(os.sep)
            if level > max_depth:
                continue
                
            indent = '  ' * level
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
            for f in files:
                tree_lines.append(f"{indent}  {f}")
                
        return "\n".join(tree_lines)

    def _get_readme_content(self) -> str:
        """Reads README.md if it exists, truncated to save tokens."""
        readme_path = os.path.join(self.project_root, "README.md")
        if os.path.exists(readme_path):
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if len(content) > 2000:
                        return content[:2000] + "\n... (truncated)"
                    return content
            except:
                return "(Error reading README.md)"
        return "(No README.md found)"
