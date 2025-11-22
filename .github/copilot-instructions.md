# Mac Python Toolbox - Copilot Instructions

## Architecture & Module System
- **Core Structure**: `main.py` is the entry point that dynamically discovers and loads tools from the `modules/` directory.
- **Module Contract**: Every tool file in `modules/` MUST define:
  1. `META` dictionary: `{"name": str, "description": str, "emoji": str, "order": int}`.
  2. `run()` function: The primary entry point for the tool logic.
  3. `if __name__ == "__main__": run()` block to allow standalone execution and testing.
- **Isolation**: Modules should be self-contained. Imports should be local to the module where possible.

## UI/UX Standards (Rich)
- **Library**: Use `rich` for ALL terminal output. Avoid standard `print()`.
- **Consistency**:
  - Start `run()` with `console.clear()` and `console.rule("[bold color]Title[/]")`.
  - Use `rich.panel.Panel` for important summaries or alerts.
  - Use `rich.table.Table(expand=True)` for tabular data.
- **Interaction**: Use `rich.prompt.Prompt` for text input and `rich.prompt.Confirm` for yes/no questions.
- **Feedback**: Use `with console.status("Message..."):` for blocking operations (scans, network calls).

## System Interactions
- **Execution**: Use `subprocess.check_output` to capture text (decode with `text=True`) and `subprocess.run` for interactive/fire-and-forget commands.
- **Validation**: Always check for the existence of external CLIs (e.g., `brew`, `tmutil`) using `shutil.which()` before execution. Provide a helpful error message if missing.
- **Error Handling**: Wrap system calls in `try/except` blocks to handle `subprocess.CalledProcessError` or `PermissionError`.

## Development Workflow
- **New Tools**: To add a feature, simply create a new `.py` file in `modules/` following the Module Contract. No changes to `main.py` are required.
- **Testing**: Test modules individually by running them directly: `python3 modules/my_new_tool.py`.
