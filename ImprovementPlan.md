# 🚀 Night Shift Performance Improvement Plan
**목표**: Brian과 Hassan의 메시지 효율성 향상 및 Loop 방지  
**작성일**: 2025-01-31  
**우선순위**: 단기 Quick Wins → 중기 구조 개선 → 장기 아키텍처 혁신

---

## 📊 현재 시스템 분석

### 핵심 병목 지점
1. **검증 루프 오버헤드**: Brain이 Hassan의 작업 결과를 매번 `cat`/`read_file`로 물리적 검증 → 2-3배 메시지 증가
2. **JSON 파싱 취약성**: Brain의 JSON 출력이 불안정하여 다중 fallback 로직 필요
3. **컨텍스트 윈도우 비효율**: 단순 tail 기반 truncation으로 중요 정보 손실 가능
4. **단일 명령 실행**: Brain이 한 번에 하나의 명령만 발행 → 배치 작업에서 비효율적
5. **고정 Thinking Budget**: 단순/복잡 작업 구분 없이 동일한 사고 비용

### 성능 메트릭 (추정)
- **평균 Task당 메시지 수**: 8-12회 (검증 포함)
- **토큰 사용량**: Task당 ~15K-25K tokens
- **Loop 발생 빈도**: 복잡한 작업의 ~15-20%

---

## 🎯 개선 제안 (우선순위별)

### ⚡ Phase 1: Quick Wins (1-2주 구현 가능)

#### 1.1 Auto-Verification Mode (최우선 🔥)
**문제**: Brain이 Hassan 작업 후 별도 검증 명령 실행 → 메시지 2배 증가  
**해결책**: Hassan이 작업 완료 시 자동으로 검증 결과 포함

**구현 방안**:
```python
# nightshift/agents.py - Hassan 클래스에 추가
def run(self, query, print_query=True, auto_verify=True):
    # 기존 실행 로직
    output = self._execute_command(query)
    
    # Auto-verification 로직
    if auto_verify and self._is_mutation_command(query):
        verification = self._generate_verification(query)
        if verification:
            verify_output = self._execute_command(verification)
            output += f"\n\n[AUTO-VERIFICATION]\n{verify_output}"
    
    return output

def _is_mutation_command(self, query):
    """파일 생성/수정 명령 감지"""
    patterns = [r'write_file', r'edit', r'echo.*>', r'cat.*>']
    return any(re.search(p, query) for p in patterns)

def _generate_verification(self, query):
    """명령어 기반 자동 검증 생성"""
    # 예: write_file foo.py → cat foo.py
    # 예: edit bar.js → rg -n "pattern" bar.js
    if 'write_file' in query:
        match = re.search(r'write_file\s+(\S+)', query)
        if match:
            return f"cat {match.group(1)}"
    return None
```

**예상 효과**:
- ✅ 메시지 수 **30-40% 감소**
- ✅ Loop 위험 **20% 감소** (검증 실패로 인한 재시도 제거)
- ⚠️ Hassan 응답 크기 약간 증가 (trade-off 가능)

---

#### 1.2 Simplified Output Format (DSL 기반)
**문제**: JSON 파싱 실패 시 복잡한 fallback 로직 필요  
**해결책**: LLM-friendly한 간단한 구조화 포맷 사용

**구현 방안**:
```python
# nightshift/orchestrator.py
def _interpret_brain_response(self, response):
    # 기존 JSON 파싱 대신 키워드 기반 파싱
    """
    예상 출력:
    ACTION: ls -la
    STATUS: CONTINUE
    
    또는:
    ACTION: none
    STATUS: COMPLETED
    """
    action_match = re.search(r'^ACTION:\s*(.+)$', response, re.MULTILINE)
    status_match = re.search(r'^STATUS:\s*(.+)$', response, re.MULTILINE)
    
    if status_match and "COMPLETED" in status_match.group(1).upper():
        return "MISSION_COMPLETED"
    
    if action_match:
        return action_match.group(1).strip()
    
    # Fallback to existing logic
    return response
```

**Brain 프롬프트 수정**:
```python
format_section = """
[OUTPUT FORMAT]
Output exactly 2 lines:
ACTION: <command string or "none">
STATUS: CONTINUE or COMPLETED

Example:
ACTION: cat hello.py
STATUS: CONTINUE
"""
```

**예상 효과**:
- ✅ 파싱 실패율 **80% 감소**
- ✅ Brain 응답 생성 속도 **15% 향상** (JSON 구조 부담 제거)
- ✅ 로컬 LLM(Ollama, DeepSeek) 호환성 향상

---

#### 1.3 Smart Orchestrator Expansion
**문제**: 단순 읽기 작업도 Hassan을 거쳐 느림  
**해결책**: Orchestrator가 더 많은 명령을 직접 실행

**구현 방안**:
```python
# nightshift/orchestrator.py
def _execute_single_task(self, ...):
    # 기존 local check 확장
    if self._is_direct_executable(next_action):
        logging.info(f"⚡ Direct Execution: {next_action}")
        local_output = self._execute_directly(next_action)
        task_history += f"\n--- ⚡ DIRECT OUTPUT ---\n{local_output}\n"
        last_output = local_output
        continue

def _is_direct_executable(self, command):
    """Python으로 직접 실행 가능한 명령 감지"""
    direct_commands = {
        "view", "read_file", "cat", "list", "ls", 
        "glob", "rg", "grep", "find", "stat"
    }
    parts = shlex.split(command)
    return parts[0] in direct_commands

def _execute_directly(self, command):
    """SmartTools를 통한 직접 실행"""
    parts = shlex.split(command)
    cmd = parts[0]
    
    if cmd in ["view", "read_file", "cat"]:
        return self.smart_tools.read_file(parts[1])
    elif cmd in ["list", "ls"]:
        return self.smart_tools.list_files(parts[1] if len(parts) > 1 else ".")
    elif cmd in ["rg", "grep"]:
        return self.smart_tools.search_file_content(parts[1], parts[2] if len(parts) > 2 else ".")
    # ... 추가 명령어
```

**예상 효과**:
- ✅ Hassan 호출 **20-30% 감소** (읽기 작업용)
- ✅ 응답 속도 **2-3배 향상** (LLM 우회)
- ✅ 토큰 비용 절감

---

### 🏗️ Phase 2: 중기 구조 개선 (1-2개월)

#### 2.1 Hierarchical Context Compression
**문제**: 단순 tail truncation으로 중요 정보 손실  
**해결책**: 우선순위 기반 계층적 압축

**구현 방안**:
```python
# nightshift/optimizer.py (신규 모듈)
class ContextCompressor:
    def __init__(self, max_chars=MAX_HISTORY_CHARS):
        self.max_chars = max_chars
        self.priority_zones = {
            "critical": 1.0,  # 현재 태스크, 최근 출력
            "recent": 0.7,    # 최근 3턴
            "summary": 0.3,   # 중간 이력 요약
        }
    
    def compress(self, history, current_task, last_output):
        """계층적 압축"""
        sections = self._parse_sections(history)
        
        # 1순위: 항상 유지
        critical = current_task + "\n\n" + last_output
        budget_remaining = self.max_chars - len(critical)
        
        # 2순위: 최근 N턴 (full)
        recent_turns = sections[-3:]
        recent_text = "\n".join(recent_turns)
        budget_remaining -= len(recent_text)
        
        # 3순위: 중간 이력 (요약)
        if budget_remaining > 0 and len(sections) > 3:
            middle = sections[:-3]
            summary = self._summarize_middle(middle)
            recent_text = summary + "\n...\n" + recent_text
        
        return critical + "\n" + recent_text
    
    def _summarize_middle(self, sections):
        """중간 이력 요약 (LLM 또는 휴리스틱)"""
        # 간단 버전: 명령어만 추출
        commands = []
        for sec in sections:
            if "BRAIN DECISION" in sec:
                commands.append(sec.split('\n')[0])
        return "Past commands: " + " → ".join(commands)
```

**예상 효과**:
- ✅ 컨텍스트 품질 **40% 향상** (중요 정보 보존)
- ✅ 장기 Task에서 Loop 위험 **30% 감소**
- ⚠️ 구현 복잡도 증가

---

#### 2.2 Confidence-Based Verification Skip
**문제**: 단순 작업도 항상 검증 → 불필요한 오버헤드  
**해결책**: 높은 신뢰도 작업은 검증 생략

**구현 방안**:
```python
# nightshift/validation.py
class ConfidenceChecker:
    def calculate_confidence(self, task_text):
        score = 100
        checks = []
        
        # Deterministic tasks = HIGH confidence
        if any(kw in task_text.lower() for kw in ["create file", "write", "copy"]):
            score += 20
            checks.append("✓ Deterministic file operation")
        
        # Exploratory tasks = LOW confidence
        if any(kw in task_text.lower() for kw in ["debug", "fix", "investigate"]):
            score -= 30
            checks.append("⚠ Exploratory/debugging task")
        
        # 파일 존재 여부 확인 가능 = HIGH
        if re.search(r'\.py|\.js|\.md', task_text):
            score += 10
            checks.append("✓ Specific file extension mentioned")
        
        return {
            "score": score,
            "status": "HIGH" if score > 80 else "MEDIUM" if score > 50 else "LOW",
            "checks": checks,
            "skip_verification": score > 85  # NEW: Auto-skip 플래그
        }

# orchestrator.py에서 활용
confidence = self.confidence_checker.calculate_confidence(task_block)
if confidence['skip_verification']:
    logging.info("⚡ High confidence task: Skipping explicit verification")
    # Hassan 응답만으로 완료 판단
```

**예상 효과**:
- ✅ 단순 작업에서 메시지 **40-50% 감소**
- ⚠️ 검증 없이 실패 시 복구 비용 증가 (안전장치 필요)

---

#### 2.3 Adaptive Thinking Budget
**문제**: 모든 작업에 동일한 사고 비용  
**해결책**: 복잡도 기반 동적 조정

**구현 방안**:
```python
# settings.yaml
brain:
  thinking_strategy: "adaptive"
  thinking_budget_map:
    simple: 2      # score > 80
    medium: 5      # score 50-80
    complex: 10    # score < 50

# agents.py
def think(self, current_task_block, ...):
    # 동적 예산 계산
    complexity = self._assess_complexity(current_task_block)
    budget = self.brain_config.get("thinking_budget_map", {}).get(complexity, 5)
    
    cognitive_strategy = f"""
[COGNITIVE STRATEGY]
- COMPLEXITY: {complexity.upper()}
- THINKING BUDGET: {budget} steps maximum
- Use 'sequential_thinking' only if task requires multi-step reasoning
"""
```

**예상 효과**:
- ✅ 단순 작업 처리 **30% 고속화**
- ✅ 복잡 작업 정확도 **15% 향상**

---

### 🌟 Phase 3: 장기 아키텍처 혁신 (3-6개월)

#### 3.1 Proactive Multi-Step Planning (Batch Mode)
**문제**: Brain이 한 번에 하나씩만 명령 실행  
**해결책**: 결정론적 작업을 배치로 그룹화

**구현 방안**:
```python
# agents.py - Brain 클래스
def think(self, ...):
    # 배치 모드 활성화 시
    if self._can_batch(current_task_block):
        return self._generate_batch_plan(current_task_block)

def _can_batch(self, task):
    """배치 가능 여부 판단"""
    # 예: "Create 5 test files", "Set up project structure"
    batch_indicators = [
        r'create \d+ files',
        r'set up.*structure',
        r'initialize.*project',
        r'install dependencies'
    ]
    return any(re.search(p, task, re.I) for p in batch_indicators)

def _generate_batch_plan(self, task):
    """Multi-step batch command 생성"""
    return {
        "command": """
# Batch execution mode
write_file test1.py "content1" && \\
write_file test2.py "content2" && \\
write_file test3.py "content3" && \\
ls -la && cat test*.py
""",
        "status": "batch"
    }
```

**Hassan 측 지원**:
```python
# Hassan이 배치 명령을 순차 실행
def run(self, query, ...):
    if "&&" in query or query.startswith("#"):
        # Multi-line script mode
        return self._execute_batch(query)
```

**예상 효과**:
- ✅ 배치 작업에서 메시지 **50-70% 감소**
- ✅ 프로젝트 초기 설정 속도 **3배 향상**
- ⚠️ 오류 처리 복잡도 증가 (중간 단계 실패 시)

---

#### 3.2 Hybrid Brain-Hassan Architecture
**문제**: Brain과 Hassan이 완전 분리되어 비효율  
**해결책**: "Smart Hassan" - 제한적 자율성 부여

**개념**:
```
현재: Brain (Director) → Hassan (Dumb Worker)
개선: Brain (Director) ⇄ Smart Hassan (Semi-Autonomous Worker)
```

**Smart Hassan 능력**:
1. **자가 검증**: 작업 완료 후 자동 검증 + 결과 보고
2. **오류 복구**: 단순 오류 자체 해결 시도 (예: 파일 없음 → 생성)
3. **명령 확장**: "Create project structure" → 자동으로 다단계 실행

**구현 방안**:
```python
# agents.py - Hassan 클래스에 추가
class SmartHassan(Hassan):
    def __init__(self, ...):
        super().__init__(...)
        self.autonomy_level = settings.get("hassan", {}).get("autonomy", "basic")
        # basic | moderate | high
    
    def run(self, query, ...):
        # 1단계: 명령 해석 및 확장
        expanded_plan = self._expand_command(query)
        
        # 2단계: 실행
        output = super().run(expanded_plan)
        
        # 3단계: 자가 검증 (autonomy=moderate 이상)
        if self.autonomy_level in ["moderate", "high"]:
            verification = self._auto_verify(expanded_plan, output)
            if not verification["success"]:
                # 4단계: 자가 복구 시도 (autonomy=high)
                if self.autonomy_level == "high":
                    fix_output = self._attempt_fix(verification["error"])
                    output += f"\n[AUTO-FIX]\n{fix_output}"
        
        return output
```

**예상 효과**:
- ✅ Brain-Hassan 왕복 **40-60% 감소**
- ✅ 단순 오류 자동 복구로 Loop **50% 감소**
- ⚠️ Hassan 복잡도 대폭 증가 (안정성 트레이드오프)

---

#### 3.3 Memory-Driven Loop Prevention
**문제**: 같은 오류 반복 발생  
**해결책**: ReflexionMemory를 적극 활용한 선제적 방지

**구현 방안**:
```python
# memory.py
class ReflexionMemory:
    def get_preventive_rules(self, task_text):
        """과거 실패 패턴 기반 예방 규칙 생성"""
        relevant_errors = self._search_similar_errors(task_text)
        
        rules = []
        for error in relevant_errors:
            if error["status"] == "adopted":
                rules.append(f"⚠️ AVOID: {error['error_signature']}")
                rules.append(f"✓ USE: {error['fix']}")
        
        return "\n".join(rules) if rules else ""

# orchestrator.py
reflexion_rules = self.reflexion_memory.get_preventive_rules(task_block)
if reflexion_rules:
    task_block = f"{task_block}\n\n[LEARNED RULES]\n{reflexion_rules}"
```

**예상 효과**:
- ✅ 반복 오류 **70% 감소**
- ✅ 장기 프로젝트에서 학습 곡선 향상

---

## 📈 예상 종합 효과

| 지표 | 현재 | Phase 1 | Phase 2 | Phase 3 |
|-----|------|---------|---------|---------|
| 평균 메시지/Task | 10회 | 6-7회 (**-30%**) | 4-5회 (**-50%**) | 2-3회 (**-70%**) |
| 토큰 사용량 | 20K | 14K (**-30%**) | 10K (**-50%**) | 6K (**-70%**) |
| Loop 발생률 | 15% | 10% (**-33%**) | 5% (**-67%**) | 2% (**-87%**) |
| 단순 작업 속도 | 기준 | 1.5배 | 2.5배 | 4배 |
| 복잡 작업 정확도 | 기준 | +10% | +20% | +30% |

---

## 🛠️ 구현 우선순위 (단기 로드맵)

### Week 1-2: Phase 1 Quick Wins
1. **Auto-Verification Mode** (2일)
   - Hassan.run()에 auto_verify 파라미터 추가
   - _generate_verification() 로직 구현
   - 설정 파일에 `auto_verify: true` 추가

2. **Simplified Output Format** (2일)
   - Brain 프롬프트를 ACTION/STATUS 포맷으로 변경
   - _interpret_brain_response() 파서 수정
   - Backward compatibility 유지 (JSON fallback)

3. **Smart Orchestrator Expansion** (3일)
   - _is_direct_executable() 확장
   - _execute_directly() 구현
   - SmartTools와 통합 테스트

### Week 3-4: Phase 1 검증 및 조정
- 실제 mission.yaml로 A/B 테스트
- 메트릭 수집 (메시지 수, 토큰, 성공률)
- 피드백 기반 fine-tuning

### Month 2-3: Phase 2 구현
- Hierarchical Context Compression
- Confidence-Based Skip
- Adaptive Thinking Budget

### Month 4-6: Phase 3 연구 및 프로토타입
- Batch Mode PoC
- Smart Hassan 아키텍처 설계
- Memory-Driven Prevention 고도화

---

## 🧪 검증 방법

### 성능 테스트 Suite
```yaml
# tests/performance/benchmark.yaml
benchmarks:
  - name: "Simple File Creation"
    task: "Create hello.py with print('hello')"
    expected_messages: 2-3  # Phase 1 목표
    
  - name: "Multi-File Setup"
    task: "Create project structure with 5 files"
    expected_messages: 3-4  # Phase 3 목표 (batch)
    
  - name: "Debug Task"
    task: "Fix authentication bug in auth.py"
    expected_messages: 6-8  # 복잡 작업 허용
    
  - name: "Loop Prevention"
    task: "Intentional error scenario"
    max_retries: 3
    expected_loop_recovery: true
```

### 메트릭 수집
```python
# nightshift/metrics.py (신규)
class PerformanceMetrics:
    def __init__(self):
        self.metrics = {
            "messages_per_task": [],
            "tokens_per_task": [],
            "verification_count": [],
            "loop_incidents": [],
            "task_success_rate": []
        }
    
    def record_task(self, task_id, data):
        self.metrics["messages_per_task"].append(data["message_count"])
        # ...
    
    def generate_report(self):
        return {
            "avg_messages": statistics.mean(self.metrics["messages_per_task"]),
            "loop_rate": len(self.metrics["loop_incidents"]) / total_tasks
        }
```

---

## 🎓 학습 및 개선 사이클

### Continuous Improvement Loop
```
1. 메트릭 수집 (매 Task마다)
   ↓
2. 주간 리뷰 (병목 분석)
   ↓
3. ReflexionMemory 업데이트 (패턴 학습)
   ↓
4. 프롬프트/로직 조정
   ↓
5. A/B 테스트
   ↓
(반복)
```

---

## ⚠️ 리스크 및 완화 전략

| 리스크 | 영향 | 확률 | 완화 전략 |
|--------|------|------|-----------|
| Auto-Verify가 잘못된 결과 승인 | 높음 | 중간 | 복잡 작업에서만 명시적 검증 유지 (Confidence 기반) |
| Batch Mode 중간 실패 | 중간 | 높음 | Atomic transaction 패턴 + 롤백 |
| Smart Hassan의 자율성 오버런 | 높음 | 낮음 | Autonomy level을 기본 "basic"으로 설정 |
| 컨텍스트 압축으로 정보 손실 | 중간 | 중간 | Critical zone을 보수적으로 설정 |

---

## 🏁 결론

이 개선 계획은 **단계적 구현**을 통해 리스크를 관리하면서도, 최종적으로 **메시지 70% 감소, Loop 87% 감소**라는 극적인 성능 향상을 목표로 합니다.

**추천 접근법**:
1. **Phase 1 Quick Wins**를 먼저 구현하여 즉각적인 30% 개선 달성
2. 실제 사용 데이터로 Phase 2의 우선순위 조정
3. Phase 3는 연구 프로젝트로 병행 진행

**다음 단계**:
- [ ] Phase 1 구현 착수 (Auto-Verification Mode부터)
- [ ] 성능 메트릭 수집 파이프라인 구축
- [ ] 첫 번째 benchmark 실행 및 baseline 확정
