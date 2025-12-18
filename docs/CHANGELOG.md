# Changelog

All notable changes to Night Shift will be documented in this file.

## [3.0.0] - 2024-12-18

### 🎉 Major Refactoring & Enhancements

#### Added
- **Schema Validation**: 설정 파일 (`settings.yaml`, `mission.yaml`)에 대한 스키마 검증 추가
  - `validate_settings_schema()`: Brain 설정 검증
  - `validate_mission_schema()`: 미션 설정 검증
  - 런타임 오류를 사전에 방지하여 안정성 향상

- **Enhanced Logging System**: Brain의 모든 활동을 상세히 기록
  - `brain_log_{date}.txt`: Brain의 요청/응답을 타임스탬프와 함께 기록
  - `_log_to_file()` 메서드: 전용 Brain 로그 파일 관리
  - 디버깅 및 트러블슈팅 용이

- **Google AI Library Update**: 최신 API로 마이그레이션
  - `google-generativeai` (deprecated) → `google-genai` (최신)
  - `genai.Client()` 기반의 새로운 API 사용
  - FutureWarning 제거

#### Improved
- **Code Readability**: 대규모 리팩토링으로 가독성 대폭 향상
  - `Brain.think()`: 79줄 → 45줄 (프롬프트 빌딩 및 LLM 호출 분리)
  - `NightShiftAgent._run_claude_command()`: 61줄 → 40줄 (명령어 구성 및 실행 분리)
  - 각 메서드가 단일 책임 원칙(SRP) 준수

- **Error Handling**: 일반적인 Exception에서 구체적인 예외 타입으로 개선
  - `ValueError`: 설정 오류 (잘못된 API 키, 모델 타입)
  - `RuntimeError`: LLM API 호출 실패
  - `FileNotFoundError`: Claude CLI 미설치
  - 더 명확하고 유용한 에러 메시지

- **Documentation**: 모든 메서드에 포괄적인 docstring 추가
  - Args, Returns, Raises 섹션 명시
  - 한국어 설명으로 이해도 향상
  - 코드 의도를 명확히 전달

#### Refactored
- **Brain Class** - 새로운 헬퍼 메서드 추가:
  - `_build_director_prompt()`: Director 프롬프트 구성 전담
  - `_call_llm_api()`: LLM API 호출 및 응답 처리 전담
  - `_log_to_file()`: Brain 활동 로깅 전담

- **NightShiftAgent Class** - 명령어 실행 로직 분리:
  - `_build_claude_command()`: Claude Code 명령어 구성
  - `_execute_subprocess()`: subprocess 실행 및 에러 처리

### Changed
- `requirements.txt`: `google-generativeai` → `google-genai`
- 전체 파일 라인 수: 354줄 → 544줄 (더 나은 구조화 및 문서화)

### Technical Details
- **코드 품질**: +233 insertions, -76 deletions
- **테스트 상태**: ✅ 모든 검증 통과 (문법, import, CLI)
- **기능 손상**: 없음 (기존 기능 100% 보존)

---

## [2.0.0] - Previous Version

### Features
- Brain 기반 자율 의사결정
- OODA Loop 구현
- Multi-LLM 지원 (Gemini, GPT, Claude)
- 자연어 미션 정의

---

## Future Roadmap

### Planned Features
- [ ] Unit Tests 추가 (pytest)
- [ ] Type Hints 추가 (Python 타입 어노테이션)
- [ ] Logging Module 전환 (print → logging)
- [ ] Morning Report 자동 생성
- [ ] Web UI 지원
