import os
import shutil
import subprocess
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.panel import Panel

console = Console()
CONFIG_FILE = Path("cleaner_config.json")

META = {
    "name": "System Cleaner",
    "description": "Junk, Logs, Trash",
    "emoji": "🧹",
    "order": 2
}

# --- CONFIGURATION MANAGEMENT ---

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(key, value):
    config = load_config()
    config[key] = value
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    console.print(f"[dim]Saved preference '{key}: {value}' to {CONFIG_FILE}[/]")

# --- SCAN LOCATIONS ---
SCAN_LOCATIONS = [
    ("User Caches", "~/Library/Caches", "App temporary files (Safe to delete)"),
    ("User Logs", "~/Library/Logs", "Debug logs (Safe to delete)"),
    ("Xcode DerivedData", "~/Library/Developer/Xcode/DerivedData", "Build artifacts"),
    ("User Trash", "~/.Trash", "Items in your Dock Trash"),
    ("Mail Downloads", "~/Library/Containers/com.apple.mail/Data/Library/Mail Downloads", "Mail attachments"),
    ("Message Attachments", "~/Library/Messages/Attachments", "Old iMessage images/videos"),
    ("Slack Cache", "~/Library/Containers/com.tinyspeck.slackmacgap/Data/Library/Application Support/Slack/Cache", "Slack Temp Data"),
    ("Discord Cache", "~/Library/Application Support/discord/Cache", "Discord Temp Data")
]

# --- HELPER FUNCTIONS ---

def get_directory_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_directory_size(entry.path)
    except (PermissionError, OSError):
        pass
    return total

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def scan_top_offenders(base_path_str, top_n=5):
    base_path = Path(base_path_str).expanduser()
    if not base_path.exists():
        return [], 0

    items = []
    total_dir_size = 0
    
    try:
        total_dir_size = get_directory_size(base_path)
        with os.scandir(base_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        size = get_directory_size(entry.path)
                        if size > 5_000_000: # 5MB threshold
                            items.append((entry.name, size, entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        if size > 5_000_000:
                            items.append((entry.name, size, entry.path))
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        return [], 0

    items.sort(key=lambda x: x[1], reverse=True)
    return items[:top_n], total_dir_size

# --- MAINTENANCE FUNCTIONS ---

def run_spotlight_reindex():
    console.print("[dim]Running: sudo mdutil -E /[/]")
    console.print("[yellow]Note: Search will be slow for ~30 mins while it rebuilds.[/]")
    try:
        subprocess.run("sudo mdutil -E /", shell=True)
        console.print("[green]✓ Indexing restarted.[/]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")

def flush_dns():
    console.print("[dim]Running: sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder[/]")
    subprocess.run("sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder", shell=True)
    console.print("[green]✓ DNS Cache Flushed.[/]")

def thin_local_snapshots():
    """Deletes old local snapshots but KEEPS the last N versions."""
    console.print("[dim]Scanning for local snapshots (tmutil listlocalsnapshots /)...[/]")
    
    try:
        result = subprocess.check_output("tmutil listlocalsnapshots /", shell=True, text=True)
    except subprocess.CalledProcessError:
        console.print("[red]Error listing snapshots.[/]")
        return
    
    # Parse snapshots. Output lines look like: com.apple.TimeMachine.2023-11-01-120000.local
    snapshots = [line.strip() for line in result.split('\n') if "com.apple.TimeMachine" in line]
    
    if not snapshots:
        console.print("[green]No local snapshots found.[/]")
        return

    # Sort strictly by the date string inside the name
    # We use regex to find the YYYY-MM-DD-HHMMSS pattern
    import re
    date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}")
    
    # Filter out lines that don't match the pattern just in case
    valid_snapshots = []
    for s in snapshots:
        match = date_pattern.search(s)
        if match:
            valid_snapshots.append((s, match.group(0)))
    
    valid_snapshots.sort(key=lambda x: x[1]) # Sort by date string
    
    console.print(f"[bold yellow]Found {len(valid_snapshots)} local snapshots.[/]")

    # --- CONFIG CHECK ---
    config = load_config()
    keep_count = config.get("snapshots_to_keep")

    if keep_count is None:
        console.print("\n[bold]Snapshot Retention Policy[/]")
        console.print("How many recent snapshots should we KEEP? (Safety net)")
        keep_count = IntPrompt.ask("Number to keep", default=2)
        save_config("snapshots_to_keep", keep_count)
    else:
        console.print(f"[dim]Using config: Keeping last {keep_count} snapshots.[/]")

    # Determine deletion list
    if keep_count >= len(valid_snapshots):
        console.print(f"[green]You only have {len(valid_snapshots)} snapshots, which is <= your keep limit ({keep_count}). Nothing to delete.[/]")
        return

    # We delete everything BEFORE the last N
    # valid_snapshots is a list of tuples: (full_name, date_string)
    to_delete = valid_snapshots[:-keep_count]
    
    console.print(f"\n[bold red]Ready to delete {len(to_delete)} old snapshots:[/]")
    for full_name, date_str in to_delete:
        console.print(f"[dim] - {full_name}[/]")
    console.print(f"[green]Keeping the {keep_count} most recent.[/]")

    if Confirm.ask("Proceed with deletion?"):
        for full_name, date_str in to_delete:
            console.print(f"[dim]Deleting {date_str}...[/]")
            # Pass ONLY the date string to tmutil
            subprocess.run(f"tmutil deletelocalsnapshots {date_str}", shell=True)
        console.print("[green]✓ Old snapshots cleaned.[/]")

def maintenance_menu():
    while True:
        console.print("\n[bold white on blue] Maintenance Tools [/]")
        console.print("[1] Free Up RAM (sudo purge)")
        console.print("[2] Flush DNS Cache")
        console.print("[3] Reindex Spotlight")
        console.print("[4] Thin Local Snapshots (Smart)")
        console.print("[Enter] Return to Main Menu")
        
        choice = Prompt.ask("Select Tool", choices=["1", "2", "3", "4", "5"], default="5", show_default=False)
        
        if choice == "1": subprocess.run("sudo purge", shell=True)
        elif choice == "2": flush_dns()
        elif choice == "3": run_spotlight_reindex()
        elif choice == "4": thin_local_snapshots()
        elif choice == "5": break

def file_scan_mode():
    console.clear()
    all_findings = {}
    grand_total = 0

    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), BarColumn(), console=console) as progress:
        task = progress.add_task("Scanning...", total=len(SCAN_LOCATIONS))
        for name, path, desc in SCAN_LOCATIONS:
            progress.update(task, description=f"Scanning {name}...")
            top_items, total_size = scan_top_offenders(path)
            if total_size > 0:
                all_findings[name] = {"path": path, "total_size": total_size, "items": top_items, "desc": desc}
                grand_total += total_size
            progress.advance(task)

    tree = Tree(f"🔍 [bold]Junk Scan Results[/] (Total: [bold red]{format_bytes(grand_total)}[/])")
    cleanup_queue = []
    
    for category, data in all_findings.items():
        cat_branch = tree.add(f"[bold cyan]{category}[/] - [bold yellow]{format_bytes(data['total_size'])}[/]")
        if data['items']:
            for n, s, p in data['items']:
                cat_branch.add(f"[white]{n}[/] - [red]{format_bytes(s)}[/]")
                cleanup_queue.append((n, p, s))

    console.print("\n")
    console.print(tree)
    console.print("\n")

    if grand_total == 0:
        console.print("[green]System Clean![/]")
        return

    if Confirm.ask("[bold]Do you want to review and delete these files?[/]"):
        for name, path, size in cleanup_queue:
            console.print(f"\nItem: [cyan]{name}[/] ({format_bytes(size)})")
            console.print(f"Path: [dim]{path}[/]")
            if Confirm.ask("Delete this item?"):
                try:
                    p = Path(path)
                    if p.is_dir(): shutil.rmtree(p)
                    else: p.unlink()
                    console.print("[green]Deleted[/]")
                except Exception as e:
                    console.print(f"[red]Error: {e}[/]")

def main():
    console.rule("[bold red]Mac Cleaner Pro[/]")
    while True:
        console.print("\n[1] [bold cyan]Scan for Junk[/] (Caches, Logs, Trash)")
        console.print("[2] [bold magenta]Maintenance Tools[/]")
        console.print("[Enter] Exit")
        
        choice = Prompt.ask("Choose Option", choices=["1", "2", "3"], default="3", show_default=False)
        
        if choice == "1": file_scan_mode()
        elif choice == "2": maintenance_menu()
        elif choice == "3": 
            console.print("[green]Bye![/]")
            break

run = main

if __name__ == "__main__":
    main()