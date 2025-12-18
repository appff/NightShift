# Night Shift API Documentation

이 문서는 Night Shift의 주요 클래스와 메서드에 대한 API 레퍼런스를 제공합니다. (v4.0 기준)

---

## Brain Class

**설명**: LLM을 사용하여 상황을 분석하고 다음 행동을 결정하는 전략 유닛 (Director).

### Constructor

```python
Brain(settings)
```

**Parameters**:
- `settings` (dict): 로드된 설정 딕셔너리

---

### Methods

#### `think(mission_goal, constraints, conversation_history, last_body_output)`

상황을 분석하고 Body(Actor)를 위한 다음 명령을 반환합니다.

**Parameters**:
- `mission_goal` (str): 미션 목표
- `constraints` (list): 제약사항 리스트
- `conversation_history` (str): 대화 이력
- `last_body_output` (str): 마지막 Body 실행 결과

**Returns**:
- `str`: 다음에 실행할 명령어 또는 "MISSION_COMPLETED"

---

## Body Class

**설명**: CLI 도구(Claude, Aider 등)를 실행하는 실행 유닛 (Actor). `settings.yaml`의 설정에 따라 동적으로 드라이버를 구성합니다.

### Constructor

```python
Body(settings, mission_config)
```

**Parameters**:
- `settings` (dict): 전체 설정 딕셔너리 (`body` 섹션 포함)
- `mission_config` (dict): 미션 설정 딕셔너리

---

### Methods

#### `prepare()`

Body 실행에 필요한 리소스(예: 시스템 프롬프트 파일)를 준비합니다.

#### `run(query)`

설정된 드라이버(Command)를 실행하고 결과를 반환합니다.

**Parameters**:
- `query` (str): Body에게 전달할 명령/쿼리

**Returns**:
- `str`: 실행 결과(stdout) 또는 에러 메시지

#### `cleanup()`

사용된 임시 리소스를 정리합니다.

---

## NightShiftAgent Class

**설명**: Brain과 Body를 조율하는 메인 오케스트레이터 클래스.

### Constructor

```python
NightShiftAgent(mission_path="mission.yaml")
```

**Parameters**:
- `mission_path` (str): 미션 설정 파일 경로

---

### Methods

#### `start()`

Night Shift 에이전트를 시작하고 OODA Loop를 실행합니다.

**Process**:
1. `Body.prepare()` 호출
2. 초기 Kickstart 명령 실행
3. **Loop**:
    - Quota Limit 확인 및 대기 (`_handle_quota_limit`)
    - `Brain.think()`로 다음 행동 결정
    - `Body.run()`으로 명령 실행
    - 로그 기록 및 Rate Limiting
4. `Body.cleanup()` 호출 및 종료

---

## Validation Functions

### `validate_settings_schema(settings)`
settings.yaml의 필수 키(`brain`) 존재 여부를 검증합니다.

### `validate_mission_schema(mission_config)`
mission.yaml의 필수 키(`goal`) 존재 여부를 검증합니다.

---

## Constants

### Defaults
- `DEFAULT_GEMINI_MODEL`: 'gemini-1.5-pro-002'
- `DEFAULT_GPT_MODEL`: 'gpt-4o'
- `DEFAULT_CLAUDE_MODEL`: 'claude-3-5-sonnet-20240620'

### Limits
- `MAX_CONTEXT_CHARS`: 3000
- `MAX_HISTORY_CHARS`: 4000
- `RATE_LIMIT_SLEEP`: 2 (초)
