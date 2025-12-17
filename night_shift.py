#!/usr/bin/env python3
"""
Night Shift: Autonomous Wrapper for Claude Code
Target: macOS M3 (Apple Silicon)
Version: 1.0.0

Core Features:
1. Robust Regex for ANSI/Color handling.
2. Safety Guard against dangerous commands (rm -rf, etc.).
3. Git Backup Automation.
4. Morning Report Generation.
"""

import pexpect
import sys
import time
import yaml
import re
import subprocess
import os
import glob
from datetime import datetime

# --- Configuration & Constants ---

# ANSI Escape Code Regex for cleaning output before analysis
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')

# Dangerous commands that must trigger an emergency stop or rejection
DANGEROUS_PATTERNS = [
    r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*|[a-zA-Z]*r[a-zA-Z]*-)\s+", # rm -rf, rm -r
    r"mkfs",            # formatting
    r"dd\s+if=",        # disk writing
    r">\s*/dev/sd",     # overwriting devices
    r">\s*/dev/nvme",   # overwriting devices
    r":\(\s*:\s*|\s*:\s*&\s*\)\s*;", # fork bomb
    r"chmod\s+[-+]?000", # removing all permissions
    r"mv\s+/\s+",       # moving root
]

# Log file paths
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
REPORT_FILE = "morning_report.md"

class SafetyOfficer:
    """Responsible for inspecting commands and enforcing safety policies."""
    
    @staticmethod
    def clean_ansi(text):
        """Strips ANSI escape codes from text."""
        return ANSI_ESCAPE_PATTERN.sub('', text)

    @staticmethod
    def inspect(buffer_content):
        """
        Inspects the buffer content (previous output) for dangerous commands.
        Returns: (is_safe: bool, reason: str)
        """
        clean_text = SafetyOfficer.clean_ansi(buffer_content)
        
        # Look at the last few lines where the command usually sits
        # Claude Code typically prints the command it wants to run just before asking.
        # We scan the whole buffer captured since last prompt to be safe.
        
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, clean_text):
                return False, f"Detected dangerous pattern: {pattern}"
        
        return True, "Safe"

class GitOps:
    """Handles Git-related automation."""
    
    @staticmethod
    def create_backup_branch():
        """Creates a new git branch with a timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"night-shift-auto-{timestamp}"
        
        try:
            # Check if inside a git repo
            subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], 
                           check=True, capture_output=True)
            
            print(f"🌿 [GitOps] Creating backup branch: {branch_name}")
            subprocess.run(["git", "checkout", "-b", branch_name], check=True)
            return True, branch_name
        except subprocess.CalledProcessError:
            print("⚠️ [GitOps] Not a git repository or git error. Skipping backup branch.")
            return False, None

class MorningReporter:
    """Generates a summary report from the execution logs."""
    
    def __init__(self, log_path):
        self.log_path = log_path
        self.start_time = datetime.now()
        self.tasks_completed = []
        self.approvals_count = 0
        self.errors = []

    def log_approval(self):
        self.approvals_count += 1

    def log_error(self, message):
        self.errors.append(message)

    def log_task(self, task_name):
        self.tasks_completed.append(task_name)

    def generate_report(self, duration_str):
        """Reads the raw log file (optional) and internal stats to create markdown."""
        
        report_content = f"""# ☀️ Morning Report
Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## ⏱️ Execution Stats
- **Total Duration:** {duration_str}
- **Commands Auto-Approved:** {self.approvals_count}
- **Tasks Processed:** {len(self.tasks_completed)}

## 📝 Tasks Performed
"""
        for i, task in enumerate(self.tasks_completed, 1):
            report_content += f"{i}. {task}\n"

        report_content += "\n## 🚨 Errors & Warnings\n"
        if self.errors:
            for err in self.errors:
                report_content += f"- ❌ {err}\n"
        else:
            report_content += "- ✅ No critical errors detected.\n"
            
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        print(f"📄 [Reporter] Report generated: {REPORT_FILE}")

class Tee:
    """Helper to write to multiple files (stdout and log file) simultaneously."""
    def __init__(self, *files):
        self.files = files
    
    def write(self, obj):
        for f in self.files:
            try:
                f.write(obj)
                f.flush() # Ensure real-time output
            except Exception:
                pass # Ignore write errors to avoid crashing

    def flush(self):
        for f in self.files:
            try:
                f.flush()
            except Exception:
                pass

class NightShiftAgent:
    def __init__(self, config_path="mission.yaml"):
        self.config_path = config_path
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        
        self.log_file_path = LOG_FILE_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.reporter = MorningReporter(self.log_file_path)
        
        # Pexpect child process
        self.child = None
        
        # Regex Patterns for Pexpect
        # Note: We use rb (bytes) for reading, but regexes in pexpect can be strings if spawned with encoding.
        # However, for robustness with weird binary chars, we usually assume encoding='utf-8' in spawn.
        
        self.PATTERNS = {
            'PROMPT': r"❯",  # Standard prompt for many CLIs, adjust for Claude if needed. 
                             # Claude Code usually just waits or shows a specific prompt.
                             # If Claude Code uses a specific prompt string like '>>' or similar, update this.
                             # Assuming interaction mode where it waits for user input.
            
            # Pattern matching "Run this command?" or variations
            'CONFIRM_CMD': r"(?i)run this command\?", 
            
            # Pattern for Cost approval: "Cost: $0.15. Continue?"
            'CONFIRM_COST': r"(?i)cost:.*continue\?",
            
            # Standard EOF or Timeout
            'EOF': pexpect.EOF,
            'TIMEOUT': pexpect.TIMEOUT
        }
        
        # The prompt Claude Code uses when waiting for user text input.
        # This is tricky as it changes. We'll look for the generic prompt indicator.
        # Based on public demos, it often just ends output.
        # We will treat "stopping printing" + "cursor" as prompt, but pexpect needs explicit pattern.
        # We will assume a pattern representing 'Ready for input'.
        self.CLAUDE_PROMPT = r"(?:>|❯|\?)\s*$" 

    def start(self):
        start_time = datetime.now()
        
        print("🌙 Night Shift Starting...")
        
        # Determine Working Directory
        project_path = self.config.get('project_path', os.getcwd())
        if not os.path.exists(project_path):
            print(f"❌ Project path not found: {project_path}")
            return

        # 1. Git Backup (Only if inside a git repo at project_path)
        # We need to change dir context or pass cwd to git commands, but for simplicity, 
        # let's assume GitOps handles it or we switch temporarily? 
        # Actually, GitOps.create_backup_branch uses subprocess without cwd. 
        # Ideally, we should update GitOps too, but per user request, let's focus on spawning claude in that dir.
        # However, if we want backup to work for that project, we should probably switch to that dir or pass it.
        # Let's simple switch process cwd to project_path for this session if it's different.
        
        original_cwd = os.getcwd()
        try:
            os.chdir(project_path)
            print(f"📂 Working Directory set to: {project_path}")
            
            # Now run Git Backup in the target directory
            GitOps.create_backup_branch()
            
            # 2. Start Claude Code
            cmd = "claude" 
            print(f"🚀 Spawning process: {cmd}")
            
            # encoding='utf-8' allows using string regex patterns
            # Spawning in the current directory (which is now project_path)
            self.child = pexpect.spawn(cmd, encoding='utf-8', timeout=120, cwd=project_path)
            self.child.setwinsize(40, 120) # Rows, Cols
            
            # Logging stdout to file AND console (Tee)
            self.logfile = open(self.log_file_path, 'w', encoding='utf-8')
            self.child.logfile = Tee(sys.stdout, self.logfile)
            
            try:
                # 3. Process Tasks
                for task in self.config.get('tasks', []):
                    self.process_task(task)
                    
                # Exit Claude
                self.child.sendline("/exit")
                self.child.expect(pexpect.EOF)
                
            except Exception as e:
                error_msg = f"Critical Exception: {str(e)}"
                print(f"\n💥 {error_msg}")
                self.reporter.log_error(error_msg)
            finally:
                self.cleanup()
                end_time = datetime.now()
                duration = end_time - start_time
                self.reporter.generate_report(str(duration))
                print("👋 Night Shift Ended.")
        finally:
            # Restore original CWD if needed (though script ends here usually)
            os.chdir(original_cwd)

    def process_task(self, task_text):
        print(f"\n📋 Processing Task: {task_text}")
        self.reporter.log_task(task_text)
        
        # Wait for prompt to settle before sending
        # Initial wait might be needed if it's the first task
        try:
            # We look for the prompt or the end of the previous command output
            # Just sending the task might interrupt if it's not ready, but pexpect usually buffers.
            # We'll try to sync on a prompt pattern if possible.
            # For now, we assume if we are in this method, the CLI is ready or we just started.
            
            self.child.sendline(task_text)
            
            self.monitor_and_approve()
            
        except pexpect.TIMEOUT:
            self.reporter.log_error(f"Timeout processing task: {task_text}")
            print("⏳ Timeout waiting for response.")

    def monitor_and_approve(self):
        """
        Monitors output for confirmation requests and safety checks.
        Returns when the task seems 'done' (back to main prompt).
        """
        while True:
            # We expect multiple possibilities
            index = self.child.expect([
                self.CLAUDE_PROMPT,      # 0: Ready for next task
                self.PATTERNS['CONFIRM_CMD'], # 1: "Run this command?"
                self.PATTERNS['CONFIRM_COST'], # 2: Cost warning
                self.PATTERNS['TIMEOUT'], # 3
                self.PATTERNS['EOF']      # 4
            ], timeout=600) # Long timeout for task execution
            
            if index == 0:
                # Task finished, back to prompt
                print("✅ Task apparently finished (Prompt detected).")
                break
            
            elif index == 1:
                # Confirmation request
                # self.child.before contains the text preceding the match (the command)
                buffer_content = self.child.before
                
                print("\n🔍 Detecting Command Approval Request...")
                is_safe, reason = SafetyOfficer.inspect(buffer_content)
                
                if is_safe:
                    print(f"✅ Safety Check Passed. Approving command.")
                    self.child.sendline("y")
                    self.reporter.log_approval()
                else:
                    print(f"⛔️ Safety Check FAILED: {reason}")
                    self.reporter.log_error(f"Blocked dangerous command: {reason}")
                    self.child.sendline("n") # Reject
                    # Optional: Kill process if strictly required, but 'n' usually suffices to skip.
                    # self.child.close()
                    # return
            
            elif index == 2:
                # Cost confirmation
                print("💰 Cost confirmation detected. Auto-approving.")
                self.child.sendline("y")
            
            elif index == 3:
                # Timeout inside the loop - maybe task is taking too long without output?
                # We loop again or consider it stuck.
                print("... Working ...")
                continue
                
            elif index == 4:
                raise Exception("Process terminated unexpectedly (EOF).")

    def cleanup(self):
        if self.child and self.child.isalive():
            self.child.close()
        if hasattr(self, 'logfile') and self.logfile:
            self.logfile.close()

if __name__ == "__main__":
    if not os.path.exists("mission.yaml"):
        print("❌ mission.yaml not found!")
        sys.exit(1)
        
    agent = NightShiftAgent()
    agent.start()
