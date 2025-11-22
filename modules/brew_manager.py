import subprocess
import json
import re
import sys
import shutil
import argparse
from typing import List, Dict, Any, Tuple, Set, Optional, Union
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

# --- Configuration ---
MAX_VER_WIDTH = 25  # Prevents massive version strings from breaking layout
API_URL = "https://formulae.brew.sh/api/analytics/install/30d.json"
BETA_REGEX = r"/(@|-)(beta|alpha|nightly|insider|preview|dev|next|canary|edge)/"
BETA_MATCH_REGEX = r"^(@|-)(beta|alpha|nightly|insider|preview|dev|next|canary|edge)"

console = Console()

META = {
    "name": "Brew Manager",
    "description": "Updates, Betas, Cleanup, Search",
    "emoji": "🍺",
    "order": 1
}

def check_brew_installed() -> bool:
    """Checks if Homebrew is installed and available in PATH."""
    if not shutil.which("brew"):
        console.print(Panel(
            "[bold red]Homebrew is not installed![/]\n\n"
            "Please install it by running this command in your terminal:\n"
            "[cyan]/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"[/]",
            title="Missing Dependency",
            border_style="red"
        ))
        return False
    return True

def run_command(command: str, stream: bool = False) -> Union[str, int]:
    """
    Execute a shell command.

    Args:
        command: The command string to execute.
        stream: If True, stream output to console (returns exit code).
                If False, capture output (returns stdout string).

    Returns:
        Exit code (int) if stream=True, else stdout (str).
    """
    if stream:
        return subprocess.call(command, shell=True)
    try:
        return subprocess.check_output(command, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return ""

def clean_version(v: str) -> str:
    """Remove build numbers/suffixes from version string."""
    if not v: return ""
    return re.sub(r'[_\-]\d+$', '', v)

def truncate(text: Any, limit: int) -> str:
    """Truncate text to limit characters."""
    text = str(text)
    if len(text) > limit:
        return text[:limit-1] + "…"
    return text

def get_data() -> Tuple[Dict[str, Any], Set[str]]:
    """
    Fetch installed packages and available beta versions.

    Returns:
        Tuple of (installed_data_dict, set_of_beta_names)
    """
    with console.status("[bold green]Scanning Homebrew system..."):
        # 1. Get Installed
        raw_inst = run_command("brew info --json=v2 --installed")
        installed_data = {}
        if isinstance(raw_inst, str):
            try: 
                installed_data = json.loads(raw_inst)
            except json.JSONDecodeError: 
                console.print("[red]Error parsing installed packages JSON.[/]")
                installed_data = {}

        # 2. Get Betas
        raw_search = run_command(f"brew search '{BETA_REGEX}'")
        all_betas = set()
        if isinstance(raw_search, str):
            all_betas = set([x.strip() for x in raw_search.split('\n') if x.strip() and "==>" not in x])
        
        return installed_data, all_betas

def get_beta_metadata(beta_names: List[str]) -> Dict[str, Any]:
    """Fetch metadata for a list of beta packages."""
    if not beta_names: return {}
    cmd = f"brew info --json=v2 {' '.join(beta_names)}"
    raw = run_command(cmd)
    if not isinstance(raw, str): return {}
    
    try:
        data = json.loads(raw)
        lookup = {}
        for cat in ['formulae', 'casks']:
            for item in data.get(cat, []):
                if item.get('token'): lookup[item.get('token')] = item
                if item.get('name'): lookup[item.get('name')] = item
        return lookup
    except json.JSONDecodeError: 
        return {}

def parse_item(item: Dict[str, Any], item_type: str) -> Tuple[str, str, str, bool]:
    """Extract name, local version, latest version, and outdated status."""
    name = item.get('token') or item.get('name') or "Unknown"
    is_outdated = item.get('outdated', False)

    if item_type == 'cask':
        local = item.get('installed', "N/A")
        latest = item.get('version', "Unknown")
    else: 
        inst = item.get('installed', [])
        local = inst[0]['version'] if inst else "N/A"
        latest = item.get('versions', {}).get('stable', "Unknown")
    return name, str(local), str(latest), is_outdated

def build_rows() -> List[Dict[str, Any]]:
    """Build data rows for the main table."""
    installed_data, all_betas = get_data()
    rows = []
    betas_to_lookup = []

    for cat, type_label in [('casks', 'cask'), ('formulae', 'formula')]:
        for item in installed_data.get(cat, []):
            name, local, latest, is_outdated = parse_item(item, type_label)
            
            beta_match = None
            for b in all_betas:
                if b.startswith(name):
                    rem = b[len(name):]
                    if re.match(BETA_MATCH_REGEX, rem):
                        beta_match = b
                        betas_to_lookup.append(b)
                        break
            
            needs_update = is_outdated
            
            priority = 3
            if needs_update: priority = 1
            elif beta_match: priority = 2
            
            rows.append({
                "name": name,
                "type": type_label,
                "local": local,
                "latest": latest,
                "beta_name": beta_match if beta_match else "-",
                "beta_ver": "-",
                "priority": priority,
                "needs_update": needs_update
            })

    beta_details = get_beta_metadata(betas_to_lookup)
    for row in rows:
        if row['beta_name'] != "-":
            b_data = beta_details.get(row['beta_name'])
            if b_data:
                if 'version' in b_data: row['beta_ver'] = b_data['version']
                elif 'versions' in b_data: row['beta_ver'] = b_data['versions'].get('stable', 'Unknown')

    rows.sort(key=lambda x: (x['priority'], x['name']))
    return rows

def print_table(rows: List[Dict[str, Any]]) -> None:
    """Render the package table."""
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("App Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta", width=8)
    table.add_column("Your Ver", max_width=MAX_VER_WIDTH)
    table.add_column("Stable", max_width=MAX_VER_WIDTH)
    table.add_column("Avail Beta", style="green")
    table.add_column("Beta Ver", max_width=MAX_VER_WIDTH)

    for r in rows:
        row_style = ""
        name_style = "cyan"
        if r['needs_update']:
            row_style = "bold yellow"
            name_style = "bold yellow"
        elif r['beta_name'] == "-":
            row_style = "dim"
        
        local_ver = Text(truncate(r['local'], MAX_VER_WIDTH))
        stable_ver = Text(truncate(r['latest'], MAX_VER_WIDTH))
        beta_ver = Text(truncate(r['beta_ver'], MAX_VER_WIDTH))

        if r['needs_update']:
             local_ver.stylize("red strike")
             stable_ver.stylize("green")

        table.add_row(
            Text(r['name'], style=name_style),
            Text(r['type']),
            local_ver,
            stable_ver,
            r['beta_name'] if r['beta_name'] != "-" else "",
            beta_ver if r['beta_ver'] != "-" else "",
            style=row_style
        )
    console.print(table)
    console.print(f"[yellow]Yellow[/] = Update Available  |  [green]Green[/] = Beta Alternative Available", style="italic dim")

def get_top_packages_data(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch top installed packages from Homebrew analytics."""
    try:
        # Fetch analytics
        cmd = f"curl -s {API_URL}"
        raw_json = subprocess.check_output(cmd, shell=True, text=True)
        data = json.loads(raw_json)
        items = data.get("items", [])[:limit]
        
        if not items: return []

        # Map formula name to install count
        install_counts = {item['formula']: item['count'] for item in items}
        names = list(install_counts.keys())

        # Fetch details
        cmd_info = f"brew info --json=v2 {' '.join(names)}"
        raw_info = run_command(cmd_info)
        if not isinstance(raw_info, str): return []
        
        info_data = json.loads(raw_info)
        
        results = []
        # Process formulae
        for f in info_data.get("formulae", []):
            name = f.get("name")
            desc = f.get("desc", "No description")
            count = install_counts.get(name, 0)
            results.append({"name": name, "desc": desc, "count": count})
        
        # Sort by count desc (since brew info might reorder)
        results.sort(key=lambda x: int(str(x["count"]).replace(",","")), reverse=True)
        return results

    except Exception as e:
        console.print(f"[red]Error fetching top packages: {e}[/]")
        return []

def display_top_packages(data: List[Dict[str, Any]]) -> None:
    """Display top packages table."""
    if not data: return

    table = Table(box=box.SIMPLE, expand=True, show_header=True)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Name", style="bold cyan", width=20)
    table.add_column("Description", style="white")
    table.add_column("Installs", style="green", justify="right")

    for idx, item in enumerate(data, 1):
        desc = truncate(item['desc'], 50) # Ensure it fits
        table.add_row(str(idx), item['name'], desc, f"{int(str(item['count']).replace(',','')):,}")
    
    console.print(table)
    console.print("")

def search_packages() -> None:
    """Search menu: Search by name or browse top packages."""
    while True:
        console.clear()
        console.rule("[bold cyan]Find Packages[/]")
        console.print("[1] Search by Name")
        console.print("[2] Browse Top Packages (30d Analytics)")
        console.print("[Enter] Back")
        
        choice = Prompt.ask("Select Option", choices=["1", "2", "3"], default="3", show_default=False)
        
        if choice == "1":
            do_search_by_name()
        elif choice == "2":
            do_browse_top()
        else:
            break

def do_search_by_name() -> None:
    """Execute search by name."""
    console.rule("[bold cyan]Search Homebrew[/]")
    query = Prompt.ask("Enter search term")
    if not query: return

    with console.status(f"Searching for '{query}'..."):
        result = run_command(f"brew search '{query}'")
    
    if not result or not isinstance(result, str):
        console.print("[yellow]No results found.[/]")
        Prompt.ask("Press Enter to continue...")
        return

    # Parse results: split by whitespace to handle multi-column output
    tokens = result.split()
    clean_list = [t for t in tokens if t not in ["==>", "Formulae", "Casks"]]
    
    if not clean_list:
        console.print("[yellow]No results found.[/]")
        Prompt.ask("Press Enter to continue...")
        return

    # Display with numbers
    table = Table(title=f"Search Results for '{query}'", expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Package", style="cyan")
    
    for idx, name in enumerate(clean_list, 1):
        table.add_row(str(idx), name)
    
    console.print(table)
    
    choice = Prompt.ask("Enter number to see info (or Enter to go back)")
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(clean_list):
            show_package_info(clean_list[idx])

def do_browse_top() -> None:
    """Execute browse top packages."""
    console.rule("[bold cyan]Top Homebrew Packages (30 Days)[/]")
    
    with console.status("Fetching analytics data..."):
        data = get_top_packages_data(20)

    if not data:
        Prompt.ask("Press Enter to continue...")
        return

    table = Table(expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Package", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Installs", style="green", justify="right")
    
    # Map for quick lookup
    rank_map = {}

    for idx, item in enumerate(data, 1):
        name = item['name']
        desc = truncate(item['desc'], 60)
        count = item['count']
        
        rank_map[str(idx)] = name
        table.add_row(str(idx), name, desc, f"{int(str(count).replace(',','')):,}")
        
    console.print(table)
    
    choice = Prompt.ask("Enter number (Rank) to see info (or Enter to go back)")
    if choice in rank_map:
        show_package_info(rank_map[choice])
    elif choice:
        console.print("[red]Invalid selection.[/]")
        Prompt.ask("Press Enter...")

def show_package_info(package_name: Optional[str] = None) -> None:
    """Show info for a specific package."""
    if not package_name:
        package_name = Prompt.ask("Enter package name to look up")
    
    if not package_name: return

    console.rule(f"[bold cyan]Info: {package_name}[/]")
    with console.status(f"Fetching info for {package_name}..."):
        # Try json first for structured data
        raw_json = run_command(f"brew info --json=v2 {package_name}")
        
        try:
            if isinstance(raw_json, str):
                data = json.loads(raw_json)
                found = False
                
                # Handle Formulae
                for f in data.get("formulae", []):
                    found = True
                    console.print(Panel(
                        f"[bold]Name:[/] {f['name']}\n"
                        f"[bold]Desc:[/] {f['desc']}\n"
                        f"[bold]Homepage:[/] {f['homepage']}\n"
                        f"[bold]Version:[/] {f['versions']['stable']}\n"
                        f"[bold]Installed:[/] {[i['version'] for i in f['installed']] if f['installed'] else 'No'}\n"
                        f"[bold]License:[/] {f['license']}",
                        title=f"Formula: {f['name']}",
                        border_style="green"
                    ))

                # Handle Casks
                for c in data.get("casks", []):
                    found = True
                    console.print(Panel(
                        f"[bold]Name:[/] {c['token']}\n"
                        f"[bold]Desc:[/] {c['desc']}\n"
                        f"[bold]Homepage:[/] {c['homepage']}\n"
                        f"[bold]Version:[/] {c['version']}\n"
                        f"[bold]Installed:[/] {c.get('installed', 'No')}",
                        title=f"Cask: {c['token']}",
                        border_style="magenta"
                    ))
                
                if not found:
                    # Fallback to text output if JSON was empty but command didn't fail (rare)
                    console.print(run_command(f"brew info {package_name}"))
            else:
                console.print("[red]Failed to fetch info.[/]")

        except json.JSONDecodeError:
            # Fallback to raw text if JSON fails
            console.print(run_command(f"brew info {package_name}"))

    Prompt.ask("\nPress Enter to continue...")

# --- AUTO PILOT LOGIC ---

def audit_and_update() -> None:
    """Run the main audit and update workflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print command but do not run")
    # We need to handle args manually since we are in a module
    args, unknown = parser.parse_known_args()

    # 1. Show the View
    rows = build_rows()
    print_table(rows)
    print("\n")

    # 2. Analyze
    outdated_count = len([r for r in rows if r['needs_update']])
    potential_swaps = [r for r in rows if r['beta_name'] != "-"]
    
    # 3. Construct Command Chain
    chain = ["brew update"] # Always start with fresh definitions
    
    # -- Step A: Updates --
    if outdated_count > 0:
        if Confirm.ask(f"[bold yellow]Included upgrades for {outdated_count} outdated apps?[/]"):
            chain.append("brew upgrade --greedy")
    else:
        console.print("[dim]System is up to date.[/]")

    # -- Step B: Swaps --
    if potential_swaps:
        console.print(f"\n[bold green]Found {len(potential_swaps)} possible beta swaps.[/]")
        console.print("[dim]Type names to swap (space separated), 'all', or 'no'[/]")
        choice = Prompt.ask("Selection", default="no")
        
        swaps_to_do = []
        if choice.lower() == 'all':
            swaps_to_do = potential_swaps
        elif choice.lower() not in ['no', 'none', 'n']:
            targets = choice.split()
            swaps_to_do = [x for x in potential_swaps if x['name'] in targets or x['beta_name'] in targets]
        
        if swaps_to_do:
            remove_list = [x['name'] for x in swaps_to_do]
            install_list = [x['beta_name'] for x in swaps_to_do]
            
            # Use --force on uninstall to prevent "Directory not empty" errors
            chain.append(f"brew uninstall --force {' '.join(remove_list)}")
            chain.append(f"brew install --cask {' '.join(install_list)}")
    
    # -- Step C: Cleanup --
    chain.append("brew cleanup -s")
    chain.append("brew doctor")

    # 4. Execute
    full_cmd = " && ".join(chain)
    
    console.print("\n[bold white on blue] Final Command to Run: [/]")
    console.print(f"[cyan]{full_cmd}[/]\n")

    if args.dry_run:
        console.print("[yellow][Dry Run] Exiting.[/]")
    else:
        if Confirm.ask("Run this now?"):
            console.print("\n[green]🚀 Executing...[/]")
            run_command(full_cmd, stream=True)
        else:
            console.print("[red]Aborted.[/]")
    
    Prompt.ask("\nPress Enter to return to menu...")

def main() -> None:
    """Main entry point."""
    if not check_brew_installed():
        Prompt.ask("Press Enter to return...")
        return

    # Fetch top packages once on load
    top_data = []
    with console.status("Loading Brew Manager..."):
        top_data = get_top_packages_data(10)

    while True:
        console.clear()
        console.rule("[bold magenta]Brew Manager[/]")
        
        # Display dashboard
        if top_data:
            display_top_packages(top_data)

        console.print("\n[1] [bold cyan]Audit & Update[/] (Check for updates, betas)")
        console.print("[2] [bold green]Search Packages[/] (Find new apps)")
        console.print("[3] [bold yellow]Package Info[/] (Details & Dependencies)")
        console.print("[Enter] Return to Main Menu")
        
        choice = Prompt.ask("Select Option", choices=["1", "2", "3", "4"], default="4", show_default=False)
        
        if choice == "1":
            audit_and_update()
        elif choice == "2":
            search_packages()
        elif choice == "3":
            show_package_info()
        elif choice == "4":
            break

run = main

if __name__ == "__main__":
    main()
