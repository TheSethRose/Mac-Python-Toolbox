import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

META = {
    "name": "Find Large Files",
    "description": ">1GB scanner",
    "emoji": "🐘",
    "order": 5
}

DEFAULT_SIZE_THRESHOLD = "1G"
DEFAULT_LIMIT = 20

def run() -> None:
    """
    Finds files larger than 1GB in Home Directory.
    
    Executes a shell command to find, sort, and display large files.
    """
    console.clear()
    console.rule("[bold red]Large File Hunter (>1GB)[/]")
    console.print("[dim]Scanning home directory... (This uses 'find', may take a moment)[/]")
    
    # Using system 'find' is faster than python recursion for this
    cmd = f"find ~ -type f -size +{DEFAULT_SIZE_THRESHOLD} -not -path '*/.*' -print0 | xargs -0 ls -lhS | head -n {DEFAULT_LIMIT}"
    
    try:
        # We run this via shell to utilize xargs/ls sorting
        result = subprocess.check_output(cmd, shell=True, text=True)
        
        if not result:
            console.print(f"[green]No files larger than {DEFAULT_SIZE_THRESHOLD} found![/]")
        else:
            console.print(Panel(result, title="Largest Files", border_style="red"))
            console.print("[yellow]Tip: To delete, use 'rm <path>' in terminal or open directory.[/]")
            
    except subprocess.CalledProcessError:
        console.print("[red]Error scanning files (permissions?).[/]")

    Prompt.ask("\n[bold]Press Enter to return to menu...[/]")

if __name__ == "__main__":
    run()
