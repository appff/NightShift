✅ 필수 구현 요청사항 (Requirements)
위 초안 코드를 바탕으로 다음 기능들을 구체적으로 구현하여 코드를 완성해줘.

1. Regex 패턴 고도화 (Crucial)
Claude Code CLI는 단순 텍스트가 아니라 컬러 코드나 특수 문자를 뱉을 수 있다. _monitor_and_approve 메서드 내의 self.process.expect 리스트를 실제 환경에서 작동하도록 수정해줘.

ANSI Escape code를 무시하거나 처리할 수 있는 Regex 패턴 제안.

"Run this command?" 외에 "Cost: $0.15..." 같은 비용 승인 패턴도 처리.

2. Safety Guard 구현 (Critical)
_monitor_and_approve 내부에서 승인(y)을 보내기 전에, self.process.before (직전 출력 버퍼)를 검사하는 로직을 추가해.

금지 키워드: rm -rf, mkfs, dd if=/dev/zero, > /dev/sda 등.

위 키워드가 발견되면 n을 보내거나 프로세스를 즉시 kill하고 EMERGENCY_STOP 로그를 남길 것.

3. Git Backup Automation
스크립트가 시작될 때(run_night_shift 초입), 현재 작업 디렉토리에서 안전을 위해 새로운 Git 브랜치를 따는 코드를 추가해.

명령어: git checkout -b night-shift-auto-{timestamp}

4. Reporter 구현
Reporter 클래스를 구현해서 night_shift_log_*.txt 파일을 읽고 다음 정보를 추출해 morning_report.md로 저장해줘.

총 소요 시간

수행한 태스크 목록

자동 승인한 명령어 개수

(있다면) 에러 메시지 요약

5. mission.yaml 샘플
위 코드를 바로 테스트해볼 수 있는 실제 YAML 파일을 작성해줘.

시나리오: "현재 폴더의 README.md를 읽고, 오타를 3개 찾아서 수정해줘."


📤 최종 결과물 형식
night_shift.py (전체 코드)

mission.yaml (테스트용 설정)

사용 가이드 (필요한 pip install 패키지 등)
