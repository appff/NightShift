import json
import os
import re
from datetime import datetime


class PerformanceMetrics:
    def __init__(self, root, enabled=True):
        self.enabled = enabled
        self.metrics_path = os.path.join(root, ".night_shift", "metrics.jsonl")
        os.makedirs(os.path.dirname(self.metrics_path), exist_ok=True)
        self.records = []
        self._reset()

    def _reset(self):
        self.task_id = None
        self.task_text = None
        self.persona = None
        self.started_at = None
        self.brain_calls = 0
        self.hassan_calls = 0
        self.command_count = 0
        self.local_check_count = 0
        self.batch_count = 0
        self.brain_tokens_reported = 0
        self.hassan_tokens_reported = 0
        self.brain_tokens_estimate = 0
        self.hassan_tokens_estimate = 0

    def start_task(self, task_id, task_text, persona):
        if not self.enabled:
            return
        self._reset()
        self.task_id = task_id
        self.task_text = task_text
        self.persona = persona
        self.started_at = datetime.now().isoformat()

    def record_brain_response(self, text):
        if not self.enabled:
            return
        self.brain_calls += 1
        self.brain_tokens_reported += self._extract_tokens(text)
        self.brain_tokens_estimate += self._estimate_tokens(text)

    def record_hassan_response(self, text):
        if not self.enabled:
            return
        self.hassan_calls += 1
        self.hassan_tokens_reported += self._extract_tokens(text)
        self.hassan_tokens_estimate += self._estimate_tokens(text)

    def record_command(self, command, local_check=False, batch=False):
        if not self.enabled:
            return
        if command:
            self.command_count += 1
        if local_check:
            self.local_check_count += 1
        if batch:
            self.batch_count += 1

    def finalize_task(self, status, duration_seconds):
        if not self.enabled:
            return None
        record = {
            "task_id": self.task_id,
            "task_text": self.task_text,
            "persona": self.persona,
            "status": status,
            "started_at": self.started_at,
            "ended_at": datetime.now().isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "message_count": self.brain_calls + self.hassan_calls,
            "brain_calls": self.brain_calls,
            "hassan_calls": self.hassan_calls,
            "command_count": self.command_count,
            "local_check_count": self.local_check_count,
            "batch_count": self.batch_count,
            "tokens_reported": {
                "brain": self.brain_tokens_reported,
                "hassan": self.hassan_tokens_reported,
            },
            "tokens_estimate": {
                "brain": self.brain_tokens_estimate,
                "hassan": self.hassan_tokens_estimate,
            },
        }
        self.records.append(record)
        self._append_record(record)
        return record

    def summarize_run(self):
        if not self.enabled or not self.records:
            return {}
        totals = {
            "tasks": len(self.records),
            "message_count": 0,
            "brain_calls": 0,
            "hassan_calls": 0,
            "command_count": 0,
            "local_check_count": 0,
            "batch_count": 0,
            "tokens_reported": {"brain": 0, "hassan": 0},
            "tokens_estimate": {"brain": 0, "hassan": 0},
        }
        for record in self.records:
            totals["message_count"] += record.get("message_count", 0)
            totals["brain_calls"] += record.get("brain_calls", 0)
            totals["hassan_calls"] += record.get("hassan_calls", 0)
            totals["command_count"] += record.get("command_count", 0)
            totals["local_check_count"] += record.get("local_check_count", 0)
            totals["batch_count"] += record.get("batch_count", 0)
            totals["tokens_reported"]["brain"] += record.get("tokens_reported", {}).get("brain", 0)
            totals["tokens_reported"]["hassan"] += record.get("tokens_reported", {}).get("hassan", 0)
            totals["tokens_estimate"]["brain"] += record.get("tokens_estimate", {}).get("brain", 0)
            totals["tokens_estimate"]["hassan"] += record.get("tokens_estimate", {}).get("hassan", 0)
        return totals

    def _append_record(self, record):
        try:
            with open(self.metrics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _extract_tokens(self, text):
        if not text:
            return 0
        patterns = [
            r"tokens used\s*[:=]?\s*([0-9,]+)",
            r"tokens\s*[:=]?\s*([0-9,]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _estimate_tokens(self, text):
        if not text:
            return 0
        return max(1, int((len(text) + 3) / 4))
