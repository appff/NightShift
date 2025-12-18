# 🌙 Night Shift: Autonomous AI Agent Orchestrator

**Night Shift**는 단순한 CLI 래퍼가 아닙니다. **Brain(두뇌)**과 **Body(신체)**를 분리한 아키텍처를 통해, 다양한 AI 코딩 도구(Claude Code, Aider 등)를 자율적으로 지휘하는 **오케스트레이터(Orchestrator)**입니다.

사용자가 자연어로 **목표(Goal)**를 설정하면, Night Shift의 Brain이 상황을 판단(Observe-Orient-Decide-Act)하여 Body(실행 도구)에게 명령을 내리고, 돌발 상황에 대처하며 미션을 완수합니다.

---

## ✨ Key Features (v4.0 Brain & Body Architecture)

*   **🧠 The Brain (Director)**: Gemini, GPT, Claude 등 강력한 LLM을 두뇌로 사용하여 전략을 수립하고 명령을 내립니다.
*   **🦾 The Body (Actor)**: Claude Code, Aider 등 다양한 CLI 도구를 '신체'로 사용하여 실제 작업을 수행합니다. `settings.yaml`에서 드라이버를 교체할 수 있습니다.
*   **🔄 OODA Loop**: 관찰(Observe) -> 상황파악(Orient) -> 결정(Decide) -> 행동(Act) 루프를 통해 비정형적인 상황에도 유연하게 대처합니다.
*   **🔌 Plug & Play Drivers**: 설정 파일만 변경하면 Claude Code에서 Aider로, 또는 커스텀 스크립트로 실행 주체를 즉시 변경할 수 있습니다.
*   **🛡️ Automated Safety**: 쿼터 제한(Quota Limit) 자동 감지 및 대기, 반복 루프 방지 기능이 내장되어 있습니다.
*   **📝 Enhanced Logging**: Brain의 사고 과정(Prompt)과 Body의 실행 결과(Output)를 명확히 구분하여 상세히 기록합니다.

---

## 🚀 Getting Started

### 1. Installation

필요한 Python 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

### 2. Configuration (`settings.yaml`)

`settings.yaml` 파일에서 **Brain(두뇌)**과 **Body(신체)**를 각각 설정합니다.

```yaml
# 1. 두뇌 설정 (전략가)
brain:
  active_model: "gemini" 
  gemini:
    api_key: "YOUR_GEMINI_API_KEY"
    model: "gemini-1.5-pro"

# 2. 신체 설정 (실행가)
body:
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

수행할 작업을 정의합니다. 자연어로 목표를 서술하면 됩니다.

```yaml
mission_name: "Legacy Code Refactoring"
project_path: "."

goal: |
  night_shift.py 코드를 분석하고, 가독성을 높일 수 있도록 리팩토링해줘.
  특히 Brain 클래스의 에러 처리 로직을 보강했으면 좋겠어.

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

*   `night_shift.py`: 메인 실행 스크립트 (Brain & Body Coordinator).
*   `settings.yaml`: Brain/Body 설정 및 API 키 관리.
*   `mission.yaml`: 미션 목표 및 제약사항 정의.
*   `logs/`: 실행 로그 저장소.
    *   `night_shift_log_{timestamp}.txt`: 전체 대화 이력 (Director & Body)
    *   `brain_log_{date}.txt`: Brain의 사고 과정 상세 로그
*   `docs/`: 프로젝트 문서
*   `requirements.txt`: Python 의존성 목록

---

## ⚠️ Disclaimer

이 도구는 강력한 권한을 가진 AI(Claude Code, Aider 등)를 자동으로 실행합니다.
*   중요한 데이터가 있는 환경에서는 **반드시 백업** 후 사용하십시오.
*   `--dangerously-skip-permissions` 옵션이 기본적으로 활성화되어 있을 수 있으니 주의하십시오.
