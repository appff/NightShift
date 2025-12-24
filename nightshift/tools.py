import os
import subprocess
import re
import logging

class SmartTools:
    """
    High-level tools for Local LLMs (DeepSeek, Qwen) to interact with the project reliably.
    Mimics the toolset available in Claude Code CLI but implemented in Python.
    """
    def __init__(self, project_root="."):
        self.project_root = os.path.abspath(project_root)

    def _resolve_path(self, path):
        return os.path.join(self.project_root, path)

    def view(self, target):
        """
        Reads content from a local file OR a URL.
        Usage: view("src/main.py") or view("https://example.com")
        """
        if target.startswith("http://") or target.startswith("https://"):
            return self._fetch_url(target)
        
        # Local file handling
        full_path = self._resolve_path(target)
        if not os.path.exists(full_path):
            return f"ERROR: File not found: {target}"
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"--- FILE: {target} ---\n{content}\n--- END OF FILE ---"
        except Exception as e:
            return f"ERROR reading file {target}: {e}"

    def _fetch_url(self, url):
        """Fetches a URL and strips HTML tags to save tokens."""
        try:
            # Use curl to fetch content (available on most unix systems)
            # -L: Follow redirects, -s: Silent
            result = subprocess.run(
                ["curl", "-L", "-s", url],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return f"ERROR fetching URL: {result.stderr}"
            
            html = result.stdout
            
            # Simple regex-based HTML tag stripping (Poor man's BeautifulSoup)
            # 1. Remove scripts and styles
            clean_text = re.sub(r'<(script|style).*?</\1>', '', html, flags=re.DOTALL)
            # 2. Remove tags
            clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
            # 3. Collapse whitespace
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            return f"--- WEB CONTENT: {url} ---\n{clean_text[:10000]} ... (truncated if too long)\n--- END OF WEB CONTENT ---"
        except Exception as e:
            return f"ERROR processing URL {url}: {e}"

    def list_files(self, path="."):
        """Lists files in a directory (like ls -R but cleaner)."""
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            return f"ERROR: Directory not found: {path}"
        
        try:
            entries = os.listdir(full_path)
            result = []
            for entry in entries:
                if entry.startswith("."): continue # Skip hidden files
                is_dir = os.path.isdir(os.path.join(full_path, entry))
                prefix = "📁 " if is_dir else "📄 "
                result.append(f"{prefix}{entry}")
            return "\n".join(sorted(result))
        except Exception as e:
            return f"ERROR listing directory {path}: {e}"

    def run_command(self, command):
        """Executes a shell command."""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                cwd=self.project_root, 
                capture_output=True, 
                text=True,
                timeout=300
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            return output.strip() if output.strip() else "(Command executed with no output)"
        except Exception as e:
            return f"ERROR executing command: {e}"

    def edit_file(self, path, old_text, new_text):
        """Replaces exact text in a file."""
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            return f"ERROR: File not found: {path}"
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_text not in content:
                return f"ERROR: 'old_text' not found in {path}. Please check exact whitespace/indentation."
            
            new_content = content.replace(old_text, new_text, 1)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            return f"SUCCESS: File {path} updated."
        except Exception as e:
            return f"ERROR editing file {path}: {e}"
