# 🌙 Night Shift: The Autonomous Overlord (v4.2)

**Night Shift**는 단순히 코딩을 돕는 도구가 아닙니다. 당신이 잠든 사이(또는 커피를 마시는 사이), **Brain(두뇌)**과 **Hassan(수행자)**이라는 두 존재가 협력하여 프로젝트를 완수하는 **자율 에이전트 오케스트레이터**입니다.

v4.2부터는 거추장스러운 API SDK와 작별하고, 오직 **순수 CLI 도구(Claude Code, Gemini CLI, Codex 등)**만을 사용하여 더욱 강력하고 격리된 방식으로 동작합니다.

---

## ✨ Why Night Shift? (Witty Features)

*   **🧠 Pure CLI Brain (Director)**: 더 이상 API 키를 찾아 헤매지 마세요. 이미 설치된 `claude`, `gemini`, `codex` CLI를 그대로 '두뇌'로 사용합니다.
*   **🏘️ Brain's Own Room (Shadow Workspace)**: Brain은 `.night_shift/brain_env`라는 자기만의 방(Isolated $HOME)에서 고민합니다. 당신의 실제 작업 세션과 Brain의 독백이 섞일 염려가 없습니다. "평행 우주"급 격리를 보장합니다!
*   **🦾 The Hassan (Worker)**: 무거운 짐은 Hassan이 듭니다. `Claude Code` 같은 강력한 수행자를 드라이버로 사용하여 실제 코드를 주무릅니다.
*   **⏳ The Patient Waiter**: 쿼터 제한(Quota Limit)에 걸리셨나요? Night Shift는 조급해하지 않습니다. 1분마다 남은 시간을 카운트다운하며 쿼터가 풀리는 순간까지 끈질기게 기다립니다.
*   **🔄 Stateless OODA Loop**: 관찰하고, 판단하고, 결정하고, 실행합니다. 매 루프마다 백지 상태에서 최신 상황을 분석하므로, 과거의 실수에 갇히지 않습니다.
*   **🔌 Zero-SDK Dependency**: `requirements.txt`가 가벼워졌습니다. 복잡한 라이브러리 설치 없이 CLI 도구만 있으면 바로 시작할 수 있습니다.

---

## 🚀 Getting Started

### 1. Preparation
사용할 CLI 도구에 미리 로그인해 두세요. (인증 정보는 Brain과 Hassan이 사이 좋게 공유합니다.)
```bash
claude login  # or gemini login, codex login
```

### 2. Configuration (`settings.yaml`)
이제 API 키 대신 실행 경로와 인자를 설정합니다. 훨씬 직관적이죠!

```yaml
brain:
  active_driver: "claude" # 전략을 짤 똑똑한 녀석
  drivers:
    claude:
      command: "claude"
      args: ["-p", "{prompt}", "--dangerously-skip-permissions"]

hassan: # 실제로 삽질을 할 녀석
  active_driver: "claude"
  drivers:
    claude:
      command: "claude"
      args: ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}", "-c", "--dangerously-skip-permissions"]
```

### 3. Run Your Mission
`mission.yaml`에 목표를 적고, 명령을 내리세요.
```bash
python3 night_shift.py mission.yaml
```

---

## 📂 The New Folder Structure

*   `night_shift.py`: 지휘 통제실.
*   `.night_shift/brain_env`: Brain의 개인 공간. (세션 데이터가 여기 격리됩니다.)
*   `logs/`: 두 존재의 은밀한 기록들.
    *   `night_shift_log_...`: 전체 진행 상황.
    *   `brain_log_...`: Brain의 깊은 고민(지시 프롬프트) 기록.
    *   `night_shift_history_...`: 나중에 보고할 때 쓰는 전체 요약.

---

## ⚠️ Safety Notice (The "Adults Only" Rule)

이 도구는 **파일 수정 및 삭제 권한을 가진 AI**를 자동으로 실행합니다.
*   **백업은 필수**입니다. Night Shift는 당신의 코드를 사랑하지만, 가끔은 너무 과격하게 사랑할 수 있습니다.
*   `--dangerously-skip-permissions` 옵션이 켜져 있으므로, 실행 전 `mission.yaml`을 한 번 더 확인하세요.

---

## 🤝 Contribution

이 토이 프로젝트가 맘에 드신다면 마음껏 주무르고 개선해 주세요. 잠은 Night Shift가 자줄 테니까요! 😴✨
