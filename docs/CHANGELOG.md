# Changelog

All notable changes to Night Shift will be documented in this file.

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