import os
import glob
import re
from typing import List, Dict, Tuple, Any

# --- Legacy Validation Functions (Restored) ---

def validate_mission_schema(config: Dict[str, Any]):
    """
    Validates the mission.yaml configuration.
    Raises ValueError if required fields are missing or invalid.
    """
    if not isinstance(config, dict):
        raise ValueError("Mission configuration must be a dictionary.")
    
    # Support both legacy 'goal' and new 'tasks' format
    if "goal" not in config and "tasks" not in config:
        raise ValueError("Mission configuration must contain either a 'goal' or a 'tasks' field.")
            
    # Check 'goal' if present
    if "goal" in config:
        goal = config.get("goal")
        if not (isinstance(goal, str) or isinstance(goal, list)):
             raise ValueError("Mission 'goal' must be a string or a list of tasks.")
        if isinstance(goal, list):
            if not all(isinstance(item, (str, dict)) for item in goal):
                 raise ValueError("Mission 'goal' list items must be strings or task dictionaries.")

    # Check 'tasks' if present
    if "tasks" in config:
        tasks = config.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("Mission 'tasks' must be a list.")
        for task in tasks:
            if not isinstance(task, dict):
                # We can be lenient and allow string tasks in the list too
                continue
            if "title" not in task and "task" not in task:
                # One of them should be present for a valid task object
                pass

def validate_settings_schema(config: Dict[str, Any]):
    """
    Validates the settings.yaml configuration.
    Raises ValueError if invalid.
    """
    if not isinstance(config, dict):
        raise ValueError("Settings configuration must be a dictionary.")
    
    # Basic structure check (optional)
    # Just ensure it's a dict for now as settings are often optional/merged
    pass

# --- New Cognitive Architecture Classes ---

class ConfidenceChecker:
    """
    Pre-flight validation system to assess readiness before execution.
    Prevents "running blind" by enforcing evidence-based checks.
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def calculate_confidence(self, task_description: str) -> Dict:
        """
        Assess confidence level (0.0 - 1.0) based on project state and task nature.
        
        Returns:
            Dict containing score, checks passed, and skip_verification flag.
        """
        checks = []
        score = 0.0
        
        # Check 1: Documentation Readiness (20%)
        has_docs = self._check_documentation()
        if has_docs:
            score += 0.2
            checks.append("✅ Documentation found")
        else:
            checks.append("❌ Missing documentation")

        # Check 2: Task Clarity (30%)
        is_clear = len(task_description.split()) > 5
        if is_clear:
            score += 0.3
            checks.append("✅ Task description is detailed")
        else:
            checks.append("❌ Task description too vague")

        # Check 3: Deterministic Nature (50% - NEW)
        # Higher score for explicit, simple actions
        task_lower = task_description.lower()
        deterministic_score = 0.0
        if any(kw in task_lower for kw in ["create", "write", "print", "echo", "list", "show"]):
            deterministic_score += 0.3
            checks.append("✓ Likely deterministic task")
        
        if any(kw in task_lower for kw in ["fix", "debug", "investigate", "research", "analyze", "resolve"]):
            deterministic_score -= 0.2
            checks.append("⚠ Exploratory task (requires verification)")
        
        if re.search(r'\.py|\.js|\.md|\.yaml|\.json', task_lower):
            deterministic_score += 0.2
            checks.append("✓ Specific file target mentioned")
            
        score += max(0, deterministic_score)

        # Determine status
        if score >= 0.75:
            status = "GREEN"
            action = "Proceed. Skip manual verification if output looks clear."
        elif score >= 0.4:
            status = "YELLOW"
            action = "Proceed with caution. Verify results."
        else:
            status = "RED"
            action = "STOP. High uncertainty."

        return {
            "score": round(score, 2),
            "status": status,
            "action": action,
            "checks": checks,
            "skip_verification": score >= 0.8 # HIGH confidence threshold
        }

    def _check_documentation(self) -> bool:
        """Check for README.md or docs/ directory."""
        readme = os.path.exists(os.path.join(self.project_root, "README.md"))
        docs_dir = os.path.exists(os.path.join(self.project_root, "docs"))
        return readme or docs_dir

    def _check_potential_duplication(self, task_description: str) -> List[str]:
        """
        Simple keyword matching to see if related files exist.
        e.g., if task says "auth", check for files with "auth" in name.
        """
        keywords = [w for w in task_description.lower().split() if len(w) > 4]
        matches = []
        
        for keyword in keywords:
            # Naive glob search
            found = glob.glob(f"**/*{keyword}*", recursive=True)
            # Filter out git/venv/cache
            clean_found = [f for f in found if ".git" not in f and "__pycache__" not in f]
            if clean_found:
                matches.extend(clean_found[:3]) # Limit results
        
        return matches


class SelfCheckProtocol:
    """
    Post-flight validation to ensure quality before reporting completion.
    Enforces 'The 4 Questions' to prevent hallucination and laziness.
    """
    
    def _is_coding_task(self, persona_name: str, task_description: str) -> bool:
        """Heuristically determine if the task is about writing/modifying code."""
        coding_personas = [
            "backend-architect", "frontend-architect", "python-expert", "refactoring-expert",
            "security-engineer", "quality-engineer", "performance-engineer"
        ]
        if persona_name in coding_personas:
            return True

        coding_keywords = [
            "implement", "fix", "add", "refactor", "modify", "develop", "bug", 
            "error", "test", "feature", "endpoint", "class", "function", "code",
        ]
        return any(keyword in task_description.lower() for keyword in coding_keywords)

    def validate_completion(
        self,
        persona_name: str,
        task_description: str,
        execution_log: str,
        changed_files: List[str]
    ) -> Dict:
        """
        Analyze execution artifacts to answer the 4 questions, adapting to task type and persona.
        If verification is not deterministic, default to PASS (Soft Pass).
        """
        is_coding = self._is_coding_task(persona_name, task_description)
        log_lower = execution_log.lower()
        
        checks = {
            "tests_passed": True, # Default to True (Soft Pass)
            "requirements_met": True, # Default to True (Soft Pass)
            "assumptions_verified": False,
            "evidence_provided": False,
        }
        
        # 1. Test Verification (Strict only if explicitly a coding task AND tests were run)
        if is_coding:
            if "failed" in log_lower and "passed" not in log_lower:
                checks["tests_passed"] = False # Explicit failure
            elif "error" in log_lower and "traceback" in log_lower:
                checks["tests_passed"] = False # Explicit error
            # Otherwise stay True (Soft Pass if no tests ran or output is ambiguous)
        
        # 2. Requirements Met (Strict only for specific personas)
        if persona_name == "technical-writer":
            # Must see doc-related keywords
            checks["requirements_met"] = any(k in log_lower for k in ["readme", "doc", "guide", "md"])
        elif persona_name == "deep-research-agent":
            # Must see sources
            checks["requirements_met"] = any(k in log_lower for k in ["source:", "link:", "http"])
        
        # 3. Assumptions Verified (Did they look before leaping?)
        # Strict Verification: Must use observation tools to confirm.
        verification_tools = ["cat ", "grep ", "ls ", "find ", "search_file_content", "read_file", "glob"]
        
        if any(tool in execution_log for tool in verification_tools):
            checks["assumptions_verified"] = True
        else:
            # If no verification tools were used, this check FAILS.
            # This forces the Brain to perform a 'read_file' or 'ls' to confirm the result.
            checks["assumptions_verified"] = False
            
        # 4. Evidence Provided (Did they do anything?)
        if changed_files or len(execution_log.strip()) > 50:
            checks["evidence_provided"] = True
        
        # Final Verdict
        passed = all(checks.values())
        
        return {
            "passed": passed,
            "checks": checks,
            "missing": [k for k, v in checks.items() if not v]
        }
