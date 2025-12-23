import os
import glob
from typing import List, Dict, Tuple, Any

# --- Legacy Validation Functions (Restored) ---

def validate_mission_schema(config: Dict[str, Any]):
    """
    Validates the mission.yaml configuration.
    Raises ValueError if required fields are missing or invalid.
    """
    if not isinstance(config, dict):
        raise ValueError("Mission configuration must be a dictionary.")
    
    # Required fields
    required_fields = ["goal"] # 'mission_name' might be optional or have default
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Mission configuration missing required field: '{field}'")
            
    # 'goal' can be string or list of strings/dicts
    goal = config.get("goal")
    if not (isinstance(goal, str) or isinstance(goal, list)):
         raise ValueError("Mission 'goal' must be a string or a list of tasks.")

    if isinstance(goal, list):
        if not all(isinstance(item, (str, dict)) for item in goal):
             raise ValueError("Mission 'goal' list items must be strings or task dictionaries.")

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
        Assess confidence level (0.0 - 1.0) based on project state.
        
        Returns:
            Dict containing score, checks passed, and recommendations.
        """
        checks = []
        score = 0.0
        
        # Check 1: Documentation Readiness (30%)
        # Does the project have basic documentation?
        has_docs = self._check_documentation()
        if has_docs:
            score += 0.3
            checks.append("✅ Documentation found (README/docs)")
        else:
            checks.append("❌ Missing documentation (running blind?)")

        # Check 2: Duplication Risk (30%)
        # Does this look like something that might already exist?
        # (This is a heuristic check)
        potential_duplication = self._check_potential_duplication(task_description)
        if not potential_duplication:
            score += 0.3
            checks.append("✅ No obvious duplication detected")
        else:
            checks.append(f"⚠️ Potential duplication detected in: {potential_duplication}")
            score += 0.1  # Partial points only

        # Check 3: Task Clarity (40%)
        # Is the task description detailed enough?
        is_clear = len(task_description.split()) > 5
        if is_clear:
            score += 0.4
            checks.append("✅ Task description seems detailed")
        else:
            checks.append("❌ Task description too vague")

        # Determine action based on score
        if score >= 0.7:
            status = "GREEN"
            action = "Proceed with execution."
        elif score >= 0.4:
            status = "YELLOW"
            action = "Proceed with caution. Consider 'Deep Research' first."
        else:
            status = "RED"
            action = "STOP. Request clarification or run exploratory research."

        return {
            "score": round(score, 2),
            "status": status,
            "action": action,
            "checks": checks
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
        """
        is_coding = self._is_coding_task(persona_name, task_description)
        
        checks = {
            "tests_passed": not is_coding,
            "requirements_met": False,
            "assumptions_verified": False,
            "evidence_provided": False,
        }
        
        # 1. Test Verification (only for coding tasks)
        if is_coding:
            if "passed" in execution_log.lower() and "failed" not in execution_log.lower():
                checks["tests_passed"] = True
            elif "OK" in execution_log: # For pytest
                checks["tests_passed"] = True
            elif changed_files and "no tests ran" in execution_log.lower():
                checks["tests_passed"] = True # Pass if code changed but no tests exist
            else:
                checks["tests_passed"] = False
        
        # 2. Requirements Met (Persona-based check)
        log_lower = execution_log.lower()
        if persona_name == "technical-writer" and any(k in log_lower for k in ["readme", "doc", "guide"]):
            checks["requirements_met"] = True
        elif persona_name == "refactoring-expert" and any(k in log_lower for k in ["refactor", "simplify", "improve"]):
            checks["requirements_met"] = True
        elif persona_name == "deep-research-agent" and any(k in log_lower for k in ["source:", "link:", "http"]):
            checks["requirements_met"] = True
        elif is_coding and "implemented" in log_lower or "fixed" in log_lower:
            checks["requirements_met"] = True
        elif not is_coding and len(log_lower) > 100: # For generic non-coding tasks, assume long output is good.
             checks["requirements_met"] = True

        # 3. Assumptions Verified
        if any(cmd in execution_log for cmd in ["cat ", "grep ", "ls ", "find ", "search_file_content"]):
            checks["assumptions_verified"] = True
            
        # 4. Evidence Provided
        if changed_files or len(execution_log.strip()) > 50:
            checks["evidence_provided"] = True
        
        # Final Verdict
        passed = all(checks.values())
        
        return {
            "passed": passed,
            "checks": checks,
            "missing": [k for k, v in checks.items() if not v]
        }