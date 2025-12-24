import os
import fnmatch
from typing import List, Dict, Optional

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
