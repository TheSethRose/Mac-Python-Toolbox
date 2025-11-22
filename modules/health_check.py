import subprocess
import json
import shutil
import sys
import os
from typing import Dict, Any, Optional, Union
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

META = {
    "name": "Health Doctor",
    "description": "Network, Disk, Battery",
    "emoji": "❤️ ",
    "order": 3
}

def run_command(cmd: str, return_json: bool = False) -> Union[str, Dict[str, Any], None]:
    """
    Execute a shell command and return the output.

    Args:
        cmd: The command to execute.
        return_json: Whether to parse the output as JSON.

    Returns:
        The output string, a dictionary if parsed as JSON, or None on failure.
    """
    try:
        output = subprocess.check_output(cmd, shell=True, text=True).strip()
        if return_json:
            # Sometimes apple tools output extra text before JSON, locate the first {
            idx = output.find('{')
            if idx != -1:
                return json.loads(output[idx:])
            return {}
        return output
    except subprocess.CalledProcessError:
        return None
    except json.JSONDecodeError:
        return None
    except Exception:
        return None

# --- DIAGNOSTIC MODULES ---

def get_system_vitals() -> Dict[str, Any]:
    """Fetches hardware info, uptime, and battery health."""
    vitals = {}
    
    # 1. Uptime
    if shutil.which("uptime"):
        uptime = run_command("uptime | cut -d ',' -f1")
        if isinstance(uptime, str):
            vitals['uptime'] = uptime.strip()
    
    # 2. Hardware Info
    if shutil.which("system_profiler"):
        hw_data = run_command("system_profiler SPHardwareDataType -json", return_json=True)
        if isinstance(hw_data, dict) and 'SPHardwareDataType' in hw_data:
            info = hw_data['SPHardwareDataType'][0]
            vitals['model'] = info.get('machine_model')
            vitals['chip'] = info.get('chip_type')
            vitals['mem'] = info.get('physical_memory')

        # 3. Battery Info (if laptop)
        pwr_data = run_command("system_profiler SPPowerDataType -json", return_json=True)
        if isinstance(pwr_data, dict) and 'SPPowerDataType' in pwr_data:
            try:
                batt = pwr_data['SPPowerDataType'][0]['sppower_battery_charge_info']
                health_info = pwr_data['SPPowerDataType'][0]['sppower_battery_health_info']
                
                vitals['battery_cycle'] = health_info.get('sppower_battery_cycle_count')
                vitals['battery_cond'] = health_info.get('sppower_battery_health')
                vitals['battery_max'] = batt.get('sppower_battery_max_capacity')
                vitals['is_laptop'] = True
            except (KeyError, IndexError):
                vitals['is_laptop'] = False
        else:
             vitals['is_laptop'] = False
    
    return vitals

def run_network_test() -> None:
    """Runs macOS native networkQuality tool."""
    if not shutil.which("networkQuality"):
        console.print("[red]Error: networkQuality tool not found (Requires macOS Monterey+).[/]")
        return

    console.print("\n[bold cyan]Running Network Quality Test...[/]")
    console.print("[dim]This tests upload/download capacity and responsiveness (RPM).[/]")
    
    # networkQuality -c produces JSON output
    try:
        with console.status("[bold green]Testing connection (approx 15s)..."):
            data = run_command("networkQuality -c", return_json=True)
        
        if not data or not isinstance(data, dict):
            console.print("[red]Network test failed.[/]")
            return

        # Parse Results
        dl = float(data.get("dl_throughput", 0)) / 1000000 # bps to Mbps
        ul = float(data.get("ul_throughput", 0)) / 1000000
        rpm = data.get("responsiveness", 0)
        
        table = Table(title="Network Quality Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold green")
        
        table.add_row("Download Speed", f"{dl:.2f} Mbps")
        table.add_row("Upload Speed", f"{ul:.2f} Mbps")
        table.add_row("Responsiveness", f"{rpm} RPM (Round-trips per min)")
        
        console.print(table)
        
        if isinstance(rpm, (int, float)) and rpm < 100:
            console.print("[yellow]Note: Low RPM indicates lag during video calls.[/]")
            
    except Exception as e:
        console.print(f"[red]Error running networkQuality: {e}[/]")

def check_software_updates() -> None:
    """Checks for macOS system updates via CLI."""
    if not shutil.which("softwareupdate"):
        console.print("[red]Error: softwareupdate tool not found.[/]")
        return

    console.print("\n[bold cyan]Checking for macOS Updates...[/]")
    with console.status("[dim]Contacting Apple Update Servers..."):
        result = run_command("softwareupdate -l")
    
    if isinstance(result, str):
        if "No new software available" in result:
            console.print("[green]✓ macOS is up to date.[/]")
        else:
            console.print("[bold yellow]Updates Available:[/]")
            console.print(result)
    else:
        console.print("[red]Failed to check for updates.[/]")

# --- REPAIR MODULES ---

def verify_disk_structure() -> None:
    """Runs First Aid on the boot volume (Non-destructive verify)."""
    if not shutil.which("diskutil"):
        console.print("[red]Error: diskutil not found.[/]")
        return

    console.print("\n[bold white on red] Disk Verification [/]")
    console.print("[dim]This checks the APFS file system for corruption. It does NOT freeze the system.[/]")
    
    if Confirm.ask("Run Disk Verify on / (Boot Volume)?"):
        with console.status("[bold yellow]Verifying File System..."):
            # fsck_apfs -n checks without modifying
            # But diskutil verifyVolume is the user-friendly wrapper
            try:
                proc = subprocess.Popen("diskutil verifyVolume /", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                while True:
                    if proc.stdout:
                        line = proc.stdout.readline()
                        if not line and proc.poll() is not None:
                            break
                        if line:
                            console.print(f"[dim]{line.strip()}[/]")
                
                if proc.returncode == 0:
                    console.print("[bold green]✓ File System is Healthy.[/]")
                else:
                    console.print("[bold red]! File System Errors Found. Boot into Recovery Mode to repair.[/]")
            except OSError as e:
                console.print(f"[red]Error executing diskutil: {e}[/]")

def reset_launch_services() -> None:
    """Fixes duplicate apps in 'Open With' menu."""
    console.print("\n[bold cyan]Reset Launch Services Database[/]")
    console.print("[dim]Fixes duplicate entries in right-click 'Open With' menus and correct icon associations.[/]")
    
    lsregister_path = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    if not os.path.exists(lsregister_path):
        console.print(f"[red]Error: lsregister not found at {lsregister_path}[/]")
        return

    if Confirm.ask("Rebuild Launch Services?"):
        cmd = f"{lsregister_path} -kill -r -domain local -domain system -domain user"
        with console.status("Rebuilding database..."):
            run_command(cmd)
        console.print("[green]✓ Reset Complete. Finder will restart.[/]")
        run_command("killall Finder")

def nuke_font_cache() -> None:
    """Clears font caches to fix garbled text."""
    if not shutil.which("atsutil"):
        console.print("[red]Error: atsutil not found.[/]")
        return

    console.print("\n[bold cyan]Clear Font Caches[/]")
    console.print("[dim]Fixes 'tofu' boxes (□□□) or garbled text in apps.[/]")
    
    if Confirm.ask("Clear Font Cache?"):
        with console.status("Clearing..."):
            run_command("atsutil server -shutdown")
            run_command("atsutil server -ping")
        console.print("[green]✓ Font server restarted.[/]")

# --- UI ---

def show_dashboard() -> None:
    """Display system dashboard."""
    vitals = get_system_vitals()
    
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")
    
    # Left Panel: Specs
    rows = []
    rows.append(f"[bold]Model:[/] {vitals.get('model', 'Unknown')}")
    rows.append(f"[bold]Chip:[/] {vitals.get('chip', 'Unknown')}")
    rows.append(f"[bold]Memory:[/] {vitals.get('mem', 'Unknown')}")
    rows.append(f"[bold]Uptime:[/] {vitals.get('uptime', 'Unknown')}")
    
    # Right Panel: Battery (if applicable)
    batt_panel = None
    if vitals.get('is_laptop'):
        health_color = "green"
        cond = str(vitals.get('battery_cond', '')).lower()
        if cond != "normal": health_color = "red"
        
        batt_text = f"\n[bold underline]Battery Health[/]\n"
        batt_text += f"Condition: [{health_color}]{vitals.get('battery_cond')}[/]\n"
        batt_text += f"Cycle Count: {vitals.get('battery_cycle')}\n"
        batt_text += f"Max Capacity: {vitals.get('battery_max')}\n"
        batt_panel = Panel(batt_text, border_style="cyan")
    
    spec_text = "\n".join(rows)
    
    layout = Layout()
    layout.split_row(
        Layout(Panel(spec_text, title="System Specs", border_style="blue")),
        Layout(batt_panel) if batt_panel else Layout(Panel("Desktop Mac\nNo Battery Data", border_style="dim"))
    )
    
    console.print(layout)

def main() -> None:
    """Main entry point."""
    console.clear()
    console.rule("[bold magenta]Mac Health Monitor[/]")
    
    # 1. Dashboard
    show_dashboard()
    console.print("\n")

    # 2. Menu
    while True:
        console.print("\n[bold white on magenta] Diagnostic & Repair Tools [/]")
        console.print("[1] Run Network Quality Test (Apple Native)")
        console.print("[2] Check for macOS System Updates")
        console.print("[3] Verify Disk Health (APFS Check)")
        console.print("[4] Reset 'Open With' Menu (Launch Services)")
        console.print("[5] Fix Text/Font Issues (Reset Font Cache)")
        console.print("[Enter] Exit")
        
        choice = Prompt.ask("Select Tool", choices=["1", "2", "3", "4", "5", "6"], default="6", show_default=False)
        
        if choice == "1": run_network_test()
        elif choice == "2": check_software_updates()
        elif choice == "3": verify_disk_structure()
        elif choice == "4": reset_launch_services()
        elif choice == "5": nuke_font_cache()
        elif choice == "6": 
            console.print("[green]Stay Healthy![/]")
            break

run = main

if __name__ == "__main__":
    main()