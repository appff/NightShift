# 작업 요청: Night Shift 시스템 구현

나는 `pexpect`를 이용해 Claude Code CLI를 자동화하는 시스템을 구축 중이다.
아래 **[설계서]**와 **[초안 코드]**를 바탕으로, 부족한 부분을 채워 **완전하게 실행 가능한 코드**를 작성해라.

---

## 🏗 [설계서: System Specification]

* **목표:** 밤사이 Claude Code가 주어진 미션을 수행하고, 명령어 승인 요청(y/n)을 정책에 따라 자동 수락한다.
* **환경:** macOS (M3), Local execution (No Docker).
* **핵심 기능:**
    1.  `mission.yaml`에서 작업 목록 로드.
    2.  `pexpect`로 `claude` 명령어 실행 및 stdout 감시.
    3.  **Safety Layer:** 위험 명령어 감지 시 프로세스 종료.
    4.  **Reporter:** 작업 종료 후 로그를 요약하여 MD 파일 생성.

---

## 🐍 [초안 코드: Draft Python Code]

```python
"""
Night Shift: Autonomous Wrapper for Claude Code
Target: macOS M3
Draft Version: 0.1
"""
import pexpect
import sys
import time
import yaml
import re
from datetime import datetime
import subprocess

# ... (여기에 사용자님이 작성하신 Python 초안 코드가 있다고 가정하고 해석할 것) ...
# (Gemini, 너는 아래 draft 로직을 기반으로 완성본을 짜야 한다.)
class ClaudeCodeWrapper:
    # ... monitor_and_approve 메서드가 핵심임 ...
    pass
