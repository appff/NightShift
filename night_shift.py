#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper
Target: macOS M3 (Apple Silicon)
Version: 2.1.0 (Brain Edition - Debug Enhanced)

Core Features:
1. Brain Module (LLM) for autonomous decision making.
2. OODA Loop (Observe-Orient-Decide-Act) architecture.
3. Multi-LLM Support (Gemini, Claude, GPT)
"""

import pexpect
import sys
import time
import yaml
import re
import os
import argparse
from datetime import datetime

# --- Third-party LLM SDKs ---
try:
    import google.generativeai as genai
    from openai import OpenAI
    from anthropic import Anthropic
except ImportError:
    print("⚠️  Missing required LLM libraries. Please run: pip install google-generativeai openai anthropic")
    # We continue, assuming the user might fix it or use a mockup mode if we had one.
    # But practically, the Brain will fail.

# --- Configuration & Constants ---

# ANSI Escape Code Regex for cleaning output before analysis
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
REPORT_FILE = "morning_report.md"
SETTINGS_FILE = "settings.yaml"

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

class Brain:
    """The Intelligence Unit. Decides what to do based on the mission and current context."""
    
    def __init__(self, settings_path=SETTINGS_FILE):
        self.settings = self._load_settings(settings_path)
        self.model_type = self.settings.get('brain', {}).get('active_model', 'gemini')
        self.client = None
        self._setup_client()
        
        print(f"🧠 Brain Initialized: [{self.model_type.upper()}] Mode")

    def _load_settings(self, path):
        if not os.path.exists(path):
            print(f"⚠️  Settings file not found: {path}. Using defaults.")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _setup_client(self):
        brain_conf = self.settings.get('brain', {})
        
        if self.model_type == 'gemini':
            conf = brain_conf.get('gemini', {})
            api_key = conf.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini API Key is missing in settings.yaml or env vars.")
            genai.configure(api_key=api_key)
            self.model_name = conf.get('model', 'gemini-1.5-pro')
            
        elif self.model_type == 'gpt':
            conf = brain_conf.get('gpt', {})
            api_key = conf.get('api_key') or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API Key is missing.")
            self.client = OpenAI(api_key=api_key)
            self.model_name = conf.get('model', 'gpt-4o')
            
        elif self.model_type == 'claude':
            conf = brain_conf.get('claude', {})
            api_key = conf.get('api_key') or os.getenv("CLAUDE_API_KEY")
            if not api_key:
                raise ValueError("Anthropic API Key is missing.")
            self.client = Anthropic(api_key=api_key)
            self.model_name = conf.get('model', 'claude-3-opus-20240229')

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def think(self, mission_goal, constraints, history_text, current_screen):
        """
        Analyzes the situation and returns the next command or response.
        """
        clean_screen = self.clean_ansi(current_screen)[-3000:] # Increased context context
        
        prompt = f"""
You are the "Director" of an autonomous coding session. 
Your "Actor" is a CLI tool (Claude Code) that executes commands and asks questions.

[MISSION GOAL]
{mission_goal}

[CONSTRAINTS]
{constraints}

[CURRENT SCREEN STATE (Actor's Output)]
{clean_screen}

[HISTORY (Previous Actions)]
{history_text[-1000:]}

[INSTRUCTIONS]
1. Analyze the 'CURRENT SCREEN STATE'. The Actor is waiting for input.
2. Determine the next best action to move closer to the [MISSION GOAL].
3. If the Actor is asking a question (e.g., "Run this command?"), decide Y/N or provide the requested input based on Constraints.
4. If the Actor is idle (command finished or just started), provide the NEXT natural language instruction or shell command to proceed.
5. If the Mission is FULLY COMPLETED, reply with exactly: "MISSION_COMPLETED"

[CRITICAL RULE]
- Do NOT repeat the exact same command if it was just executed and failed or did nothing.
- If you see "Try", it's a hint. You can ignore it if you have a better plan.
- Only return the COMMAND string. No markdown, no explanations in the output.
"""
        
        response_text = ""
try:
            if self.model_type == 'gemini':
                model = genai.GenerativeModel(self.model_name)
                resp = model.generate_content(prompt)
                response_text = resp.text.strip()
                
            elif self.model_type == 'gpt':
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": "You are a helpful AI Director. Respond ONLY with the command to execute."}, 
                              {"role": "user", "content": prompt}]
                )
                response_text = resp.choices[0].message.content.strip()
                
            elif self.model_type == 'claude':
                msg = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = msg.content[0].text.strip()
                
        except Exception as e:
            print(f"🧠 Brain Freeze (Error): {e}")
            return "n" 

        return response_text

class NightShiftAgent:
    def __init__(self, mission_path="mission.yaml"):
        if not os.path.exists(mission_path):
            print(f"❌ Mission file not found: {mission_path}")
            sys.exit(1)

        with open(mission_path, 'r', encoding='utf-8') as f:
            self.mission_config = yaml.safe_load(f)
        
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        
        self.log_file_path = LOG_FILE_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.brain = Brain()
        self.child = None
        self.last_action = None
        
        self.WAIT_PATTERNS = [
            r"\? for shortcuts",           # Reliable prompt indicator in the footer
            r"Try\s+\"",                   # Matches 'Try "' 
            r">",                          # Simplest prompt matcher (Catch-all)
            r"(?:>|❯|\?)\s*$",             # Standard CLI prompt
            r"(?i)run this command\?",     # Explicit confirmation
            r"(?i)cost:.*continue\?",      # Cost check
            r"\[y/n\]",                    # Generic yes/no
            pexpect.EOF,
            pexpect.TIMEOUT
        ]

    def start(self):
        print("🌙 Night Shift (Autonomous) Starting...")
        
        project_path = self.mission_config.get('project_path', os.getcwd())
        goal = self.mission_config.get('goal', 'No goal specified')
        constraints = self.mission_config.get('constraints', [])
        
        os.chdir(project_path)
        print(f"📂 Working Directory: {project_path}")
        
        cmd = "claude"
        print(f"🚀 Spawning Actor: {cmd}")
        
        # Increased timeout slightly to avoid false positives on slow network
        self.child = pexpect.spawn(cmd, encoding='utf-8', timeout=20) 
        self.child.setwinsize(40, 120)
        
        self.logfile = open(self.log_file_path, 'w', encoding='utf-8')
        self.child.logfile_read = Tee(sys.stdout, self.logfile)
        
        try:
            print("⏳ Waiting for Actor to initialize...")
            
            history = "" 
            
            while True:
                index = self.child.expect(self.WAIT_PATTERNS)
                
                current_screen = self.child.before 
                prompt_trigger = self.child.after if isinstance(self.child.after, str) else "EOF/TIMEOUT"
                
                if index == 7: # EOF
                    print("🏁 Actor exited. Mission End.")
                    break
                
                if index == 8: # TIMEOUT
                    print("⏳ Actor is silent (Timeout). Asking Brain if we should poke it...")
                    current_screen += "\n[System Notice: The Actor has been silent for a while.]"
                
                print(f"\n--- 👁️ OBSERVED (Trigger: {repr(prompt_trigger)}) ---")
                
                print("🤔 Brain is thinking...")
                action = self.brain.think(goal, constraints, history, current_screen + prompt_trigger)
                
                # Simple loop prevention
                if action == self.last_action:
                    print(f"⚠️ Loop detected. Brain suggested '{action}' again.")
                    # We might want to force a wait or a different prompt, but for now just warn.
                
                self.last_action = action
                print(f"💡 Brain decided: '{action}'")
                
                if action == "MISSION_COMPLETED":
                    print("🎉 Mission Accomplished. Exiting.")
                    self.child.sendline("/exit")
                    break
                
                self.child.sendline(action)
                
                history += f"\n[Actor Output]: ...\n[Brain Action]: {action}\n"

        except Exception as e:
            print(f"💥 Critical Error: {e}")
        finally:
            self.child.close()
            self.logfile.close()
            print(f"📝 Log saved to: {self.log_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain-Powered Agent")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()
