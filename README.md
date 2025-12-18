# 🌙 Night Shift: Autonomous AI Agent Orchestrator

**Night Shift**는 단순한 CLI 래퍼가 아닙니다. **Brain(두뇌)**과 **Hassan(신체/노동자)**을 분리한 아키텍처를 통해, 다양한 AI 코딩 도구(Claude Code, Aider 등)를 자율적으로 지휘하는 **오케스트레이터(Orchestrator)**입니다.

사용자가 자연어로 **목표(Goal)**를 설정하면, Night Shift의 Brain이 상황을 판단(Observe-Orient-Decide-Act)하여 Hassan(실행 도구)에게 명령을 내리고, 돌발 상황에 대처하며 미션을 완수합니다.

---

## ✨ Key Features (v4.1 Brain & Hassan Architecture)

*   **🧠 The Brain (Director)**: Gemini, GPT, Claude 등 강력한 LLM을 두뇌로 사용하여 전략을 수립하고 명령을 내립니다.
*   **🦾 The Hassan (Worker)**: Claude Code, Aider 등 다양한 CLI 도구를 '신체'로 사용하여 실제 작업을 수행합니다. `settings.yaml`에서 드라이버를 교체할 수 있습니다.
*   **🔄 OODA Loop**: 관찰(Observe) -> 상황파악(Orient) -> 결정(Decide) -> 행동(Act) 루프를 통해 비정형적인 상황에도 유연하게 대처합니다.
*   **📋 Sequential Task Execution**: `mission.yaml`의 `goal`을 리스트로 작성하면, 각 항목을 순차적으로 수행하여 작업의 정확도와 성공률을 극대화합니다.
*   **🔌 Plug & Play Drivers**: 설정 파일만 변경하면 Claude Code에서 Aider로, 또는 커스텀 스크립트로 실행 주체를 즉시 변경할 수 있습니다.
*   **🛡️ Automated Safety**: 쿼터 제한(Quota Limit) 자동 감지 및 대기, 반복 루프 방지 기능이 내장되어 있습니다.
*   **📝 Enhanced Logging**: Python 표준 `logging` 모듈을 사용하여 Brain의 사고 과정과 Hassan의 실행 결과를 체계적으로 기록합니다.

---

## 🚀 Getting Started

### 1. Installation

필요한 Python 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

### 2. Configuration (`settings.yaml`)

`settings.yaml` 파일에서 **Brain(두뇌)**과 **Hassan(신체)**를 각각 설정합니다. (`body` 키워드도 호환성을 위해 지원합니다)

```yaml
# 1. 두뇌 설정 (전략가)
brain:
  active_model: "gemini" 
  gemini:
    api_key: "YOUR_GEMINI_API_KEY"
    model: "gemini-1.5-pro-002"

# 2. 신체 설정 (실행가)
hassan: # or body
  active_driver: "claude" # 사용할 드라이버 선택 (claude, aider 등)

  drivers:
    claude:
      command: "claude"
      args: ["-p", "{query}", "-c", "--dangerously-skip-permissions"]
    
    aider:
      command: "aider"
      args: ["--message", "{query}", "--no-auto-commits"]
```

### 3. Define Your Mission (`mission.yaml`)

수행할 작업을 정의합니다. 리스트(List) 형태로 작성하면 순차적으로 실행됩니다.

```yaml
mission_name: "Project Cleanup & Refactor"
project_path: "."

# [NEW] Sequential Task List
goal:
  - "docs/ 폴더 내의 오래된 문서를 찾아 삭제하거나 업데이트해줘."
  - "night_shift.py 코드의 가독성을 위해 긴 함수를 분리해줘."
  - "README.md에 최신 변경 사항을 반영해줘."

constraints:
  - "기존 기능을 깨뜨리지 말 것."
  - "주석을 꼼꼼하게 달아줄 것."
```

### 4. Run Night Shift

```bash
python3 night_shift.py
```

---

## 📂 Project Structure

*   `night_shift.py`: 메인 실행 스크립트 (Brain & Hassan Coordinator).
*   `settings.yaml`: Brain/Hassan 설정 및 API 키 관리.
*   `mission.yaml`: 미션 목표 및 제약사항 정의.
*   `logs/`: 실행 로그 저장소.
    *   `night_shift_log_{timestamp}.txt`: 런타임 로그 (logging 모듈)
    *   `night_shift_history_{timestamp}.txt`: 전체 대화 이력 (Report용)
    *   `brain_log_{date}.txt`: Brain의 사고 과정 상세 로그
*   `docs/`: 프로젝트 문서
*   `requirements.txt`: Python 의존성 목록

---

## ⚠️ Disclaimer

이 도구는 강력한 권한을 가진 AI(Claude Code, Aider 등)를 자동으로 실행합니다.
*   중요한 데이터가 있는 환경에서는 **반드시 백업** 후 사용하십시오.
*   `--dangerously-skip-permissions` 옵션이 기본적으로 활성화되어 있을 수 있으니 주의하십시오.