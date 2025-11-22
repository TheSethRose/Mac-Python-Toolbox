import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()

META = {
    "name": "Audit Startup Items",
    "description": "LaunchAgents",
    "emoji": "🚀",
    "order": 4
}

def run():
    """Lists User LaunchAgents (Apps that start at login)."""
    console.clear()
    console.rule("[bold magenta]Startup & Launch Agent Auditor[/]")
    
    paths = [
        ("~/Library/LaunchAgents", "User Agents (Run at login)"),
        ("/Library/LaunchAgents", "System Agents (Run at boot)"),
    ]
    
    table = Table(expand=True)
    table.add_column("File Name", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("Status", style="green")

    found_count = 0

    for path_str, label in paths:
        p = Path(path_str).expanduser()
        if p.exists():
            for item in p.iterdir():
                if item.suffix == ".plist":
                    # Basic check if enabled isn't trivial without launchctl parsing, 
                    # so we list existence.
                    table.add_row(item.name, label, "Installed")
                    found_count += 1

    console.print(table)
    console.print(f"\n[dim]Found {found_count} launch agents. To remove, delete the .plist file from the folder.[/]")
    
    if Confirm.ask("\nOpen User LaunchAgents folder in Finder?"):
        subprocess.run(["open", os.path.expanduser("~/Library/LaunchAgents")])
    
    Prompt.ask("\n[bold]Press Enter to return to menu...[/]")

if __name__ == "__main__":
    run()
