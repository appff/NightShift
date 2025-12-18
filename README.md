# 🌙 Night Shift: Autonomous AI Agent Orchestrator

**Night Shift**는 단순한 CLI 래퍼가 아닙니다. **Brain(두뇌)**을 탑재하여 Claude Code(CC)와 같은 AI 코딩 도구를 자율적으로 지휘하는 **오케스트레이터(Orchestrator)**입니다.

사용자가 자연어로 **목표(Goal)**를 설정하면, Night Shift의 Brain이 상황을 판단(Observe-Orient-Decide-Act)하여 작업자(CC)에게 명령을 내리고, 돌발 상황에 대처하며 미션을 완수합니다.

---

## ✨ Key Features (v2.0 Brain Edition)

*   **🧠 The Brain**: Gemini, GPT, Claude 등 강력한 LLM을 두뇌로 사용하여 상황을 판단합니다.
*   **🔄 OODA Loop**: 관찰(Observe) -> 상황파악(Orient) -> 결정(Decide) -> 행동(Act) 루프를 통해 비정형적인 상황에도 유연하게 대처합니다.
*   **🗣️ Natural Language Mission**: 딱딱한 명령어 리스트 대신, "이 코드를 리팩토링해줘"와 같은 자연어 목표를 이해합니다.
*   **🛡️ Safety & Constraints**: 미션 수행 중 지켜야 할 제약사항(파일 삭제 금지 등)을 설정하여 안전하게 작업을 수행합니다.
*   **🔌 Multi-LLM Support**: `settings.yaml`을 통해 원하는 LLM(Gemini, Claude, GPT)을 간편하게 교체하여 사용할 수 있습니다.

---

## 🚀 Getting Started

### 1. Installation

필요한 Python 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

### 2. Configuration (`settings.yaml`)

`settings.yaml` 파일에서 사용할 **Brain(LLM)**을 설정합니다. API Key는 파일에 직접 입력하거나 환경 변수로 관리할 수 있습니다.

```yaml
brain:
  active_model: "gemini" # 사용할 모델 선택 (gemini, claude, gpt)

  gemini:
    api_key: "YOUR_GEMINI_API_KEY" # 또는 환경변수 GEMINI_API_KEY
    model: "gemini-2.0-flash-exp"
```

### 3. Define Your Mission (`mission.yaml`)

수행할 작업을 정의합니다. 이제 자연어로 목표를 서술하면 됩니다.

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

*   `night_shift.py`: 메인 실행 스크립트 (The Actor & Coordinator).
*   `settings.yaml`: LLM 설정 및 API 키 관리.
*   `mission.yaml`: 미션 목표 및 제약사항 정의.
*   `logs/`: 실행 로그 저장소.
*   `morning_report.md`: (구현 예정) 작업 결과 요약 보고서.

---

## ⚠️ Disclaimer

이 도구는 강력한 권한을 가진 AI(Claude Code 등)를 자동으로 실행합니다.
*   중요한 데이터가 있는 환경에서는 **반드시 백업** 후 사용하십시오.
*   `constraints`를 통해 AI의 행동 범위를 명확히 제한하는 것을 권장합니다.