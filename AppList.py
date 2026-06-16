#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                 APPLIST                                       ║
║           Comprehensive Windows Application Inventory Scanner                 ║
║                                                                               ║
║  Scans all installed applications from multiple sources and exports          ║
║  detailed information for system migration and documentation purposes.       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Matt
Version: 1.4.1
Purpose: Pre-reinstall application inventory for Windows migration
"""

# ══════════════════════════════════════════════════════════════════════════════
# AUTOMATIC DEPENDENCY MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

import subprocess
import sys
import argparse

def ensure_dependencies():
    """Automatically install required packages if missing."""
    required_packages = {
        'customtkinter': 'customtkinter>=5.2.0',
    }
    
    missing = []
    for package, pip_name in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        print("+----------------------------------------------------------------+")
        print("|               APPLIST - First Run Setup                       |")
        print("+----------------------------------------------------------------+")
        print("|  Installing required dependencies, please wait...              |")
        print("+----------------------------------------------------------------+")
        print()
        
        for package in missing:
            print(f"  - Installing {package}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"    OK {package} installed successfully")
            except subprocess.CalledProcessError:
                # Try with --user flag if regular install fails
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", package, "--user", "-q"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    print(f"    OK {package} installed successfully (user mode)")
                except subprocess.CalledProcessError as e:
                    print(f"    ERROR Failed to install {package}")
                    print(f"      Please run: pip install {package}")
                    sys.exit(1)
        
        print()
        print("  All dependencies installed! Launching application...")
        print()

# Run dependency check before importing
ensure_dependencies()

import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
import winreg
import subprocess
import json
import csv
import os
import sys
import threading
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

APP_NAME = "AppList"
APP_VERSION = "1.4.1"
APP_SUBTITLE = "Windows Application Inventory Scanner"

# Premium Dark Theme Colors
COLORS = {
    "bg_primary": "#080B10",
    "bg_secondary": "#0D1118",
    "bg_tertiary": "#121821",
    "bg_card": "#10161F",
    "bg_elevated": "#18212D",
    "bg_hover": "#202B39",
    "bg_pressed": "#0B1220",
    "accent_primary": "#2F7DF6",
    "accent_secondary": "#5EA0FF",
    "accent_glow": "#174EA6",
    "accent_success": "#6CCB77",
    "accent_warning": "#F4B740",
    "accent_error": "#F87171",
    "text_primary": "#F4F7FB",
    "text_secondary": "#C5D0DD",
    "text_muted": "#7F8B99",
    "border_subtle": "#223041",
    "border_strong": "#34465B",
    "border_accent": "#2F7DF6",
    "table_header": "#141C27",
    "table_row_alt": "#0C121A",
    "table_selected": "#1D4ED8",
}

# Registry paths for installed applications
REGISTRY_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM64"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM32"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU"),
]

SHELL_HOST_EXECUTABLES = {
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "wscript",
    "wscript.exe",
    "cscript",
    "cscript.exe",
}

CANONICAL_SCAN_SOURCES = {
    "registry",
    "store",
    "program_files",
    "chocolatey",
    "scoop",
    "pip",
    "winget",
}

SCAN_SOURCE_ALIASES = {
    "all": CANONICAL_SCAN_SOURCES,
    "desktop": {"registry", "program_files"},
    "registry": {"registry"},
    "store": {"store"},
    "uwp": {"store"},
    "appx": {"store"},
    "program_files": {"program_files"},
    "program-files": {"program_files"},
    "programfiles": {"program_files"},
    "unregistered": {"program_files"},
    "chocolatey": {"chocolatey"},
    "choco": {"chocolatey"},
    "scoop": {"scoop"},
    "pip": {"pip"},
    "python": {"pip"},
    "winget": {"winget"},
}

TYPE_FILTERS = [
    "All Types",
    "Desktop",
    "Store",
    "Unregistered",
    "Chocolatey",
    "Scoop",
    "Python (pip)",
]

SOURCE_FILTERS = [
    "All Sources",
    "Registry",
    "Program Files",
    "Microsoft Store",
    "Package Managers",
    "Python",
    "Winget Matched",
]

UPGRADE_FILTERS = [
    "Any Upgrade State",
    "Updates Available",
    "Missing Install Path",
    "Winget Matched",
    "No Winget Match",
]


def split_windows_command_line(command_line: str) -> List[str]:
    """Split a Windows command line without invoking a command shell."""
    expanded = os.path.expandvars(command_line.strip())
    if not expanded:
        return []

    if not hasattr(ctypes, "windll"):
        return shlex.split(expanded, posix=False)

    argc = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)

    argv = shell32.CommandLineToArgvW(expanded, ctypes.byref(argc))
    if not argv:
        raise ValueError("Unable to parse uninstall command.")

    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(argv, ctypes.c_void_p))


def is_shell_host_command(executable: str) -> bool:
    """Return True when a command would delegate execution to a script shell."""
    return os.path.basename(executable).lower() in SHELL_HOST_EXECUTABLES


def parse_include_sources(raw_sources: str) -> set:
    """Parse comma-separated CLI source filters into canonical scanner sources."""
    if not raw_sources:
        return set(CANONICAL_SCAN_SOURCES)

    selected = set()
    for raw_part in raw_sources.split(","):
        source = raw_part.strip().lower()
        if not source:
            continue
        if source not in SCAN_SOURCE_ALIASES:
            allowed = ", ".join(sorted(SCAN_SOURCE_ALIASES))
            raise ValueError(f"Unknown source '{source}'. Use one of: {allowed}")
        selected.update(SCAN_SOURCE_ALIASES[source])

    return selected or set(CANONICAL_SCAN_SOURCES)

# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Application:
    """Represents an installed application with all metadata."""
    name: str
    publisher: str = ""
    version: str = ""
    install_date: str = ""
    install_location: str = ""
    uninstall_registry_key: str = ""
    uninstall_command: str = ""
    estimated_size: str = ""
    source: str = ""
    architecture: str = ""
    app_type: str = "Desktop"
    winget_id: str = ""
    upgrade_available: str = ""  # "Update Available" if newer version exists in winget, else ""
    ghost: bool = False  # True if install_location doesn't exist on disk

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def to_export_row(self) -> List[str]:
        return [
            self.name,
            self.publisher,
            self.version,
            self.install_date,
            self.install_location,
            self.uninstall_registry_key,
            self.uninstall_command,
            self.estimated_size,
            self.source,
            self.architecture,
            self.app_type,
            self.winget_id,
            self.upgrade_available,
        ]


def write_txt_export(apps: List[Application], filepath: str):
    """Write applications to a TXT report."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write(f"  {APP_NAME} - Application Inventory Report\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Total Applications: {len(apps)}\n")
        f.write("=" * 100 + "\n\n")

        for i, app in enumerate(apps, 1):
            f.write(f"[{i:04d}] {app.name}\n")
            f.write("-" * 80 + "\n")
            if app.publisher:
                f.write(f"       Publisher:        {app.publisher}\n")
            if app.version:
                f.write(f"       Version:          {app.version}\n")
            if app.install_date:
                f.write(f"       Install Date:     {app.install_date}\n")
            if app.install_location:
                f.write(f"       Install Location: {app.install_location}\n")
            if app.uninstall_registry_key:
                f.write(f"       Registry Key:     {app.uninstall_registry_key}\n")
            if app.uninstall_command:
                f.write(f"       Uninstall Cmd:    {app.uninstall_command}\n")
            if app.estimated_size:
                f.write(f"       Size:             {app.estimated_size}\n")
            f.write(f"       Type:             {app.app_type}\n")
            f.write(f"       Source:           {app.source}\n")
            f.write("\n")

        f.write("=" * 100 + "\n")
        f.write("  End of Report\n")
        f.write("=" * 100 + "\n")


def write_csv_export(apps: List[Application], filepath: str):
    """Write applications to CSV."""
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Application Name",
            "Publisher",
            "Version",
            "Install Date",
            "Install Location",
            "Registry Key",
            "Uninstall Command",
            "Estimated Size",
            "Source",
            "Architecture",
            "Type",
            "Winget ID",
            "Update Available",
        ])
        for app in apps:
            writer.writerow(app.to_export_row())


def get_markdown_groups(apps: List[Application]) -> List[Tuple[str, List[Application]]]:
    """Group applications for Markdown export without dropping unknown types."""
    group_titles = {
        "Desktop": "Desktop Apps",
        "Store App": "Store / UWP Apps",
        "Desktop (Unregistered)": "Unregistered (Program Files)",
        "Chocolatey": "Chocolatey Packages",
        "Scoop": "Scoop Apps",
        "Python Package": "Python Packages (pip)",
    }
    group_order = [
        "Desktop",
        "Store App",
        "Desktop (Unregistered)",
        "Chocolatey",
        "Scoop",
        "Python Package",
    ]
    groups: Dict[str, List[Application]] = {}
    for app in apps:
        groups.setdefault(app.app_type or "Unknown", []).append(app)

    ordered_types = [app_type for app_type in group_order if app_type in groups]
    ordered_types.extend(
        sorted(app_type for app_type in groups if app_type not in group_titles)
    )
    return [(group_titles.get(app_type, app_type), groups[app_type]) for app_type in ordered_types]


def write_markdown_export(apps: List[Application], filepath: str):
    """Write applications to a Markdown report grouped by type."""
    hostname = os.environ.get("COMPUTERNAME", "Unknown")
    username = os.environ.get("USERNAME", "Unknown")

    def _md_row(i: int, app: Application) -> str:
        name = app.name.replace("|", "\\|")
        pub = app.publisher.replace("|", "\\|")
        wid = app.winget_id if app.winget_id else ""
        return f"| {i} | {name} | {pub} | {app.version} | {app.install_date} | {app.estimated_size} | {wid} |\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Application Inventory — {hostname}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Machine:** `{hostname}` / `{username}`  \n")
        f.write(f"**Total:** {len(apps)} applications  \n\n")
        f.write("---\n\n")

        for group_name, group in get_markdown_groups(apps):
            if not group:
                continue
            f.write(f"## {group_name} ({len(group)})\n\n")
            f.write("| # | Name | Publisher | Version | Install Date | Size | Winget ID |\n")
            f.write("|---|------|-----------|---------|--------------|------|-----------|\n")
            for i, app in enumerate(group, 1):
                f.write(_md_row(i, app))
            f.write("\n")


def write_json_export(apps: List[Application], filepath: str):
    """Write applications to AppList JSON."""
    hostname = os.environ.get("COMPUTERNAME", "Unknown")
    export_data = {
        "schema": f"AppList/{APP_VERSION}",
        "generated": datetime.now().isoformat(),
        "machine": hostname,
        "total": len(apps),
        "applications": [app.to_dict() for app in apps],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)


def write_winget_export(apps: List[Application], filepath: str) -> int:
    """Write matched apps as winget import-compatible JSON and return count."""
    winget_apps = [a for a in apps if a.winget_id]
    if not winget_apps:
        raise ValueError("No applications with winget IDs are available to export.")

    packages_list = [
        {
            "PackageIdentifier": a.winget_id,
            "PackageVersion": a.version,
            "PackageName": a.name,
            "PackageSource": "winget",
        }
        for a in winget_apps
    ]
    export_data = {
        "$schema": "https://aka.ms/winget-packages.schema.2.0.json",
        "CreationDate": datetime.now().isoformat(),
        "WinGetVersion": "1.0.0",
        "Sources": [
            {
                "SourceDetails": {
                    "Argument": "https://cdn.winget.microsoft.com/cache",
                    "Identifier": "Microsoft.Winget.Source_8wekyb3d8bbwe",
                    "Name": "winget",
                    "Type": "Microsoft.PreIndexed.Package",
                },
                "Packages": packages_list,
            }
        ],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    return len(winget_apps)

# ══════════════════════════════════════════════════════════════════════════════
# APPLICATION SCANNER ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ApplicationScanner:
    """Core engine for scanning installed applications from multiple sources."""
    
    def __init__(self, progress_callback=None, status_callback=None):
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.applications: List[Application] = []
        self.seen_apps: set = set()
        self._cancelled = False
    
    def cancel(self):
        """Cancel the scanning operation."""
        self._cancelled = True
    
    def _update_progress(self, value: float, maximum: float = 100):
        if self.progress_callback:
            self.progress_callback(value, maximum)
    
    def _update_status(self, status: str):
        if self.status_callback:
            self.status_callback(status)

    def _log_warning(self, message: str):
        print(f"Warning: {message}", file=sys.stderr)
    
    def _normalize_name(self, name: str) -> str:
        """Normalize application name for deduplication."""
        return re.sub(r'[^\w]', '', name.lower())
    
    def _format_size(self, size_kb: int) -> str:
        """Format size in KB to human-readable string."""
        if size_kb <= 0:
            return ""
        if size_kb < 1024:
            return f"{size_kb} KB"
        elif size_kb < 1024 * 1024:
            return f"{size_kb / 1024:.1f} MB"
        else:
            return f"{size_kb / (1024 * 1024):.2f} GB"
    
    def _parse_install_date(self, date_str: str) -> str:
        """Parse install date from various formats."""
        if not date_str:
            return ""
        try:
            if len(date_str) == 8 and date_str.isdigit():
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return date_str
        except (TypeError, ValueError):
            return date_str
    
    def _get_registry_value(self, key, value_name: str, default: str = "") -> str:
        """Safely get a registry value."""
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value) if value else default
        except (FileNotFoundError, OSError):
            return default
    
    def scan_registry(self) -> List[Application]:
        """Scan Windows Registry for installed applications."""
        apps = []
        total_paths = len(REGISTRY_PATHS)
        
        for idx, (hive, path, source_name) in enumerate(REGISTRY_PATHS):
            if self._cancelled:
                break
                
            self._update_status(f"Scanning registry: {source_name}...")
            self._update_progress((idx / total_paths) * 20)
            
            try:
                arch = "64-bit" if "WOW6432Node" not in path else "32-bit"
                if source_name == "HKCU":
                    arch = "User"
                
                access_flag = winreg.KEY_READ
                if "WOW6432Node" not in path and hive == winreg.HKEY_LOCAL_MACHINE:
                    access_flag |= winreg.KEY_WOW64_64KEY
                
                with winreg.OpenKey(hive, path, 0, access_flag) as key:
                    subkey_count = winreg.QueryInfoKey(key)[0]
                    
                    for i in range(subkey_count):
                        if self._cancelled:
                            break
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name, 0, access_flag) as subkey:
                                name = self._get_registry_value(subkey, "DisplayName")
                                
                                if not name:
                                    continue
                                
                                # Skip system components and updates
                                system_component = self._get_registry_value(subkey, "SystemComponent")
                                if system_component == "1":
                                    continue
                                
                                parent_name = self._get_registry_value(subkey, "ParentDisplayName")
                                if parent_name:
                                    continue
                                
                                # Deduplicate
                                norm_name = self._normalize_name(name)
                                if norm_name in self.seen_apps:
                                    continue
                                self.seen_apps.add(norm_name)
                                
                                # Build full registry path
                                hive_name = "HKEY_LOCAL_MACHINE" if hive == winreg.HKEY_LOCAL_MACHINE else "HKEY_CURRENT_USER"
                                full_reg_path = f"{hive_name}\\{path}\\{subkey_name}"
                                
                                # Get size
                                size_kb = 0
                                try:
                                    size_kb = int(self._get_registry_value(subkey, "EstimatedSize", "0"))
                                except ValueError:
                                    pass
                                
                                app = Application(
                                    name=name,
                                    publisher=self._get_registry_value(subkey, "Publisher"),
                                    version=self._get_registry_value(subkey, "DisplayVersion"),
                                    install_date=self._parse_install_date(
                                        self._get_registry_value(subkey, "InstallDate")
                                    ),
                                    install_location=self._get_registry_value(subkey, "InstallLocation"),
                                    uninstall_registry_key=full_reg_path,
                                    uninstall_command=self._get_registry_value(subkey, "UninstallString"),
                                    estimated_size=self._format_size(size_kb),
                                    source=source_name,
                                    architecture=arch,
                                    app_type="Desktop",
                                )
                                apps.append(app)
                                
                        except (OSError, PermissionError):
                            continue
                            
            except (FileNotFoundError, OSError, PermissionError) as e:
                self._log_warning(f"Registry source {source_name} could not be scanned: {e}")
                continue
        
        return apps
    
    def scan_store_apps(self) -> List[Application]:
        """Scan Microsoft Store / UWP applications."""
        apps = []
        self._update_status("Scanning Microsoft Store apps...")
        self._update_progress(22)
        
        try:
            # Use PowerShell to get AppX packages
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-AppxPackage | Select-Object Name, Publisher, Version, InstallLocation, PackageFullName | ConvertTo-Json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0 and result.stdout.strip():
                packages = json.loads(result.stdout)
                if not isinstance(packages, list):
                    packages = [packages]
                
                total = len(packages)
                for idx, pkg in enumerate(packages):
                    if self._cancelled:
                        break
                    
                    self._update_progress(22 + (idx / total) * 12)
                    
                    name = pkg.get("Name", "")
                    if not name:
                        continue
                    
                    # Skip framework packages
                    if any(x in name.lower() for x in [".net", "vclibs", "framework", "microsoft.ui"]):
                        continue
                    
                    # Create friendly name
                    display_name = name.split(".")[-1] if "." in name else name
                    display_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', display_name)
                    
                    norm_name = self._normalize_name(display_name)
                    if norm_name in self.seen_apps:
                        continue
                    self.seen_apps.add(norm_name)
                    
                    publisher = pkg.get("Publisher", "")
                    # Clean up publisher string
                    if publisher:
                        pub_match = re.search(r'CN=([^,]+)', publisher)
                        if pub_match:
                            publisher = pub_match.group(1)
                    
                    app = Application(
                        name=f"[Store] {display_name}",
                        publisher=publisher,
                        version=pkg.get("Version", ""),
                        install_location=pkg.get("InstallLocation", ""),
                        uninstall_registry_key="",
                        uninstall_command=f"Remove-AppxPackage {pkg.get('PackageFullName', '')}",
                        source="Microsoft Store",
                        architecture="UWP",
                        app_type="Store App",
                    )
                    apps.append(app)
                    
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError,
                json.JSONDecodeError, OSError, TypeError) as e:
            self._log_warning(f"Microsoft Store scan failed: {e}")
        
        return apps
    
    def scan_program_files(self) -> List[Application]:
        """Scan Program Files directories for additional applications."""
        apps = []
        self._update_status("Scanning Program Files directories...")
        self._update_progress(36)
        
        program_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        ]
        
        total_dirs = len(program_dirs)
        
        for dir_idx, program_dir in enumerate(program_dirs):
            if self._cancelled:
                break
            if not os.path.exists(program_dir):
                continue
            
            try:
                subdirs = os.listdir(program_dir)
                for sub_idx, subdir in enumerate(subdirs):
                    if self._cancelled:
                        break
                    
                    self._update_progress(36 + ((dir_idx * len(subdirs) + sub_idx) / (total_dirs * max(len(subdirs), 1))) * 14)
                    
                    full_path = os.path.join(program_dir, subdir)
                    if not os.path.isdir(full_path):
                        continue
                    
                    # Skip common system/framework folders
                    skip_folders = [
                        "common files", "windows", "microsoft", "internet explorer",
                        "windowsapps", "modifiablewindowsapps", "reference assemblies"
                    ]
                    if subdir.lower() in skip_folders:
                        continue
                    
                    norm_name = self._normalize_name(subdir)
                    if norm_name in self.seen_apps:
                        continue
                    
                    # Check if folder contains executables
                    has_exe = False
                    exe_path = ""
                    try:
                        for item in os.listdir(full_path):
                            if item.lower().endswith('.exe'):
                                has_exe = True
                                exe_path = os.path.join(full_path, item)
                                break
                    except PermissionError:
                        continue
                    
                    if not has_exe:
                        continue
                    
                    self.seen_apps.add(norm_name)
                    
                    # Determine architecture from path
                    arch = "32-bit" if "x86" in program_dir.lower() else "64-bit"
                    
                    app = Application(
                        name=f"[Folder] {subdir}",
                        install_location=full_path,
                        source="Program Files Scan",
                        architecture=arch,
                        app_type="Desktop (Unregistered)",
                    )
                    apps.append(app)
                    
            except (PermissionError, OSError):
                continue
        
        return apps
    
    def scan_all(self, include_sources: Optional[set] = None) -> List[Application]:
        """Perform comprehensive scan of all sources."""
        self._cancelled = False
        self.applications = []
        self.seen_apps = set()

        def source_enabled(source: str) -> bool:
            return include_sources is None or source in include_sources
        
        # Scan registry (primary source)
        if source_enabled("registry"):
            self._update_status("Phase 1/7: Scanning Windows Registry...")
            registry_apps = self.scan_registry()
            self.applications.extend(registry_apps)
            
            if self._cancelled:
                return self.applications
        
        # Scan Store apps
        if source_enabled("store"):
            self._update_status("Phase 2/7: Scanning Microsoft Store apps...")
            store_apps = self.scan_store_apps()
            self.applications.extend(store_apps)
            
            if self._cancelled:
                return self.applications
        
        # Scan Program Files
        if source_enabled("program_files"):
            self._update_status("Phase 3/7: Scanning Program Files...")
            folder_apps = self.scan_program_files()
            self.applications.extend(folder_apps)
            
            if self._cancelled:
                return self.applications
        
        # Scan Chocolatey packages
        if source_enabled("chocolatey"):
            self._update_status("Phase 4/7: Scanning Chocolatey packages...")
            choco_apps = self.scan_chocolatey()
            self.applications.extend(choco_apps)
            
            if self._cancelled:
                return self.applications
        
        # Scan Scoop packages
        if source_enabled("scoop"):
            self._update_status("Phase 5/7: Scanning Scoop packages...")
            scoop_apps = self.scan_scoop()
            self.applications.extend(scoop_apps)
            
            if self._cancelled:
                return self.applications
        
        # Scan pip packages
        if source_enabled("pip"):
            self._update_status("Phase 6/7: Scanning Python (pip) packages...")
            pip_apps = self.scan_pip()
            self.applications.extend(pip_apps)
            
            if self._cancelled:
                return self.applications
        
        # Cross-reference with winget for package IDs and upgrade status
        if source_enabled("winget"):
            self._update_status("Phase 7/7: Cross-referencing with winget...")
            winget_map = self._build_winget_map()
            if winget_map:
                for app in self.applications:
                    norm = self._normalize_name(app.name)
                    if norm in winget_map:
                        app.winget_id = winget_map[norm]
            
            # Check for upgradeable versions
            upgrade_map = self._build_upgrade_map()
            if upgrade_map:
                for app in self.applications:
                    if app.winget_id and app.winget_id in upgrade_map:
                        app.upgrade_available = f"Update Available ({upgrade_map[app.winget_id]})"
        
        # Ghost entry detection: flag apps whose install location doesn't exist
        for app in self.applications:
            if app.install_location and not os.path.exists(app.install_location):
                app.ghost = True
        
        # Sort by name
        self.applications.sort(key=lambda x: x.name.lower())
        
        self._update_progress(100)
        self._update_status(f"Scan complete. Found {len(self.applications)} applications.")
        
        return self.applications

    def scan_chocolatey(self) -> List[Application]:
        """Scan Chocolatey installed packages from %PROGRAMDATA%\\chocolatey\\lib\\."""
        apps: List[Application] = []
        choco_lib = os.path.join(
            os.environ.get("ProgramData", r"C:\ProgramData"), "chocolatey", "lib"
        )
        if not os.path.isdir(choco_lib):
            return apps

        self._update_status("Scanning Chocolatey packages...")
        self._update_progress(52)

        try:
            pkg_dirs = [d for d in os.listdir(choco_lib) if os.path.isdir(os.path.join(choco_lib, d))]
        except OSError as e:
            self._log_warning(f"Chocolatey package directory could not be listed: {e}")
            return apps

        for pkg_dir in pkg_dirs:
            if self._cancelled:
                break
            norm = self._normalize_name(pkg_dir)
            if norm in self.seen_apps:
                continue

            pkg_path = os.path.join(choco_lib, pkg_dir)
            name = pkg_dir
            version = ""
            publisher = ""

            # Parse .nuspec for metadata
            try:
                nuspec_files = [f for f in os.listdir(pkg_path) if f.endswith(".nuspec")]
            except OSError as e:
                self._log_warning(f"Could not list Chocolatey metadata for {pkg_dir}: {e}")
                nuspec_files = []
            if nuspec_files:
                nuspec_path = os.path.join(pkg_path, nuspec_files[0])
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(nuspec_path)
                    root = tree.getroot()
                    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
                    prefix = f"{{{ns}}}" if ns else ""
                    meta = root.find(f"{prefix}metadata")
                    if meta is not None:
                        id_el = meta.find(f"{prefix}id")
                        ver_el = meta.find(f"{prefix}version")
                        auth_el = meta.find(f"{prefix}authors")
                        if id_el is not None and id_el.text:
                            name = id_el.text.strip()
                        if ver_el is not None and ver_el.text:
                            version = ver_el.text.strip()
                        if auth_el is not None and auth_el.text:
                            publisher = auth_el.text.strip()
                except (OSError, ET.ParseError, AttributeError) as e:
                    self._log_warning(f"Could not read Chocolatey metadata for {pkg_dir}: {e}")

            self.seen_apps.add(norm)
            apps.append(Application(
                name=name,
                version=version,
                publisher=publisher,
                install_location=pkg_path,
                source="Chocolatey",
                app_type="Chocolatey",
            ))

        return apps

    def scan_scoop(self) -> List[Application]:
        """Scan Scoop installed apps from ~\\scoop\\apps\\."""
        apps: List[Application] = []
        scoop_apps = os.path.join(os.path.expanduser("~"), "scoop", "apps")

        # Also check SCOOP env var
        scoop_env = os.environ.get("SCOOP", "")
        if scoop_env:
            scoop_apps = os.path.join(scoop_env, "apps")

        if not os.path.isdir(scoop_apps):
            return apps

        self._update_status("Scanning Scoop packages...")
        self._update_progress(58)

        try:
            app_dirs = [d for d in os.listdir(scoop_apps)
                        if os.path.isdir(os.path.join(scoop_apps, d)) and d != "scoop"]
        except OSError as e:
            self._log_warning(f"Scoop app directory could not be listed: {e}")
            return apps

        for app_dir in app_dirs:
            if self._cancelled:
                break
            norm = self._normalize_name(app_dir)
            if norm in self.seen_apps:
                continue

            app_path = os.path.join(scoop_apps, app_dir)
            current_path = os.path.join(app_path, "current")
            name = app_dir
            version = ""
            publisher = ""

            # Parse current\manifest.json
            manifest_path = os.path.join(current_path, "manifest.json")
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, encoding="utf-8") as f:
                        manifest = json.load(f)
                    version = str(manifest.get("version", "")).strip()
                    publisher = str(manifest.get("homepage", "")).strip()
                except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
                    self._log_warning(f"Could not read Scoop manifest for {app_dir}: {e}")

            # Fallback: version folder name
            if not version:
                try:
                    versions = [d for d in os.listdir(app_path)
                                if os.path.isdir(os.path.join(app_path, d)) and d != "current"]
                    if versions:
                        version = sorted(versions)[-1]
                except OSError as e:
                    self._log_warning(f"Could not list Scoop versions for {app_dir}: {e}")

            self.seen_apps.add(norm)
            apps.append(Application(
                name=name,
                version=version,
                publisher=publisher,
                install_location=current_path if os.path.isdir(current_path) else app_path,
                source="Scoop",
                app_type="Scoop",
            ))

        return apps

    def scan_pip(self) -> List[Application]:
        """Scan pip-installed Python packages."""
        apps: List[Application] = []
        self._update_status("Scanning Python (pip) packages...")
        self._update_progress(64)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                return apps

            packages = json.loads(result.stdout)
            for pkg in packages:
                if self._cancelled:
                    break
                pkg_name = str(pkg.get("name", "")).strip()
                if not pkg_name:
                    continue
                norm = self._normalize_name(pkg_name)
                if norm in self.seen_apps:
                    continue
                self.seen_apps.add(norm)
                apps.append(Application(
                    name=pkg_name,
                    version=str(pkg.get("version", "")).strip(),
                    publisher="",
                    source="Python (pip)",
                    app_type="Python Package",
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError,
                json.JSONDecodeError, OSError) as e:
            self._log_warning(f"pip package scan failed: {e}")

        return apps

    def _build_winget_map(self) -> Dict[str, str]:
        """Build a normalized-name → winget-package-ID map via winget list."""
        winget_map: Dict[str, str] = {}
        self._update_progress(73)
        try:
            # Try JSON output (winget 1.6+)
            result = subprocess.run(
                ["winget", "list", "--accept-source-agreements",
                 "--disable-interactivity", "--output", "json"],
                capture_output=True, text=True, timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            packages: List[Dict[str, str]] = []
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list) and data:
                        packages = data
                except json.JSONDecodeError:
                    pass

            # Fall back to tabular text parsing
            if not packages:
                result = subprocess.run(
                    ["winget", "list", "--accept-source-agreements",
                     "--disable-interactivity"],
                    capture_output=True, text=True, timeout=90,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    packages = self._parse_winget_table(result.stdout)

            for pkg in packages:
                name = str(pkg.get("Name", "")).strip()
                winget_id = str(pkg.get("Id", "")).strip()
                if name and winget_id:
                    winget_map[self._normalize_name(name)] = winget_id

        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            self._log_warning(f"winget list cross-reference failed: {e}")

        return winget_map

    def _parse_winget_table(self, output: str) -> List[Dict[str, str]]:
        """Parse winget column-aligned text output into a list of dicts."""
        packages: List[Dict[str, str]] = []
        lines = output.splitlines()

        header_idx = -1
        for i, line in enumerate(lines):
            if "Name" in line and "Id" in line and "Version" in line:
                header_idx = i
                break
        if header_idx < 0:
            return packages

        header = lines[header_idx]
        name_pos = header.find("Name")
        id_pos = header.find("Id")
        ver_pos = header.find("Version")
        if name_pos < 0 or id_pos < 0:
            return packages

        for line in lines[header_idx + 2:]:
            if not line.strip():
                continue
            try:
                name = line[name_pos:id_pos].strip() if id_pos > name_pos else ""
                winget_id = (
                    line[id_pos:ver_pos].strip()
                    if ver_pos > id_pos
                    else line[id_pos:].strip()
                )
                version = (
                    line[ver_pos:].split()[0]
                    if ver_pos > 0 and len(line) > ver_pos
                    else ""
                )
                if name or winget_id:
                    packages.append({"Name": name, "Id": winget_id, "Version": version})
            except (IndexError, ValueError):
                continue

        return packages

    def _build_upgrade_map(self) -> Dict[str, str]:
        """Build a winget_id → new_version map via winget upgrade."""
        upgrade_map: Dict[str, str] = {}
        self._update_progress(75)
        try:
            result = subprocess.run(
                ["winget", "upgrade", "--accept-source-agreements",
                 "--disable-interactivity", "--output", "json"],
                capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    upgradeable = data.get("Upgradeable", [])
                    for pkg in upgradeable:
                        pkg_id = str(pkg.get("Id", "")).strip()
                        new_ver = str(pkg.get("AvailableVersion", "")).strip()
                        if pkg_id and new_ver:
                            upgrade_map[pkg_id] = new_ver
                except json.JSONDecodeError:
                    pass
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            self._log_warning(f"winget upgrade cross-reference failed: {e}")
        return upgrade_map

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ══════════════════════════════════════════════════════════════════════════════

class GradientFrame(ctk.CTkFrame):
    """A frame with gradient background effect."""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["bg_primary"])

class StatsCard(ctk.CTkFrame):
    """Compact statistics card with a stable visual rhythm."""

    def __init__(
        self,
        master,
        title: str,
        value: str = "0",
        helper: str = "",
        accent: str = COLORS["accent_primary"],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.configure(
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border_subtle"],
        )

        accent_bar = ctk.CTkFrame(self, width=3, fg_color=accent, corner_radius=0)
        accent_bar.pack(side="left", fill="y")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x")

        self.value_label = ctk.CTkLabel(
            top_row,
            text=value,
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self.value_label.pack(side="left")

        self.title_label = ctk.CTkLabel(
            top_row,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        self.title_label.pack(side="left", padx=(12, 0), pady=(7, 0))

        self.helper_label = ctk.CTkLabel(
            content,
            text=helper,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self.helper_label.pack(anchor="w", pady=(5, 0))

    def set_value(self, value: str):
        self.value_label.configure(text=value)

    def set_title(self, title: str):
        self.title_label.configure(text=title)

    def set_helper(self, helper: str):
        self.helper_label.configure(text=helper)


class PremiumButton(ctk.CTkButton):
    """Primary action button."""

    def __init__(self, master, **kwargs):
        default_config = {
            "corner_radius": 8,
            "height": 38,
            "font": ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            "fg_color": COLORS["accent_primary"],
            "hover_color": COLORS["accent_secondary"],
            "text_color": COLORS["text_primary"],
            "text_color_disabled": COLORS["text_muted"],
        }
        default_config.update(kwargs)
        super().__init__(master, **default_config)


class SecondaryButton(ctk.CTkButton):
    """Secondary action button with consistent disabled treatment."""

    def __init__(self, master, **kwargs):
        default_config = {
            "corner_radius": 8,
            "height": 38,
            "font": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "fg_color": COLORS["bg_elevated"],
            "hover_color": COLORS["bg_hover"],
            "text_color": COLORS["text_secondary"],
            "text_color_disabled": COLORS["text_muted"],
            "border_width": 1,
            "border_color": COLORS["border_subtle"],
        }
        default_config.update(kwargs)
        super().__init__(master, **default_config)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class AppList(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1400x900")
        self.minsize(1200, 700)
        
        # Set dark title bar on Windows
        self._set_dark_title_bar()
        
        # Configure appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.configure(fg_color=COLORS["bg_primary"])
        
        # State
        self.scanner = None
        self.applications: List[Application] = []
        self.filtered_apps: List[Application] = []
        self.tree_iid_to_index: Dict[str, int] = {}
        self.scan_thread = None
        self.sort_column = "name"
        self.sort_reverse = False
        self.is_scanning = False
        self.scan_has_run = False
        
        # Build UI
        self._create_header()
        self._create_stats_panel()
        self._create_toolbar()
        self._create_main_content()
        self._create_status_bar()
        self._set_export_buttons_enabled(False)
        self._show_empty_state(
            "No inventory yet",
            "Run a scan to discover installed desktop, Store, package-manager, and Python applications.",
            action_text="Scan System",
            action_command=self._start_scan,
        )
        
        # Configure treeview style
        self._configure_treeview_style()
        
        # Bind events
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _set_dark_title_bar(self):
        """Enable dark title bar on Windows 10/11."""
        try:
            self.update()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except (AttributeError, OSError, ValueError, tk.TclError):
            pass
    
    def _configure_treeview_style(self):
        """Configure premium treeview styling."""
        style = ttk.Style()
        
        style.theme_use("clam")
        
        # Treeview configuration
        style.configure(
            "Premium.Treeview",
            background=COLORS["bg_secondary"],
            foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_secondary"],
            borderwidth=0,
            bordercolor=COLORS["bg_secondary"],
            lightcolor=COLORS["bg_secondary"],
            darkcolor=COLORS["bg_secondary"],
            relief="flat",
            font=("Segoe UI", 10),
            rowheight=34,
        )
        style.layout("Premium.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        
        style.configure(
            "Premium.Treeview.Heading",
            background=COLORS["table_header"],
            foreground=COLORS["text_primary"],
            borderwidth=0,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        
        style.map(
            "Premium.Treeview",
            background=[("selected", COLORS["table_selected"])],
            foreground=[("selected", COLORS["text_primary"])],
        )
        
        style.map(
            "Premium.Treeview.Heading",
            background=[("active", COLORS["bg_elevated"])],
            foreground=[("active", COLORS["text_primary"])],
        )
        
        # Scrollbar styling
        style.configure(
            "Premium.Vertical.TScrollbar",
            background=COLORS["bg_elevated"],
            troughcolor=COLORS["bg_secondary"],
            borderwidth=0,
            arrowsize=0,
        )
        style.configure(
            "Premium.Horizontal.TScrollbar",
            background=COLORS["bg_elevated"],
            troughcolor=COLORS["bg_secondary"],
            borderwidth=0,
            arrowsize=0,
        )
    
    def _create_header(self):
        """Create the premium header section."""
        header_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_secondary"],
            corner_radius=0,
            height=88,
        )
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Inner container
        inner = ctk.CTkFrame(header_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=30, pady=17)
        
        # Left side - branding
        brand_frame = ctk.CTkFrame(inner, fg_color="transparent")
        brand_frame.pack(side="left", fill="y")
        
        # App icon placeholder
        icon_label = ctk.CTkLabel(
            brand_frame,
            text="◈",
            font=ctk.CTkFont(size=32),
            text_color=COLORS["accent_primary"],
        )
        icon_label.pack(side="left", padx=(0, 14))
        
        # Title stack
        title_stack = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_stack.pack(side="left", fill="y", pady=2)

        title_row = ctk.CTkFrame(title_stack, fg_color="transparent")
        title_row.pack(anchor="w")
        
        title_label = ctk.CTkLabel(
            title_row,
            text=APP_NAME,
            font=ctk.CTkFont(family="Segoe UI", size=23, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        title_label.pack(side="left")

        version_label = ctk.CTkLabel(
            title_row,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        )
        version_label.pack(side="left", padx=(10, 0), pady=(4, 0))
        
        subtitle_label = ctk.CTkLabel(
            title_stack,
            text=APP_SUBTITLE,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
        )
        subtitle_label.pack(anchor="w")
        
        # Right side - primary actions
        actions_frame = ctk.CTkFrame(inner, fg_color="transparent")
        actions_frame.pack(side="right", fill="y")
        
        self.scan_button = PremiumButton(
            actions_frame,
            text="Scan System",
            width=150,
            command=self._start_scan,
        )
        self.scan_button.pack(side="left", padx=(0, 10))
        
        self.cancel_button = SecondaryButton(
            actions_frame,
            text="Cancel",
            width=96,
            command=self._cancel_scan,
            state="disabled",
        )
        self.cancel_button.pack(side="left")
    
    def _create_stats_panel(self):
        """Create the statistics dashboard panel."""
        stats_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            height=102,
        )
        stats_frame.pack(fill="x", padx=30, pady=(18, 0))
        stats_frame.pack_propagate(False)
        
        # Stats cards
        self.stats_total = StatsCard(
            stats_frame,
            "Total",
            "0",
            "All applications found",
            COLORS["accent_primary"],
        )
        self.stats_total.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.stats_desktop = StatsCard(
            stats_frame,
            "Desktop",
            "0",
            "Registry and desktop entries",
            COLORS["accent_secondary"],
        )
        self.stats_desktop.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.stats_store = StatsCard(
            stats_frame,
            "Store",
            "0",
            "Microsoft Store packages",
            COLORS["accent_success"],
        )
        self.stats_store.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.stats_unregistered = StatsCard(
            stats_frame,
            "Other",
            "0",
            "Unregistered, package, and Python",
            COLORS["accent_warning"],
        )
        self.stats_unregistered.pack(side="left", fill="both", expand=True)
    
    def _create_toolbar(self):
        """Create the toolbar with search and export options."""
        toolbar_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            height=92,
        )
        toolbar_frame.pack(fill="x", padx=30, pady=(18, 12))
        toolbar_frame.pack_propagate(False)

        top_row = ctk.CTkFrame(toolbar_frame, fg_color="transparent")
        top_row.pack(fill="x")

        bottom_row = ctk.CTkFrame(toolbar_frame, fg_color="transparent")
        bottom_row.pack(fill="x", pady=(10, 0))
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_changed)

        search_label = ctk.CTkLabel(
            top_row,
            text="Search",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        )
        search_label.pack(side="left", padx=(0, 8))
        
        self.search_entry = ctk.CTkEntry(
            top_row,
            placeholder_text="Search applications...",
            textvariable=self.search_var,
            width=300,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border_subtle"],
            placeholder_text_color=COLORS["text_muted"],
            corner_radius=8,
        )
        self.search_entry.pack(side="left")

        self.filter_var = tk.StringVar(value="All Types")
        self.filter_dropdown = ctk.CTkComboBox(
            top_row,
            values=TYPE_FILTERS,
            variable=self.filter_var,
            width=150,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border_subtle"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_elevated"],
            corner_radius=8,
            state="readonly",
            command=self._on_filter_changed,
        )
        self.filter_dropdown.pack(side="left", padx=(10, 0))

        self.source_filter_var = tk.StringVar(value="All Sources")
        self.source_filter_dropdown = ctk.CTkComboBox(
            top_row,
            values=SOURCE_FILTERS,
            variable=self.source_filter_var,
            width=170,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border_subtle"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_elevated"],
            corner_radius=8,
            state="readonly",
            command=self._on_filter_changed,
        )
        self.source_filter_dropdown.pack(side="left", padx=(10, 0))

        self.upgrade_filter_var = tk.StringVar(value="Any Upgrade State")
        self.upgrade_filter_dropdown = ctk.CTkComboBox(
            top_row,
            values=UPGRADE_FILTERS,
            variable=self.upgrade_filter_var,
            width=190,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border_subtle"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_elevated"],
            corner_radius=8,
            state="readonly",
            command=self._on_filter_changed,
        )
        self.upgrade_filter_dropdown.pack(side="left", padx=(10, 0))

        export_hint = ctk.CTkLabel(
            bottom_row,
            text="Exports use the current filtered view.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        export_hint.pack(side="left")

        export_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        export_frame.pack(side="right")
        
        self.export_txt_btn = SecondaryButton(
            export_frame,
            text="Export TXT",
            width=106,
            command=self._export_txt,
        )
        self.export_txt_btn.pack(side="left", padx=(0, 8))
        
        self.export_csv_btn = SecondaryButton(
            export_frame,
            text="Export CSV",
            width=106,
            command=self._export_csv,
        )
        self.export_csv_btn.pack(side="left", padx=(0, 8))

        self.export_md_btn = SecondaryButton(
            export_frame,
            text="Export MD",
            width=104,
            command=self._export_markdown,
        )
        self.export_md_btn.pack(side="left", padx=(0, 8))

        self.export_json_btn = SecondaryButton(
            export_frame,
            text="Export JSON",
            width=116,
            command=self._export_json,
        )
        self.export_json_btn.pack(side="left", padx=(0, 8))

        self.export_winget_btn = SecondaryButton(
            export_frame,
            text="Export Winget",
            width=124,
            command=self._export_winget,
        )
        self.export_winget_btn.pack(side="left")
    
    def _create_main_content(self):
        """Create the main content area with treeview."""
        content_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border_subtle"],
        )
        content_frame.pack(fill="both", expand=True, padx=30, pady=(0, 14))
        
        # Treeview columns
        columns = (
            "name", "publisher", "version", "install_date",
            "type", "source", "upgrade_available", "winget_id",
            "size", "architecture", "install_location", "registry_key",
        )
        
        # Create treeview with scrollbar
        tree_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Scrollbars
        y_scroll = ctk.CTkScrollbar(
            tree_frame,
            orientation="vertical",
            width=12,
            corner_radius=4,
            fg_color=COLORS["bg_secondary"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
        )
        x_scroll = ctk.CTkScrollbar(
            tree_frame,
            orientation="horizontal",
            height=12,
            corner_radius=4,
            fg_color=COLORS["bg_secondary"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
        )
        
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Premium.Treeview",
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        
        y_scroll.configure(command=self.tree.yview)
        x_scroll.configure(command=self.tree.xview)
        
        # Configure columns
        column_config = {
            "name": ("Application", 260),
            "publisher": ("Publisher", 180),
            "version": ("Version", 100),
            "install_date": ("Installed", 105),
            "type": ("Type", 132),
            "source": ("Source", 132),
            "upgrade_available": ("Upgrade", 175),
            "winget_id": ("Winget ID", 200),
            "size": ("Size", 90),
            "architecture": ("Arch", 80),
            "install_location": ("Location", 280),
            "registry_key": ("Registry Key", 320),
        }
        
        for col, (heading, width) in column_config.items():
            self.tree.heading(col, text=heading, anchor="w", command=lambda c=col: self._sort_by_column(c))
            self.tree.column(col, width=width, minwidth=80, anchor="w")
        
        # Pack treeview and scrollbars
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.tag_configure("ghost", foreground=COLORS["accent_warning"])
        self.tree.tag_configure("update", foreground=COLORS["accent_secondary"])

        self.empty_state_frame = ctk.CTkFrame(
            content_frame,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
        )
        self.empty_icon = ctk.CTkLabel(
            self.empty_state_frame,
            text="AppList",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["accent_primary"],
        )
        self.empty_icon.pack(padx=28, pady=(24, 8))

        self.empty_title = ctk.CTkLabel(
            self.empty_state_frame,
            text="No inventory yet",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self.empty_title.pack(padx=28)

        self.empty_body = ctk.CTkLabel(
            self.empty_state_frame,
            text="Run a scan to discover installed applications.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
            wraplength=420,
            justify="center",
        )
        self.empty_body.pack(padx=28, pady=(8, 18))

        self.empty_action = SecondaryButton(
            self.empty_state_frame,
            text="Scan System",
            width=142,
            command=self._start_scan,
        )
        self.empty_action.pack(padx=28, pady=(0, 24))
        
        # Context menu
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            bg=COLORS["bg_card"],
            fg=COLORS["text_primary"],
            activebackground=COLORS["bg_hover"],
            activeforeground=COLORS["text_primary"],
            disabledforeground=COLORS["text_muted"],
        )
        self.context_menu.add_command(label="Copy Name", command=self._copy_name)
        self.context_menu.add_command(label="Copy Install Location", command=self._copy_location)
        self.context_menu.add_command(label="Copy Registry Key", command=self._copy_registry)
        self.context_menu.add_command(label="Copy Uninstall Command", command=self._copy_uninstall)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open Install Location", command=self._open_location)
        self.context_menu.add_command(label="Open Registry Key in Regedit", command=self._open_registry_key)
        self.context_menu.add_command(label="Lookup on Winget", command=self._lookup_winget)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Uninstall", command=self._uninstall_app)
        
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-1>", self._on_double_click)
    
    def _create_status_bar(self):
        """Create the status bar at the bottom."""
        status_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_secondary"],
            corner_radius=0,
            height=52,
        )
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)
        
        inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=30)
        
        self.status_dot = ctk.CTkLabel(
            inner,
            text="●",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["accent_success"],
        )
        self.status_dot.pack(side="left", pady=13, padx=(0, 10))

        self.status_label = ctk.CTkLabel(
            inner,
            text="Ready to scan",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        self.status_label.pack(side="left", pady=13)

        self.count_label = ctk.CTkLabel(
            inner,
            text="No scan performed yet",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self.count_label.pack(side="left", padx=(22, 0), pady=13)

        self.progress_percent_label = ctk.CTkLabel(
            inner,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["accent_primary"],
        )
        self.progress_percent_label.pack(side="right", pady=13)
        
        self.progress_bar = ctk.CTkProgressBar(
            inner,
            width=260,
            height=6,
            fg_color=COLORS["bg_tertiary"],
            progress_color=COLORS["accent_primary"],
            corner_radius=3,
        )
        self.progress_bar.pack(side="right", padx=(12, 12), pady=13)
        self.progress_bar.set(0)

        progress_label = ctk.CTkLabel(
            inner,
            text="Progress",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        progress_label.pack(side="right", pady=13)

    def _set_export_buttons_enabled(self, enabled: bool):
        """Enable exports only when there is a meaningful filtered result set."""
        state = "normal" if enabled else "disabled"
        for button in (
            self.export_txt_btn,
            self.export_csv_btn,
            self.export_md_btn,
            self.export_json_btn,
            self.export_winget_btn,
        ):
            button.configure(state=state)

    def _set_status_tone(self, tone: str):
        """Set a compact status indicator color."""
        color_map = {
            "idle": COLORS["accent_success"],
            "progress": COLORS["accent_primary"],
            "warning": COLORS["accent_warning"],
            "error": COLORS["accent_error"],
        }
        self.status_dot.configure(text_color=color_map.get(tone, COLORS["text_muted"]))

    def _show_empty_state(
        self,
        title: str,
        body: str,
        action_text: Optional[str] = None,
        action_command: Optional[Any] = None,
        tone: str = "idle",
    ):
        """Show the centered table overlay for empty, loading, or error states."""
        self.empty_icon.configure(text="AppList", text_color=COLORS["accent_primary"])
        self.empty_title.configure(text=title)
        self.empty_body.configure(text=body)

        if action_text and action_command:
            self.empty_action.configure(text=action_text, command=action_command, state="normal")
            if not self.empty_action.winfo_ismapped():
                self.empty_action.pack(padx=28, pady=(0, 24))
        else:
            self.empty_action.pack_forget()

        self._set_status_tone(tone)
        self.empty_state_frame.place(relx=0.5, rely=0.52, anchor="center")
        self.empty_state_frame.lift()

    def _hide_empty_state(self):
        """Hide the centered table overlay when the grid has rows."""
        self.empty_state_frame.place_forget()

    def _clear_filters(self):
        """Reset all visible filters to their neutral states."""
        self.search_var.set("")
        self.filter_var.set("All Types")
        self.source_filter_var.set("All Sources")
        self.upgrade_filter_var.set("Any Upgrade State")
        self._apply_filters()
    
    # ══════════════════════════════════════════════════════════════════════════
    # SCANNING LOGIC
    # ══════════════════════════════════════════════════════════════════════════
    
    def _start_scan(self):
        """Start the scanning process in a background thread."""
        self.is_scanning = True
        self.scan_has_run = False
        self._set_status_tone("progress")
        self.scan_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self._set_export_buttons_enabled(False)
        self.progress_bar.set(0)
        self.progress_percent_label.configure(text="0%")
        self.count_label.configure(text="Scanning all configured sources")
        self._show_empty_state(
            "Scanning system",
            "Collecting registry, Store, Program Files, package-manager, Python, and winget details.",
            tone="progress",
        )
        
        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.applications = []
        self.filtered_apps = []
        self.tree_iid_to_index = {}
        
        # Reset stats
        self.stats_total.set_value("...")
        self.stats_desktop.set_value("...")
        self.stats_store.set_value("...")
        self.stats_unregistered.set_value("...")
        
        # Create scanner
        self.scanner = ApplicationScanner(
            progress_callback=self._update_progress,
            status_callback=self._update_status,
        )
        
        # Start background thread
        self.scan_thread = threading.Thread(target=self._run_scan, daemon=True)
        self.scan_thread.start()
    
    def _run_scan(self):
        """Execute the scan in background thread."""
        try:
            apps = self.scanner.scan_all()
            self.after(0, lambda: self._on_scan_complete(apps))
        except (OSError, PermissionError, subprocess.SubprocessError,
                json.JSONDecodeError, ValueError) as e:
            self.after(0, lambda: self._on_scan_error(str(e)))
    
    def _cancel_scan(self):
        """Cancel the ongoing scan."""
        if self.scanner:
            self.scanner.cancel()
        self.is_scanning = False
        self._update_status("Scan cancelled.")
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self._set_export_buttons_enabled(bool(self.filtered_apps))
        self._set_status_tone("warning")
        if not self.filtered_apps:
            self._show_empty_state(
                "Scan cancelled",
                "No inventory was captured. Run a fresh scan when you are ready.",
                action_text="Scan System",
                action_command=self._start_scan,
                tone="warning",
            )
    
    def _on_scan_complete(self, apps: List[Application]):
        """Handle scan completion."""
        was_cancelled = bool(self.scanner and self.scanner._cancelled)
        self.is_scanning = False
        self.scan_has_run = True
        self.applications = apps
        self.filtered_apps = apps.copy()
        
        # Update stats
        desktop_count = sum(1 for a in apps if a.app_type == "Desktop")
        store_count = sum(1 for a in apps if a.app_type == "Store App")
        other_count = sum(1 for a in apps if a.app_type not in ("Desktop", "Store App"))
        
        self.stats_total.set_value(str(len(apps)))
        self.stats_desktop.set_value(str(desktop_count))
        self.stats_store.set_value(str(store_count))
        self.stats_unregistered.set_value(str(other_count))
        
        # Populate treeview through the current filters.
        self._apply_filters()
        
        # Re-enable buttons
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self._set_export_buttons_enabled(bool(self.filtered_apps))
        
        if was_cancelled:
            self._update_status(f"Scan cancelled. Captured {len(apps)} applications before stopping.")
            self._set_status_tone("warning")
        else:
            self.progress_bar.set(1)
            self.progress_percent_label.configure(text="100%")
            self._update_status(f"Scan complete. Found {len(apps)} applications.")
            self._set_status_tone("idle")
    
    def _on_scan_error(self, error: str):
        """Handle scan error."""
        self.is_scanning = False
        messagebox.showerror("Scan Error", f"An error occurred during scanning:\n{error}")
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self._set_export_buttons_enabled(bool(self.filtered_apps))
        self.progress_bar.set(0)
        self.progress_percent_label.configure(text="0%")
        self._set_status_tone("error")
        self._show_empty_state(
            "Scan did not complete",
            "Review the error message, then run the scan again.",
            action_text="Scan System",
            action_command=self._start_scan,
            tone="error",
        )
        self._update_status("Scan failed. See error message.")
    
    def _update_progress(self, value: float, maximum: float = 100):
        """Update progress bar (thread-safe)."""
        ratio = 0 if maximum <= 0 else max(0, min(value / maximum, 1))
        percent = int(round(ratio * 100))
        self.after(0, lambda: (
            self.progress_bar.set(ratio),
            self.progress_percent_label.configure(text=f"{percent}%"),
        ))
    
    def _update_status(self, status: str):
        """Update status message (thread-safe)."""
        self.after(0, lambda: self.status_label.configure(text=status))
    
    # ══════════════════════════════════════════════════════════════════════════
    # FILTERING & SORTING
    # ══════════════════════════════════════════════════════════════════════════
    
    def _populate_treeview(self):
        """Populate treeview with filtered applications."""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_iid_to_index = {}
        
        # Add filtered apps
        for index, app in enumerate(self.filtered_apps):
            # Visual indicator for update available or ghost entry
            status = ""
            row_tags = ()
            if app.ghost:
                status = "Missing path"
                row_tags = ("ghost",)
            elif app.upgrade_available:
                status = app.upgrade_available
                row_tags = ("update",)

            iid = f"app-{index}"
            self.tree_iid_to_index[iid] = index
            
            self.tree.insert("", "end", iid=iid, values=(
                app.name,
                app.publisher,
                app.version,
                app.install_date,
                app.app_type,
                app.source,
                status,
                app.winget_id,
                app.estimated_size,
                app.architecture,
                app.install_location,
                app.uninstall_registry_key,
            ), tags=row_tags)
        
        # Update count
        if self.applications:
            self.count_label.configure(text=f"Showing {len(self.filtered_apps)} of {len(self.applications)}")
        elif self.scan_has_run:
            self.count_label.configure(text="0 applications found")
        else:
            self.count_label.configure(text="No scan performed yet")

        self._set_export_buttons_enabled(bool(self.filtered_apps) and not self.is_scanning)

        if self.is_scanning:
            self._show_empty_state(
                "Scanning system",
                "Collecting registry, Store, Program Files, package-manager, Python, and winget details.",
                tone="progress",
            )
        elif not self.applications and self.scan_has_run:
            self._show_empty_state(
                "No applications found",
                "The scan completed, but no matching applications were detected from the enabled sources.",
                action_text="Scan Again",
                action_command=self._start_scan,
                tone="warning",
            )
        elif not self.applications:
            self._show_empty_state(
                "No inventory yet",
                "Run a scan to discover installed desktop, Store, package-manager, and Python applications.",
                action_text="Scan System",
                action_command=self._start_scan,
            )
        elif not self.filtered_apps:
            self._show_empty_state(
                "No matches",
                "Clear the search or filters to return to the full inventory.",
                action_text="Clear filters",
                action_command=self._clear_filters,
                tone="warning",
            )
        else:
            self._hide_empty_state()
    
    def _apply_filters(self):
        """Apply search and category filters."""
        search_text = self.search_var.get().lower()
        filter_type = self.filter_var.get()
        source_filter = self.source_filter_var.get()
        upgrade_filter = self.upgrade_filter_var.get()
        
        self.filtered_apps = []
        
        for app in self.applications:
            # Search filter
            if search_text:
                searchable = (
                    f"{app.name} {app.publisher} {app.version} {app.install_location} "
                    f"{app.uninstall_registry_key} {app.source} {app.app_type} {app.winget_id}"
                ).lower()
                if search_text not in searchable:
                    continue
            
            # Category filter
            if filter_type == "Desktop" and app.app_type != "Desktop":
                continue
            elif filter_type == "Store" and app.app_type != "Store App":
                continue
            elif filter_type == "Unregistered" and app.app_type != "Desktop (Unregistered)":
                continue
            elif filter_type == "Chocolatey" and app.app_type != "Chocolatey":
                continue
            elif filter_type == "Scoop" and app.app_type != "Scoop":
                continue
            elif filter_type == "Python (pip)" and app.app_type != "Python Package":
                continue

            # Source filter
            source_value = (app.source or "").lower()
            if source_filter == "Registry" and source_value not in {"hklm64", "hklm32", "hkcu"}:
                continue
            elif source_filter == "Program Files" and source_value != "program files scan":
                continue
            elif source_filter == "Microsoft Store" and source_value != "microsoft store":
                continue
            elif source_filter == "Package Managers" and source_value not in {"chocolatey", "scoop"}:
                continue
            elif source_filter == "Python" and source_value != "python (pip)":
                continue
            elif source_filter == "Winget Matched" and not app.winget_id:
                continue

            # Upgrade/data-quality filter
            if upgrade_filter == "Updates Available" and not app.upgrade_available:
                continue
            elif upgrade_filter == "Missing Install Path" and not app.ghost:
                continue
            elif upgrade_filter == "Winget Matched" and not app.winget_id:
                continue
            elif upgrade_filter == "No Winget Match" and app.winget_id:
                continue
            
            self.filtered_apps.append(app)
        
        # Apply current sort
        self._apply_sort()
        
        # Update view
        self._populate_treeview()
    
    def _on_search_changed(self, *args):
        """Handle search text change."""
        self._apply_filters()
    
    def _on_filter_changed(self, *args):
        """Handle filter dropdown change."""
        self._apply_filters()
    
    def _sort_by_column(self, column: str):
        """Sort treeview by column."""
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        self._apply_sort()
        self._populate_treeview()
    
    def _apply_sort(self):
        """Apply current sort to filtered apps."""
        attr_map = {
            "name": "name",
            "publisher": "publisher",
            "version": "version",
            "install_date": "install_date",
            "install_location": "install_location",
            "registry_key": "uninstall_registry_key",
            "type": "app_type",
            "source": "source",
            "size": "estimated_size",
            "architecture": "architecture",
            "winget_id": "winget_id",
            "upgrade_available": "upgrade_available",
        }
        
        attr = attr_map.get(self.sort_column, "name")
        self.filtered_apps.sort(key=lambda x: getattr(x, attr, "").lower(), reverse=self.sort_reverse)

    def _ensure_exportable_rows(self) -> bool:
        """Return True when the current filtered view can be exported."""
        if not self.applications:
            self._update_status("Run a scan before exporting an inventory.")
            messagebox.showwarning("No Inventory", "Run a scan before exporting an inventory.")
            return False
        if not self.filtered_apps:
            self._update_status("No filtered rows available to export.")
            messagebox.showwarning(
                "No Matching Rows",
                "The current search and filters have no rows to export. Clear filters or search again.",
            )
            return False
        return True
    
    # ══════════════════════════════════════════════════════════════════════════
    # EXPORT FUNCTIONS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _export_txt(self):
        """Export applications to TXT file."""
        if not self._ensure_exportable_rows():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"AppList_Export_{timestamp}.txt"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=default_name,
            title="Export as Text File",
        )
        
        if not filepath:
            return
        
        try:
            write_txt_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to TXT.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")
            
        except OSError as e:
            self._update_status("TXT export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")
    
    def _export_csv(self):
        """Export applications to CSV file."""
        if not self._ensure_exportable_rows():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"AppList_Export_{timestamp}.csv"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=default_name,
            title="Export as CSV File",
        )
        
        if not filepath:
            return
        
        try:
            write_csv_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to CSV.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")
            
        except (OSError, csv.Error) as e:
            self._update_status("CSV export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_markdown(self):
        """Export applications to a Markdown report grouped by type."""
        if not self._ensure_exportable_rows():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown Files", "*.md"), ("All Files", "*.*")],
            initialfile=f"AppList_Export_{timestamp}.md",
            title="Export as Markdown Report",
        )
        if not filepath:
            return

        try:
            write_markdown_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to Markdown.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")

        except OSError as e:
            self._update_status("Markdown export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_json(self):
        """Export applications to AppList JSON (full schema, round-trippable)."""
        if not self._ensure_exportable_rows():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=f"AppList_Export_{timestamp}.json",
            title="Export as JSON",
        )
        if not filepath:
            return

        try:
            write_json_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to JSON.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")

        except (OSError, TypeError, ValueError) as e:
            self._update_status("JSON export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    # ══════════════════════════════════════════════════════════════════════════
    # CONTEXT MENU ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _export_winget(self):
        """Export apps with winget IDs as a winget import-compatible JSON file."""
        if not self._ensure_exportable_rows():
            return

        winget_apps = [a for a in self.filtered_apps if a.winget_id]
        if not winget_apps:
            self._update_status("No winget package IDs in the current filtered view.")
            messagebox.showwarning(
                "No Winget IDs",
                "None of the scanned applications could be matched to a winget package ID.\n\n"
                "Ensure winget is installed and run a fresh scan.",
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=f"WingetPackages_{timestamp}.json",
            title="Export Winget Package List",
        )
        if not filepath:
            return

        try:
            exported_count = write_winget_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {exported_count} winget packages.")
            messagebox.showinfo(
                "Export Complete",
                f"Exported {exported_count} matched packages to:\n{filepath}\n\n"
                f"To restore, run:\n  winget import -i \"{filepath}\"",
            )
        except (OSError, TypeError, ValueError) as e:
            self._update_status("Winget export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _lookup_winget(self):
        """Open winget app page (or search page) in default browser for selected app."""
        import webbrowser
        app = self._get_selected_app()
        if not app:
            return
        if app.winget_id:
            url = f"https://winstall.app/apps/{app.winget_id}"
        else:
            query = app.name.replace(" ", "+")
            url = f"https://winget.run/?q={query}"
        webbrowser.open(url)
        self._update_status(f"Opened winget lookup for {app.name}.")

    def _uninstall_app(self):
        """Uninstall the selected application using its uninstall string."""
        app = self._get_selected_app()
        if not app:
            return
        
        # Prefer uninstall_command if available
        uninstall_str = app.uninstall_command or app.uninstall_registry_key
        if not uninstall_str:
            messagebox.showwarning("No Uninstall", f"No uninstall information available for {app.name}.")
            return
        
        # Confirm before uninstalling
        response = messagebox.askyesno(
            "Confirm Uninstall",
            f"Are you sure you want to uninstall {app.name}?\n\nCommand:\n{uninstall_str}",
        )
        if not response:
            return
        
        try:
            if app.app_type == "Store App" and uninstall_str.startswith("Remove-AppxPackage "):
                package_name = uninstall_str[len("Remove-AppxPackage "):].strip()
                command = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Remove-AppxPackage -Package $args[0]",
                    package_name,
                ]
            else:
                command = split_windows_command_line(uninstall_str)
                if not command:
                    raise ValueError("No executable found in uninstall command.")
                if is_shell_host_command(command[0]):
                    raise ValueError(
                        "Shell-based uninstall commands are not executed automatically. "
                        "Copy the uninstall command and review it before running manually."
                    )

            subprocess.Popen(
                command,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._update_status(f"Uninstall command launched for {app.name}.")
            messagebox.showinfo("Uninstall", f"Uninstall command for {app.name} executed.\nPlease complete the uninstall wizard.")
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            messagebox.showerror("Uninstall Error", f"Failed to execute uninstall:\n{e}")

    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self._sync_context_menu_state(self._get_selected_app())
            self.context_menu.post(event.x_root, event.y_root)

    def _sync_context_menu_state(self, app: Optional[Application]):
        """Disable context actions that are not valid for the selected row."""
        if not app:
            return
        has_location = bool(app.install_location and os.path.exists(app.install_location))
        has_registry = bool(app.uninstall_registry_key)
        has_uninstall = bool(app.uninstall_command)

        self.context_menu.entryconfig(1, state="normal" if app.install_location else "disabled")
        self.context_menu.entryconfig(2, state="normal" if has_registry else "disabled")
        self.context_menu.entryconfig(3, state="normal" if has_uninstall else "disabled")
        self.context_menu.entryconfig(5, state="normal" if has_location else "disabled")
        self.context_menu.entryconfig(6, state="normal" if has_registry else "disabled")
        self.context_menu.entryconfig(9, state="normal" if has_uninstall else "disabled")
    
    def _get_selected_app(self) -> Optional[Application]:
        """Get the currently selected application."""
        selection = self.tree.selection()
        if not selection:
            return None
        
        index = self.tree_iid_to_index.get(selection[0])
        if index is not None and 0 <= index < len(self.filtered_apps):
            return self.filtered_apps[index]

        return None
    
    def _copy_name(self):
        """Copy application name to clipboard."""
        app = self._get_selected_app()
        if app:
            self._copy_to_clipboard(app.name, "Application name")
    
    def _copy_location(self):
        """Copy install location to clipboard."""
        app = self._get_selected_app()
        if app and app.install_location:
            self._copy_to_clipboard(app.install_location, "Install location")
    
    def _copy_registry(self):
        """Copy registry key to clipboard."""
        app = self._get_selected_app()
        if app and app.uninstall_registry_key:
            self._copy_to_clipboard(app.uninstall_registry_key, "Registry key")

    def _copy_to_clipboard(self, value: str, label: str):
        """Copy a value and reflect the action in the status strip."""
        self.clipboard_clear()
        self.clipboard_append(value)
        self._update_status(f"{label} copied to clipboard.")
    
    def _open_location(self):
        """Open install location in Explorer."""
        app = self._get_selected_app()
        if app and app.install_location and os.path.exists(app.install_location):
            os.startfile(app.install_location)
            self._update_status(f"Opened install location for {app.name}.")
        else:
            messagebox.showinfo("Not Available", "Install location not available or does not exist.")

    def _copy_uninstall(self):
        """Copy uninstall command to clipboard."""
        app = self._get_selected_app()
        if app and app.uninstall_command:
            self._copy_to_clipboard(app.uninstall_command, "Uninstall command")
        else:
            messagebox.showinfo("Not Available", "No uninstall command available for this application.")

    def _open_registry_key(self):
        """Open the application's registry key in Regedit."""
        app = self._get_selected_app()
        if not app or not app.uninstall_registry_key:
            messagebox.showinfo("Not Available", "No registry key available for this application.")
            return
        reg_key = app.uninstall_registry_key
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Applets\Regedit",
                0, winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, "LastKey", 0, winreg.REG_SZ, reg_key)
            subprocess.Popen(["regedit.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
            self._update_status(f"Opened registry key for {app.name}.")
        except (OSError, PermissionError, subprocess.SubprocessError):
            self.clipboard_clear()
            self.clipboard_append(reg_key)
            self._update_status("Registry key copied to clipboard.")
            messagebox.showinfo(
                "Registry Key Copied",
                f"Could not open Regedit automatically.\n\n"
                f"Key copied to clipboard:\n{reg_key}",
            )
    
    def _on_double_click(self, event):
        """Handle double-click on item."""
        self._open_location()
    
    def _on_close(self):
        """Handle window close."""
        if self.scanner:
            self.scanner.cancel()
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def build_cli_parser() -> argparse.ArgumentParser:
    """Build the headless CLI parser."""
    parser = argparse.ArgumentParser(
        prog="AppList.py",
        description="Scan installed Windows applications and export an inventory without launching the GUI.",
    )
    parser.add_argument(
        "--export",
        choices=["txt", "csv", "md", "markdown", "json", "winget"],
        required=True,
        help="Export format to write.",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output file path.",
    )
    parser.add_argument(
        "--include",
        default="all",
        help=(
            "Comma-separated sources to scan. Supported: all, desktop, registry, "
            "store, program_files, chocolatey, scoop, pip, winget."
        ),
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} v{APP_VERSION}")
    return parser


def run_cli(argv: List[str]) -> int:
    """Run AppList in headless CLI mode."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    export_format = "markdown" if args.export == "md" else args.export

    try:
        include_sources = parse_include_sources(args.include)
    except ValueError as e:
        parser.error(str(e))

    if export_format == "winget":
        include_sources.add("winget")

    output_path = Path(args.output).expanduser()
    if output_path.parent and str(output_path.parent) not in ("", "."):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def status(message: str):
        print(message, file=sys.stderr)

    scanner = ApplicationScanner(status_callback=status)
    apps = scanner.scan_all(include_sources=include_sources)

    writers = {
        "txt": write_txt_export,
        "csv": write_csv_export,
        "markdown": write_markdown_export,
        "json": write_json_export,
        "winget": write_winget_export,
    }

    try:
        result = writers[export_format](apps, str(output_path))
    except (OSError, csv.Error, TypeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    exported_count = result if isinstance(result, int) else len(apps)
    print(f"Exported {exported_count} applications to {output_path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Application entry point."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        return run_cli(argv)

    # Set DPI awareness for sharp rendering on high-DPI displays
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError, ValueError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError, ValueError):
            pass
    
    app = AppList()
    app.mainloop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
