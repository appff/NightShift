# Changelog

All notable changes to Night Shift will be documented in this file.

## [4.2.0] - 2024-12-19

### 🚀 Pure CLI & Shadow Workspace (Current)

#### New Features
- **Pure CLI Brain**: 제거된 API SDK(google-genai, openai, anthropic)를 대신하여 `claude`, `gemini`, `codex` CLI를 직접 '두뇌'로 사용하는 구조 도입.
- **Shadow Workspace (HOME Isolation)**: Brain 실행 시 전용 `HOME` 환경 변수(`.night_shift/brain_env`)를 주입하여 세션 데이터 및 메타데이터를 작업자(Hassan)와 완벽히 격리.
- **Auth Symlinking**: 실제 `$HOME`의 인증 정보(`.claude`, `.gemini` 등)를 격리된 환경으로 자동 연결하여 로그인 상태 유지.
- **Interactive Quota Countdown**: 쿼터 제한 발생 시 1분 단위로 잔여 시간을 알려주는 카운트다운 기능 추가.
- **Relative Quota Parsing**: Gemini CLI의 "reset after 1h17m" 같은 상대 시간 형식 파싱 지원.
- **Brain Execution Timeout**: 브레인의 무한 루프나 응답 지연을 방지하기 위한 5분 타임아웃 도입.

#### Changed
- **Settings Optimization**: 더 이상 필요 없는 API Key 및 모델명 필드를 제거하고 드라이버 중심 구조로 간소화.
- **Dependency Cleanup**: `requirements.txt`에서 대형 LLM SDK 제거 (경량화).

#### Removed
- **Aider Driver**: 사용 빈도가 낮고 중복되는 `aider` 드라이버 관련 코드 및 가이드 삭제.

---

## [4.1.0] - 2024-12-18

### 🚀 Sequential Tasking & Rebranding

#### New Features
- **Sequential Task Execution**: `mission.yaml`의 `goal`을 리스트로 입력받아 순차적으로 하나씩 처리하는 기능 도입.
- **Logging Module**: `print` 기반 로깅을 Python 표준 `logging` 모듈로 전면 교체하여 로그 레벨 관리 및 파일/콘솔 이원화 지원.
- **Dynamic System Prompt**: Task가 변경될 때마다 `Hassan.prepare()`를 통해 시스템 프롬프트 파일을 갱신.

#### Changed
- **Rebranding**: 실행 주체(Actor/Body)의 명칭을 **`Hassan`**으로 변경.
- **Validation**: `mission.yaml`의 `goal` 필드가 문자열 또는 문자열 리스트인지 엄격하게 검증하는 로직 추가.

---

## [4.0.0] - 2024-12-18

### 🚀 Brain & Body Architecture (Major Update)

#### New Architecture
- **Brain & Body Separation**: `Brain`(전략가)과 `Body`(실행가)의 역할을 명확히 분리하여 모듈성 강화.
- **Pluggable Drivers**: `settings.yaml`을 통해 `claude` 외에도 `aider` 등 다양한 CLI 도구를 Body로 사용할 수 있는 구조 도입.
- **Dynamic Configuration**: 코드 수정 없이 설정 파일만으로 실행 도구(Driver)의 명령어, 인자, 환경변수를 정의 가능.

#### Added
- **`Body` Class**: CLI 도구 실행을 전담하는 클래스 신설.
- **Quota Management**: Claude Code의 쿼터 제한 발생 시 자동 대기 기능 추가.
- **Concise Prompting**: Brain에게 간결한 명령을 내리도록 지시.
- **Real-time Mirroring**: `subprocess.Popen`을 사용하여 실행 출력을 실시간으로 콘솔에 미러링.

#### Changed
- **Terminology**: `Actor`/`CC` 용어를 `Body`로 통일.
- **Dependency**: `pexpect` 의존성 완전 제거.
- **Settings Structure**: `body` 섹션 추가.

#### Technical Details
- **Environment Variables**: `${VAR_NAME}` 문법 지원.
- **Logging**: 로그 메시지에서 실행 주체 명확히 표시.

---

## [3.0.0] - 2024-12-18

### 🎉 Major Refactoring & Enhancements

#### Added
- **Stateless CLI Wrapper**: `subprocess` 기반의 안정적인 통신 방식 도입.
- **Schema Validation**: 설정 파일 검증 로직 추가.
- **Google GenAI**: 최신 `google-genai` 라이브러리로 마이그레이션.

---

## [2.0.0] - Previous Version

### Features
- Brain 기반 자율 의사결정
- OODA Loop 구현
- Multi-LLM 지원 (Gemini, GPT, Claude)