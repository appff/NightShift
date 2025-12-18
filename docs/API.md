# Night Shift API Documentation

이 문서는 Night Shift의 주요 클래스와 메서드에 대한 API 레퍼런스를 제공합니다.

---

## Brain Class

**설명**: LLM을 사용하여 상황을 분석하고 다음 행동을 결정하는 지능 유닛

### Constructor

```python
Brain(settings_path=SETTINGS_FILE)
```

**Parameters**:
- `settings_path` (str): 설정 파일 경로 (기본값: "settings.yaml")

**Raises**:
- `ValueError`: API 키가 없거나 잘못된 모델 타입인 경우

---

### Methods

#### `think(mission_goal, constraints, conversation_history, last_claude_output)`

상황을 분석하고 Claude Code를 위한 다음 명령을 반환합니다.

**Parameters**:
- `mission_goal` (str): 미션 목표
- `constraints` (list): 제약사항 리스트
- `conversation_history` (str): 대화 이력
- `last_claude_output` (str): 마지막 Claude 출력

**Returns**:
- `str`: 다음에 실행할 명령어 또는 "MISSION_COMPLETED"/"MISSION_FAILED"

**Example**:
```python
brain = Brain()
next_action = brain.think(
    "Refactor the code",
    ["Don't delete files"],
    "Previous conversation...",
    "Claude's last output..."
)
```

---

#### `_build_director_prompt(mission_goal, constraints, conversation_history, clean_output)`

Director 프롬프트를 구성합니다.

**Parameters**:
- `mission_goal` (str): 미션 목표
- `constraints` (list): 제약사항 리스트
- `conversation_history` (str): 대화 이력
- `clean_output` (str): ANSI 코드가 제거된 Claude 출력

**Returns**:
- `str`: 구성된 프롬프트

---

#### `_call_llm_api(prompt)`

설정된 LLM API를 호출하여 응답을 받습니다.

**Parameters**:
- `prompt` (str): LLM에 전달할 프롬프트

**Returns**:
- `str`: LLM의 응답 텍스트

**Raises**:
- `ValueError`: 지원하지 않는 모델 타입인 경우
- `RuntimeError`: LLM API 호출 실패 시

---

#### `clean_ansi(text)`

텍스트에서 ANSI 이스케이프 코드를 제거합니다.

**Parameters**:
- `text` (str): 정리할 텍스트

**Returns**:
- `str`: ANSI 코드가 제거된 텍스트

---

## NightShiftAgent Class

**설명**: Night Shift의 메인 오케스트레이터 클래스

### Constructor

```python
NightShiftAgent(mission_path="mission.yaml")
```

**Parameters**:
- `mission_path` (str): 미션 설정 파일 경로 (기본값: "mission.yaml")

**Raises**:
- `SystemExit`: 미션 파일을 찾을 수 없거나 스키마 검증 실패 시

---

### Methods

#### `start()`

Night Shift 에이전트를 시작하고 OODA Loop를 실행합니다.

**Returns**: None

**Side Effects**:
- Claude Code를 실행하여 미션 수행
- 대화 로그를 `logs/` 디렉토리에 저장
- Brain 로그를 별도로 기록

**Example**:
```python
agent = NightShiftAgent("mission.yaml")
agent.start()
```

---

#### `_run_claude_command(query)`

Claude Code를 실행하고 결과를 반환합니다.

**Parameters**:
- `query` (str): Claude에게 전달할 명령/쿼리

**Returns**:
- `str`: Claude의 출력 또는 에러 메시지

---

#### `_build_claude_command(query)`

Claude Code 실행을 위한 명령어를 구성합니다.

**Parameters**:
- `query` (str): Claude에게 전달할 쿼리

**Returns**:
- `list`: subprocess 실행을 위한 명령어 리스트

---

#### `_execute_subprocess(command)`

subprocess를 실행하고 결과를 반환합니다.

**Parameters**:
- `command` (list): 실행할 명령어 리스트

**Returns**:
- `tuple`: (stdout, stderr, returncode)

---

## Validation Functions

### `validate_settings_schema(settings)`

settings.yaml의 스키마를 검증합니다.

**Parameters**:
- `settings` (dict): 검증할 설정 딕셔너리

**Raises**:
- `ValueError`: 스키마가 유효하지 않은 경우

**Example**:
```python
settings = yaml.safe_load(open('settings.yaml'))
validate_settings_schema(settings)
```

---

### `validate_mission_schema(mission_config)`

mission.yaml의 스키마를 검증합니다.

**Parameters**:
- `mission_config` (dict): 검증할 미션 설정 딕셔너리

**Raises**:
- `ValueError`: 스키마가 유효하지 않은 경우

**Example**:
```python
mission = yaml.safe_load(open('mission.yaml'))
validate_mission_schema(mission)
```

---

## Constants

### LLM Configuration
- `MAX_CONTEXT_CHARS` (int): Brain에 전달할 Claude 출력의 최대 문자 수 (3000)
- `MAX_HISTORY_CHARS` (int): Brain에 전달할 대화 히스토리의 최대 문자 수 (4000)
- `MAX_TOKENS` (int): LLM 응답의 최대 토큰 수 (1024)
- `RATE_LIMIT_SLEEP` (int): Brain 반복 사이의 대기 시간, 초 (2)

### Default Models
- `DEFAULT_GEMINI_MODEL` (str): 기본 Gemini 모델명 ('gemini-1.5-pro')
- `DEFAULT_GPT_MODEL` (str): 기본 GPT 모델명 ('gpt-4o')
- `DEFAULT_CLAUDE_MODEL` (str): 기본 Claude 모델명 ('claude-3-opus-20240229')

### File Paths
- `LOG_DIR` (str): 로그 디렉토리 경로 ("logs")
- `SETTINGS_FILE` (str): 설정 파일 경로 ("settings.yaml")

---

## Usage Examples

### Basic Usage

```python
from night_shift import NightShiftAgent

# 에이전트 생성 및 실행
agent = NightShiftAgent("my_mission.yaml")
agent.start()
```

### Custom Brain Usage

```python
from night_shift import Brain

# Brain 인스턴스 생성
brain = Brain("custom_settings.yaml")

# 상황 분석 및 결정
decision = brain.think(
    mission_goal="Refactor legacy code",
    constraints=["Don't delete files", "Add tests"],
    conversation_history="Previous actions...",
    last_claude_output="Claude's response..."
)

print(f"Brain decided: {decision}")
```

---

## Error Handling

Night Shift는 다음과 같은 예외를 발생시킬 수 있습니다:

- **`ValueError`**: 설정 오류 (잘못된 API 키, 모델 타입, 스키마)
- **`RuntimeError`**: LLM API 호출 실패
- **`FileNotFoundError`**: 필요한 파일이나 Claude CLI를 찾을 수 없음
- **`SystemExit`**: 치명적인 설정 오류로 프로그램 종료 필요

모든 오류는 명확한 메시지와 함께 로그에 기록됩니다.
