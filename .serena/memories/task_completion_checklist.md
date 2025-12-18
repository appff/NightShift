# Task Completion Checklist

When completing a coding task in Night Shift, follow these steps:

## 1. Code Quality Checks
- [ ] Ensure variable names are descriptive (avoid single-letter names)
- [ ] Replace magic numbers with named constants
- [ ] Add comments explaining refactoring decisions
- [ ] Follow existing naming conventions (snake_case for functions/variables)
- [ ] Ensure docstrings are present for classes and complex methods

## 2. Functional Verification
- [ ] Test the code manually by running `python3 night_shift.py`
- [ ] Verify no syntax errors or import issues
- [ ] Check that configuration files (settings.yaml, mission.yaml) are read correctly
- [ ] Verify logs are generated in `logs/` directory

## 3. Code Review
- [ ] Check for overly long functions (consider breaking into smaller functions)
- [ ] Ensure error handling is present for external API calls
- [ ] Verify file paths are handled correctly (especially on macOS)
- [ ] Check that emoji-prefixed messages are consistent with project style

## 4. Documentation
- [ ] Update README.md if functionality changes
- [ ] Add inline comments for complex logic
- [ ] Update memory files if project structure changes

## 5. Git Workflow
- [ ] Review changes with `git diff`
- [ ] Stage relevant files with `git add`
- [ ] Commit with descriptive message
- [ ] **Note**: No automated linting/formatting tools are configured

## Known Limitations
- No unit tests exist yet
- No automated code formatting (e.g., black, autopep8)
- No linting tools configured (e.g., pylint, flake8)
- Manual testing is required for verification
