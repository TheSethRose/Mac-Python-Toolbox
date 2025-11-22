import sys
import importlib.util
from pathlib import Path
from typing import List, Any
from types import ModuleType
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

MODULES_DIR = Path(__file__).parent / "modules"
APP_TITLE = "[bold white]Mac Python Toolbox[/]"
APP_SUBTITLE = "[dim]v2.0 - Modular Ecosystem[/]"

def load_modules() -> List[ModuleType]:
    """
    Dynamically loads modules from the modules directory.
    
    Returns:
        A list of loaded module objects, sorted by their 'order' metadata.
    """
    modules = []
    if not MODULES_DIR.exists():
        console.print(f"[red]Modules directory not found: {MODULES_DIR}[/]")
        return modules
    
    for file_path in MODULES_DIR.glob("*.py"):
        if file_path.name == "__init__.py":
            continue
        
        try:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[file_path.stem] = module
                spec.loader.exec_module(module)
                
                if hasattr(module, "META") and hasattr(module, "run"):
                    modules.append(module)
        except (ImportError, SyntaxError) as e:
             console.print(f"[red]Error loading {file_path.name}: {e}[/]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load {file_path.name}: {e}[/]")
    
    # Sort by order in META, default to 99 if not specified
    modules.sort(key=lambda m: getattr(m, "META", {}).get("order", 99))
    return modules

def main_menu() -> None:
    """Displays the main menu and handles user input."""
    modules = load_modules()
    
    while True:
        console.clear()
        
        # Title Block
        console.print(Panel.fit(
            f"{APP_TITLE}\n{APP_SUBTITLE}", 
            border_style="blue"
        ))

        if not modules:
            console.print("[red]No modules loaded![/]")
            console.print(f"[dim]Checked: {MODULES_DIR}[/]")
            break

        console.print("\n[bold white on blue] AVAILABLE TOOLS [/]")
        
        choices = []
        for idx, module in enumerate(modules, 1):
            meta = getattr(module, "META", {})
            name = meta.get("name", module.__name__)
            desc = meta.get("description", "")
            emoji = meta.get("emoji", "🔧")
            
            console.print(f"[{idx}] {emoji} [bold cyan]{name}[/] ({desc})")
            choices.append(str(idx))
        
        choices.append("q")
        console.print("\n[Q] Quit")
        
        choice = Prompt.ask("Select Option", choices=choices, default="q", show_default=False)

        if choice.lower() == "q":
            console.print("[green]Goodbye![/]")
            break
        
        # Execute module
        try:
            selected_idx = int(choice) - 1
            if 0 <= selected_idx < len(modules):
                module = modules[selected_idx]
                try:
                    # Run the module
                    module.run()
                except KeyboardInterrupt:
                    console.print("\n[yellow]Module interrupted.[/]")
                except Exception as e:
                    console.print(f"[red]Error running module: {e}[/]")
                    Prompt.ask("Press Enter to continue...")
        except ValueError:
            pass

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[green]Goodbye![/]")
