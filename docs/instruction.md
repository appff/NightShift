# 🚀 Night Shift 사용 가이드

이 문서는 Night Shift 시스템을 실행하고 활용하는 방법을 설명합니다.

### 1. 필수 패키지 설치

`night_shift.py` 스크립트 실행에 필요한 Python 패키지들을 설치해야 합니다. 터미널에서 다음 명령어를 실행하십시오:

```bash
pip install pexpect pyyaml
```

**참고:** `pexpect`는 macOS 환경에서 `pip install pexpect`로 직접 설치 가능합니다. `pyyaml`은 YAML 파일을 파싱하는 데 사용됩니다.

### 2. Claude Code CLI 설치 확인

Night Shift는 로컬에 설치된 `claude` CLI 도구를 제어합니다. `claude` 명령어가 시스템의 PATH에 올바르게 설정되어 있는지 확인하십시오. 설치되어 있지 않다면 Claude Code CLI의 공식 설치 지침에 따라 설치해야 합니다.

### 3. Night Shift 실행

`night_shift.py` 파일과 `mission.yaml` 파일이 있는 디렉토리에서 다음 명령어를 실행하십시오.

```bash
# Night Shift 스크립트에 실행 권한 부여 (한 번만 필요)
chmod +x night_shift.py

# Night Shift 시작
./night_shift.py
```

또는 Python 인터프리터를 직접 사용하여 실행할 수도 있습니다:

```bash
python3 night_shift.py
```

**주의:**
*   Night Shift의 **Git Backup** 기능은 현재 작업 디렉토리가 Git 저장소로 초기화되어 있을 때만 작동합니다. Git 저장소가 아닌 경우 해당 기능은 건너뛰고 나머지 작업이 진행됩니다.
*   스크립트 실행 중 `claude` CLI의 출력은 실시간으로 터미널에 표시되며, `logs/` 디렉토리에 상세 로그 파일로 저장됩니다.

### 4. 결과 확인

Night Shift 작업이 완료되면, 다음 파일들을 확인할 수 있습니다:

*   **`morning_report.md`**: 총 소요 시간, 수행된 태스크 목록, 자동 승인된 명령어 개수, 에러 메시지 요약 등 Night Shift 실행 결과에 대한 요약 보고서입니다.
*   **`logs/night_shift_log_YYYYMMDD_HHMMSS.txt`**: Night Shift 세션의 모든 콘솔 출력(Claude Code CLI의 출력 포함)이 기록된 상세 로그 파일입니다.

---

### 📝 `mission.yaml` 작성 예제 및 구조

`mission.yaml` 파일은 `night_shift.py`가 수행할 작업을 정의하는 핵심 설정 파일입니다.

**예시 `mission.yaml`:**

```yaml
# mission.yaml (예시)

mission_name: "코드 리팩토링 및 테스트"
project_path: "/Users/jeongminkim/Projects/MyAwesomeApp" # (선택 사항) 작업을 수행할 대상 프로젝트 경로
description: "주어진 Python 파일에서 개선점을 찾고, 리팩토링한 후 간단한 유닛 테스트를 추가합니다."
tasks:
  - "target_file.py 파일을 읽고, 코드의 복잡성을 분석해줘."
  - "분석 결과를 바탕으로 target_file.py의 'process_data' 함수를 리팩토링해서 가독성과 성능을 개선해줘."
  - "리팩토링된 'process_data' 함수에 대한 간단한 유닛 테스트 코드를 작성해서 test_target_file.py 파일에 추가해줘."
  - "추가한 유닛 테스트를 실행해서 모든 테스트가 통과하는지 확인해줘."

```

**`mission.yaml` 구조 설명:**

`mission.yaml` 파일은 크게 다음과 같은 필드로 구성됩니다:

1.  **`mission_name` (필수)**:
    *   이 미션의 전체적인 이름을 정의합니다. `morning_report.md` 파일에 미션 이름이 요약 정보로 포함될 수 있습니다.
    *   **예시**: `"코드 리팩토링 및 테스트"`, `"README.md 문서 업데이트"`

2.  **`project_path` (선택 사항)**:
    *   `claude` CLI가 실행될 **작업 디렉토리(Working Directory)**를 지정합니다.
    *   이 경로를 설정하면 Night Shift는 해당 디렉토리로 이동하여 Git 백업을 수행하고 `claude`를 실행합니다.
    *   생략 시 `night_shift.py`가 위치한 현재 디렉토리가 기본값으로 사용됩니다.
    *   **예시**: `"/Users/jeongminkim/Projects/MyProject"`

3.  **`description` (선택 사항)**:
    *   이 미션이 어떤 목적으로 수행되는지에 대한 간략한 설명을 제공합니다. 가독성을 높이는 데 도움이 됩니다.
    *   **예시**: `"주어진 Python 파일에서 개선점을 찾고, 리팩토링한 후 간단한 유닛 테스트를 추가합니다."`

4.  **`tasks` (필수)**:
    *   `claude` CLI에게 순차적으로 지시할 작업 목록입니다. 각 항목은 `claude` CLI에게 전달될 하나의 명령어 또는 지시문이 됩니다.
    *   각 작업은 `claude`가 이해하고 수행할 수 있는 형태로 작성되어야 합니다.
    *   **예시**:
        *   `- "현재 폴더의 README.md 내용을 읽어줘."`
        *   `- "내용 중에서 오타나 문법적으로 어색한 부분을 3군데 찾아서 알려줘."`
        *   `- "찾은 오타를 수정해서 README.md 파일에 덮어써줘."`

**`mission.yaml` 작성 시 팁:**

*   **구체적으로 작성**: `claude` CLI가 모호함 없이 작업을 수행할 수 있도록 최대한 구체적인 지시를 내려야 합니다. 예를 들어, "파일 수정" 대신 "A 파일의 B 함수를 C 방식으로 수정해줘"와 같이 명확하게 지시하는 것이 좋습니다.
*   **단계별 지시**: 하나의 복잡한 작업을 여러 개의 작은 `tasks`로 나누어 순서대로 지시하는 것이 효과적입니다. 이렇게 하면 각 단계의 진행 상황을 모니터링하기 쉽고, 특정 단계에서 문제가 발생했을 때 디버깅하기 용이합니다.
*   **파일 경로 포함**: 특정 파일을 대상으로 하는 작업이라면, `README.md`, `src/main.py`와 같이 정확한 파일 경로를 포함시켜야 합니다.

이제 Night Shift를 통해 Claude Code CLI 작업을 자동화할 준비가 완료되었습니다!
