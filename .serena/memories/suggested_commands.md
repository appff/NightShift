# Suggested Commands for Night Shift Development

## Running the Application
```bash
# Run Night Shift with default mission.yaml
python3 night_shift.py

# The script reads mission.yaml and settings.yaml automatically
```

## Installation and Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure settings
cp settings.sample.yaml settings.yaml
# Then edit settings.yaml to add API keys
```

## Configuration Files
- `settings.yaml`: Configure LLM provider (gemini/gpt/claude) and API keys
- `mission.yaml`: Define mission goals and constraints

## Testing
**Note**: No automated tests are currently present in the project.
To verify code works after changes:
1. Run the application with a simple mission
2. Check logs in `logs/` directory
3. Verify the conversation history is saved correctly

## macOS-Specific Commands (Darwin)
Since this project runs on macOS (Darwin):
```bash
# List files
ls -la

# Find Python files
find . -name "*.py" -type f

# Search in files (case-insensitive)
grep -i "pattern" file.py

# View file contents
cat file.py

# Check Python version
python3 --version
```

## Git Commands
```bash
# Check status
git status

# View changes
git diff

# Commit changes
git add .
git commit -m "message"
```

## Logging
- Logs are saved to `logs/session_{timestamp}.log`
- Full conversation history is saved automatically
- Check logs to debug issues with Brain decisions or Claude Code execution
