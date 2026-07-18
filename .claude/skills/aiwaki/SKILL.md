```markdown
# aiwaki Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the development patterns and coding conventions used in the `aiwaki` Python repository. It covers file naming, import/export styles, commit message patterns, and testing approaches. While no specific frameworks or automated workflows are detected, this guide provides best practices and command suggestions for working within this codebase.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `data_processor.py`, `user_utils.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import helper_function
    ```

### Export Style
- Use **named exports** (explicitly define what is exported).
  - Example:
    ```python
    __all__ = ['main_function', 'HelperClass']
    ```

### Commit Messages
- Freeform style, no strict prefixes.
- Average commit message length: ~28 characters.
  - Example: `fix bug in data loader`

## Workflows

### Adding a New Module
**Trigger:** When you need to add new functionality.
**Command:** `/add-module`

1. Create a new Python file using snake_case naming.
2. Implement your functions or classes.
3. Use relative imports to access shared utilities.
4. Define `__all__` to specify exports.
5. Add a corresponding test file (see Testing Patterns).
6. Commit your changes with a concise, descriptive message.

### Modifying Existing Code
**Trigger:** When updating or refactoring code.
**Command:** `/modify-code`

1. Locate the relevant module.
2. Make changes, following snake_case and relative import conventions.
3. Update `__all__` if exports change.
4. Update or add tests as needed.
5. Commit with a clear message summarizing the change.

### Running Tests
**Trigger:** To verify code correctness after changes.
**Command:** `/run-tests`

1. Identify test files (pattern: `*.test.*`).
2. Run tests manually or with your preferred test runner.
3. Review test results and fix any failures.

## Testing Patterns

- Test files follow the `*.test.*` naming pattern.
  - Example: `data_processor.test.py`
- Testing framework is **unknown**; adapt to your preferred tool (e.g., `pytest`, `unittest`).
- Place tests alongside or near the modules they test.
- Example test file structure:
  ```python
  import unittest
  from .data_processor import process_data

  class TestProcessData(unittest.TestCase):
      def test_basic(self):
          self.assertEqual(process_data([1, 2]), [2, 3])
  ```

## Commands
| Command        | Purpose                                      |
|----------------|----------------------------------------------|
| /add-module    | Scaffold and add a new module                |
| /modify-code   | Update or refactor existing code             |
| /run-tests     | Run all test files matching `*.test.*`       |
```