# Code Style and Conventions

## General Python Style
- **Encoding**: UTF-8 for all files
- **Language**: Korean comments and docstrings are used alongside English
- **Type Hints**: Not consistently used (legacy code)

## Naming Conventions
- **Classes**: PascalCase (e.g., `Brain`, `NightShiftAgent`)
- **Methods/Functions**: snake_case (e.g., `_load_settings`, `clean_ansi`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_CONTEXT_CHARS`, `LOG_DIR`)
- **Private Methods**: Prefixed with underscore (e.g., `_setup_client`)
- **Variables**: snake_case

## Recent Refactoring Improvements
The code shows evidence of recent refactoring focused on readability:
- Variable names improved from single letters to descriptive names (e.g., `f` → `file`, `resp` → `response`, `conf` → `config`)
- Magic numbers replaced with named constants (e.g., `MAX_CONTEXT_CHARS`, `MAX_HISTORY_CHARS`)
- Comments added explaining refactoring decisions

## Docstrings
- Classes have brief docstrings in English or Korean
- Some methods have docstrings in Korean (e.g., "설정 파일을 로드합니다.")
- Not all methods have docstrings

## Error Handling
- Basic try-except blocks used for LLM API calls
- File operations check for existence before proceeding
- Some error messages in English, some in Korean (with emoji prefixes)

## Code Organization
- Constants defined at module level
- Classes group related functionality
- Private methods prefixed with underscore
