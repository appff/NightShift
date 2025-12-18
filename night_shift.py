#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v3.0 - Stateless CLI Wrapper)
Target: macOS M3 (Apple Silicon)
Version: 3.0.0

Core Features:
1. Brain Module (LLM) for autonomous decision making.
2. OODA Loop (Observe-Orient-Decide-Act) architecture.
3. Multi-LLM Support (Gemini, Claude, GPT).
4. Robust communication with Claude Code using non-interactive mode (`claude -p`).
"""

import subprocess
import sys
import time
import yaml
import re
import os
import argparse
from datetime import datetime
import json # For parsing Claude's JSON output if applicable

# --- Third-party LLM SDKs ---
from google import genai
from openai import OpenAI
from anthropic import Anthropic

# --- Configuration & Constants ---

# ANSI Escape Code Regex for cleaning output before analysis
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')

# File paths
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
REPORT_FILE = "morning_report.md"
SETTINGS_FILE = "settings.yaml"

# LLM Configuration
# 가독성 개선: 매직 넘버를 명확한 이름의 상수로 추출하여 의도를 명확히 함
MAX_CONTEXT_CHARS = 3000  # Brain에 전달할 Claude 출력의 최대 문자 수
MAX_HISTORY_CHARS = 4000  # Brain에 전달할 대화 히스토리의 최대 문자 수
MAX_TOKENS = 1024  # LLM 응답의 최대 토큰 수
RATE_LIMIT_SLEEP = 2  # Brain 반복 사이의 대기 시간 (초)

# Default model names
# 유지보수성 개선: 모델명을 한 곳에서 관리하여 변경 시 수정 지점을 명확히 함
DEFAULT_GEMINI_MODEL = 'gemini-1.5-pro'
DEFAULT_GPT_MODEL = 'gpt-4o'
DEFAULT_CLAUDE_MODEL = 'claude-3-opus-20240229'


# --- Schema Validation Functions ---

def validate_settings_schema(settings):
    """
    settings.yaml의 스키마를 검증합니다.
    
    Args:
        settings: 검증할 설정 딕셔너리
        
    Raises:
        ValueError: 스키마가 유효하지 않은 경우
    """
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary")
    
    brain_config = settings.get('brain', {})
    if not isinstance(brain_config, dict):
        raise ValueError("'brain' configuration must be a dictionary")
    
    active_model = brain_config.get('active_model', '')
    valid_models = ['gemini', 'gpt', 'claude']
    if active_model and active_model not in valid_models:
        raise ValueError(f"active_model must be one of {valid_models}, got: {active_model}")
    
    # 각 모델 설정 검증
    for model_name in valid_models:
        if model_name in brain_config:
            model_config = brain_config[model_name]
            if not isinstance(model_config, dict):
                raise ValueError(f"'{model_name}' configuration must be a dictionary")

def validate_mission_schema(mission_config):
    """
    mission.yaml의 스키마를 검증합니다.
    
    Args:
        mission_config: 검증할 미션 설정 딕셔너리
        
    Raises:
        ValueError: 스키마가 유효하지 않은 경우
    """
    if not isinstance(mission_config, dict):
        raise ValueError("Mission configuration must be a dictionary")
    
    # 필수 필드 검증
    if 'mission_name' not in mission_config:
        raise ValueError("Missing required field: 'mission_name'")
    
    if 'goal' not in mission_config or not mission_config['goal']:
        raise ValueError("Missing or empty required field: 'goal'")
    
    # 선택 필드 타입 검증
    if 'project_path' in mission_config and not isinstance(mission_config['project_path'], str):
        raise ValueError("'project_path' must be a string")
    
    if 'constraints' in mission_config and not isinstance(mission_config['constraints'], list):
        raise ValueError("'constraints' must be a list")

class Brain:
    """The Intelligence Unit. Decides what to do based on the mission and current context."""
    
    def __init__(self, settings_path=SETTINGS_FILE):
        self.settings = self._load_settings(settings_path)
        self.model_type = self.settings.get('brain', {}).get('active_model', 'gemini')
        self.client = None
        self.model_name = ""
        self._setup_client()
        
        print(f"🧠 Brain Initialized: [{self.model_type.upper()}] Mode with model: {self.model_name}")

    def _load_settings(self, path):
        """
        설정 파일을 로드하고 스키마를 검증합니다.
        
        Args:
            path: 설정 파일 경로
            
        Returns:
            dict: 파싱되고 검증된 설정 딕셔너리 (파일이 없으면 빈 딕셔너리)
            
        Raises:
            ValueError: 스키마 검증 실패 시
        """
        if not os.path.exists(path):
            print(f"⚠️  Settings file not found: {path}. Using defaults.")
            return {}
        
        with open(path, 'r', encoding='utf-8') as file:
            settings = yaml.safe_load(file)
        
        # 스키마 검증
        try:
            validate_settings_schema(settings)
        except ValueError as e:
            print(f"❌ Settings validation error: {e}")
            raise
        
        return settings

    def _setup_client(self):
        """
        LLM 클라이언트를 설정합니다.
        
        Raises:
            ValueError: API 키가 없거나 잘못된 모델 타입인 경우
        """
        brain_config = self.settings.get('brain', {})

        if self.model_type == 'gemini':
            config = brain_config.get('gemini', {})
            api_key = config.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini API Key is missing in settings.yaml or env vars.")
            self.client = genai.Client(api_key=api_key)
            self.model_name = config.get('model', DEFAULT_GEMINI_MODEL)

        elif self.model_type == 'gpt':
            config = brain_config.get('gpt', {})
            api_key = config.get('api_key') or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API Key is missing in settings.yaml or env vars.")
            self.client = OpenAI(api_key=api_key)
            self.model_name = config.get('model', DEFAULT_GPT_MODEL)

        elif self.model_type == 'claude':
            config = brain_config.get('claude', {})
            api_key = config.get('api_key') or os.getenv("CLAUDE_API_KEY")
            if not api_key:
                raise ValueError("Anthropic API Key is missing in settings.yaml or env vars.")
            self.client = Anthropic(api_key=api_key)
            self.model_name = config.get('model', DEFAULT_CLAUDE_MODEL)
        
        else:
            raise ValueError(f"Unsupported model type: '{self.model_type}'. Choose from: gemini, gpt, claude.")

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def _build_director_prompt(self, mission_goal, constraints, conversation_history, clean_output):
        """
        Director 프롬프트를 구성합니다.
        
        Args:
            mission_goal: 미션 목표
            constraints: 제약사항 리스트
            conversation_history: 대화 이력
            clean_output: ANSI 코드가 제거된 Claude 출력
            
        Returns:
            str: 구성된 프롬프트
        """
        constraints_text = '\n'.join(constraints) if isinstance(constraints, list) else str(constraints)
        
        prompt = f"""
You are the "Director" of an autonomous coding session.
Your "Actor" is a non-interactive CLI tool (Claude Code) which you invoke with `claude -p "YOUR_COMMAND_HERE" -c`.
Your goal is to guide the Actor to achieve the [MISSION GOAL].

[MISSION GOAL]
{mission_goal}

[CONSTRAINTS]
{constraints_text}

[CONVERSATION HISTORY]
{conversation_history[-MAX_HISTORY_CHARS:]}

[LAST ACTOR'S OUTPUT]
{clean_output}

[INSTRUCTIONS]
1. Analyze the [MISSION GOAL], [CONSTRAINTS], [CONVERSATION HISTORY], and [LAST ACTOR'S OUTPUT].
2. Determine the NEXT single, specific, and actionable command/query to send to Claude Code via the `-p` flag to move closer to the [MISSION GOAL].
3. **Handle Actor's Prompts:**
   - If the Actor proposes a plan, evaluate it against the [MISSION GOAL]. If good, reply with "Proceed" or "Yes".
   - If the Actor offers choices (e.g., "English or Korean?"), select the one that best fits the goal/constraints.
   - If the Actor needs confirmation (e.g., "y/n"), provide it.
4. If the Actor's output indicates the mission is complete, or you believe no further action is needed, reply with exactly: "MISSION_COMPLETED".
5. The command you output will be executed as `claude -p "YOUR_OUTPUT_HERE" -c`. Ensure it's a valid query for Claude Code.

[CRITICAL RULE]
- Your response MUST be ONLY the command/query string. No markdown, no explanations, no wrapping in quotes unless the command itself requires it.
- Do NOT repeat the exact same command if it was just executed and yielded no progress.
- Be concise and direct.
"""
        return prompt

    def _call_llm_api(self, prompt):
        """
        설정된 LLM API를 호출하여 응답을 받습니다.
        
        Args:
            prompt: LLM에 전달할 프롬프트
            
        Returns:
            str: LLM의 응답 텍스트
            
        Raises:
            ValueError: 지원하지 않는 모델 타입인 경우
            RuntimeError: LLM API 호출 실패 시
        """
        try:
            if self.model_type == 'gemini':
                # 가독성 개선: 변수명을 명확하게 변경 (resp → response)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                response_text = response.text.strip()
                print(f"--- 🧠 BRAIN RAW RESPONSE ---\n{response_text}\n--- END RAW RESPONSE ---")
                return response_text

            elif self.model_type == 'gpt':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI Director. Respond ONLY with the command to execute."},
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.choices[0].message.content.strip()
                print(f"--- 🧠 BRAIN RAW RESPONSE ---\n{response_text}\n--- END RAW RESPONSE ---")
                return response_text

            elif self.model_type == 'claude':
                message = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=MAX_TOKENS,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text.strip()
                print(f"--- 🧠 BRAIN RAW RESPONSE ---\n{response_text}\n--- END RAW RESPONSE ---")
                return response_text
            
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")
                
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to call {self.model_type} LLM: {str(e)}") from e

    def think(self, mission_goal, constraints, conversation_history, last_claude_output):
        """
        상황을 분석하고 Claude Code를 위한 다음 명령을 반환합니다.
        
        Args:
            mission_goal: 미션 목표
            constraints: 제약사항 리스트
            conversation_history: 대화 이력
            last_claude_output: 마지막 Claude 출력
            
        Returns:
            str: 다음에 실행할 명령어 또는 "MISSION_COMPLETED"/"MISSION_FAILED"
        """
        # ANSI 이스케이프 코드 제거 및 컨텍스트 크기 제한
        clean_output = self.clean_ansi(last_claude_output)[-MAX_CONTEXT_CHARS:]

        # 프롬프트 구성
        prompt = self._build_director_prompt(mission_goal, constraints, conversation_history, clean_output)
        
        # 디버깅 및 로깅용 프롬프트 출력
        print("\n--- 🧠 PROMPT TO BRAIN ---")
        print(prompt)
        print("--- END PROMPT ---")
        
        # 로그 파일에도 기록 (타임스탬프 포함)
        log_entry = f"\n{'='*80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'='*80}\n{prompt}\n"
        self._log_to_file(log_entry)

        try:
            # LLM API 호출
            response_text = self._call_llm_api(prompt)
            
            # 응답도 로그에 기록
            response_log = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-'*80}\n{response_text}\n"
            self._log_to_file(response_log)
            
            return response_text
            
        except ValueError as e:
            # 설정 오류 (잘못된 모델 타입)
            print(f"🧠 Brain Configuration Error: {e}")
            error_msg = f"MISSION_FAILED: Configuration error - {e}"
            self._log_to_file(f"\n❌ ERROR: {error_msg}\n")
            return error_msg
            
        except RuntimeError as e:
            # LLM API 호출 실패
            print(f"🧠 Brain Freeze (LLM Error): {e}")
            error_msg = f"MISSION_FAILED: {e}"
            self._log_to_file(f"\n❌ ERROR: {error_msg}\n")
            return error_msg
            
        except Exception as e:
            # 예상치 못한 오류
            print(f"🧠 Brain Freeze (Unexpected Error): {e}")
            error_msg = "MISSION_FAILED: Unexpected error during LLM call."
            self._log_to_file(f"\n❌ ERROR: {error_msg} - {e}\n")
            return error_msg

    def _log_to_file(self, message):
        """
        Brain 활동을 전용 로그 파일에 기록합니다.
        
        Args:
            message: 기록할 메시지
        """
        brain_log_file = os.path.join(LOG_DIR, f"brain_log_{datetime.now().strftime('%Y%m%d')}.txt")
        try:
            with open(brain_log_file, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception as e:
            print(f"⚠️ Failed to write to brain log: {e}")

class NightShiftAgent:
    """Night Shift 에이전트 메인 클래스"""

    def __init__(self, mission_path="mission.yaml"):
        """
        NightShiftAgent를 초기화하고 미션 설정을 로드합니다.
        
        Args:
            mission_path: 미션 설정 파일 경로
            
        Raises:
            SystemExit: 미션 파일을 찾을 수 없는 경우
            ValueError: 미션 스키마 검증 실패 시
        """
        if not os.path.exists(mission_path):
            print(f"❌ Mission file not found: {mission_path}")
            sys.exit(1)

        with open(mission_path, 'r', encoding='utf-8') as file:
            self.mission_config = yaml.safe_load(file)
        
        # 미션 스키마 검증
        try:
            validate_mission_schema(self.mission_config)
        except ValueError as e:
            print(f"❌ Mission validation error: {e}")
            sys.exit(1)
        
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        
        self.log_file_path = LOG_FILE_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.brain = Brain()
        self.conversation_history = ""
        self.last_claude_query = ""
        self.last_claude_output = ""

    def _create_system_prompt_file(self):
        """
        멀티라인 goal 처리를 위한 임시 시스템 프롬프트 파일을 생성합니다.
        
        Returns:
            str: 생성된 파일명 또는 None (goal이 없는 경우)
        """
        goal = self.mission_config.get('goal', '')
        if not goal:
            return None
        
        filename = ".night_shift_system_prompt.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(goal)
        return filename

    def _cleanup_system_prompt_file(self, filename):
        """
        임시로 생성한 시스템 프롬프트 파일을 삭제합니다.
        
        Args:
            filename: 삭제할 파일명 (None인 경우 무시)
        """
        if filename and os.path.exists(filename):
            os.remove(filename)

    def _build_claude_command(self, query):
        """
        Claude Code 실행을 위한 명령어를 구성합니다.
        
        Args:
            query: Claude에게 전달할 쿼리
            
        Returns:
            list: subprocess 실행을 위한 명령어 리스트
        """
        command = ["claude"]

        # 시스템 프롬프트 파일 또는 직접 프롬프트 추가
        if self.system_prompt_file:
            command.extend(["--system-prompt-file", self.system_prompt_file])
        elif self.mission_config.get('goal'):
            command.extend(["--system-prompt", self.mission_config['goal']])

        # 쿼리 추가
        command.extend(["-p", query])

        # 대화 계속 플래그
        command.append("-c")
        
        # 자동 파일 수정 허용
        command.append("--dangerously-skip-permissions")
        command.extend(["--allowedTools", "Write"])

        return command

    def _execute_subprocess(self, command):
        """
        subprocess를 실행하고 결과를 반환합니다.
        
        Args:
            command: 실행할 명령어 리스트
            
        Returns:
            tuple: (stdout, stderr, returncode)
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                cwd=self.mission_config.get('project_path', os.getcwd())
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
            
        except FileNotFoundError:
            error_msg = "ERROR: 'claude' command not found. Is Claude Code CLI installed and in PATH?"
            return error_msg, "", 1
        except Exception as e:
            error_msg = f"ERROR running Claude Code: {e}"
            return error_msg, "", 1

    def _run_claude_command(self, query):
        """
        Claude Code를 실행하고 결과를 반환합니다.
        
        Args:
            query: Claude에게 전달할 명령/쿼리
            
        Returns:
            str: Claude의 출력 또는 에러 메시지
        """
        if not query or query.strip() == "":
            return "ERROR: Brain sent an empty query to Claude Code. Assuming mission failure."

        # 명령어 구성
        command = self._build_claude_command(query)

        # 명령어 정보 출력
        print(f"\n--- 🚀 Running Claude Code ---")
        print(f"Full Command: {' '.join(command)}")
        print(f"Query: {query}")
        print("---")

        # 명령어 실행
        output, error, returncode = self._execute_subprocess(command)

        # 결과 출력
        print(f"--- Claude Code Output ---")
        print(output)
        if error:
            print(f"--- Claude Code Error ---")
            print(error)
        print("---")

        # 에러 처리
        if returncode != 0:
            return f"Claude Code exited with error code {returncode}:\n{output}\n{error}"
        
        return output

    def start(self):
        """
        Night Shift 에이전트를 시작하고 OODA Loop를 실행합니다.
        미션을 수행하고 대화 로그를 저장합니다.
        """
        print("🌙 Night Shift (v3.0) Starting...")
        
        project_path = self.mission_config.get('project_path', os.getcwd())
        goal = self.mission_config.get('goal', 'No goal specified')
        constraints = self.mission_config.get('constraints', [])
        
        # 멀티라인 goal 처리를 위한 시스템 프롬프트 파일 생성
        self.system_prompt_file = self._create_system_prompt_file()
        
        try:
            # 초기 미션 시작
            initial_query = "Begin the mission. Analyze the current project based on the system prompt."
            claude_output = self._run_claude_command(initial_query)
            self.conversation_history += f"Director initial instruction: {initial_query}\nActor Output:\n{claude_output}\n"
            self.last_claude_query = initial_query
            self.last_claude_output = claude_output

            # OODA Loop 실행
            while True:
                print("\n🤔 Brain is thinking...")
                next_action = self.brain.think(
                    goal,
                    constraints,
                    self.conversation_history,
                    self.last_claude_output
                )

                print(f"💡 Director (Brain): {next_action}")

                # Brain의 결정을 대화 이력에 기록
                self.conversation_history += f"\n--- 🧠 DIRECTOR (BRAIN) DECISION ---\n{next_action}\n----------------------------------\n"

                if next_action == "MISSION_COMPLETED":
                    print("🎉 Mission Accomplished. Exiting.")
                    break
                
                if next_action.startswith("MISSION_FAILED"):
                    print(f"❌ {next_action}. Exiting.")
                    break

                if next_action == self.last_claude_query:
                    print(f"⚠️ Loop detected: Brain suggested '{next_action}' again without new output. Forcing break.")
                    break

                claude_output = self._run_claude_command(next_action)
                
                # Actor의 출력을 대화 이력에 추가
                self.conversation_history += f"\n--- 🤖 ACTOR (CLAUDE) OUTPUT ---\n{claude_output}\n------------------------------\n"
                self.last_claude_query = next_action
                self.last_claude_output = claude_output
                
                # Rate limiting
                time.sleep(RATE_LIMIT_SLEEP)

        finally:
            self._cleanup_system_prompt_file(self.system_prompt_file)

        print("\n👋 Night Shift Ended.")
        
        # 대화 로그 저장
        with open(self.log_file_path, "w", encoding="utf-8") as file:
            file.write(self.conversation_history)
        print(f"📝 Full conversation log saved to: {self.log_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain-Powered Agent")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()