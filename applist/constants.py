"""Configuration constants for AppList."""

import os
import shlex
import ctypes
import winreg
from typing import List

# Catppuccin Mocha Theme Colors
# https://github.com/catppuccin/catppuccin
COLORS = {
    "bg_primary": "#1e1e2e",       # Base
    "bg_secondary": "#181825",     # Mantle
    "bg_tertiary": "#11111b",      # Crust
    "bg_card": "#181825",          # Mantle
    "bg_elevated": "#313244",      # Surface0
    "bg_hover": "#45475a",         # Surface1
    "bg_pressed": "#11111b",       # Crust
    "bg_input": "#181825",         # Mantle (input fields)
    "accent_primary": "#89b4fa",   # Blue
    "accent_secondary": "#74c7ec", # Sapphire
    "accent_glow": "#7287fd",      # Lavender
    "accent_success": "#a6e3a1",   # Green
    "accent_warning": "#f9e2af",   # Yellow
    "accent_error": "#f38ba8",     # Red
    "text_primary": "#cdd6f4",     # Text
    "text_secondary": "#bac2de",   # Subtext1
    "text_muted": "#a6adc8",       # Subtext0
    "border_subtle": "#313244",    # Surface0
    "border_strong": "#45475a",    # Surface1
    "border_accent": "#89b4fa",    # Blue
    "table_header": "#181825",     # Mantle
    "table_row_alt": "#1e1e2e",    # Base
    "table_selected": "#585b70",   # Surface2
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
    "startup",
    "portable",
    "drivers",
    "features",
    "wsl",
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
    "startup": {"startup"},
    "portable": {"portable"},
    "drivers": {"drivers"},
    "features": {"features"},
    "wsl": {"wsl"},
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
    "Pinned",
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


OEM_BLOATWARE_PUBLISHERS = {
    "cyberlink",
    "corel corporation",
    "corel",
    "wildtangent",
    "playtime",
    "playtime games",
    "mcafee",
    "mcafee, inc.",
    "norton",
    "norton lifelock",
    "nortonlifelock inc.",
    "symantec",
    "symantec corporation",
    "avast software",
    "avg technologies",
    "trend micro",
    "eset",
    "webroot",
    "panda security",
    "bitdefender",
    "f-secure",
    "kaspersky",
    "dell inc.",
    "dell",
    "dell technologies",
    "hp inc.",
    "hp",
    "hewlett-packard",
    "lenovo",
    "asus",
    "acer",
    "acer incorporated",
    "samsung electronics",
    "toshiba",
    "tobii",
    "tobii technology",
    "tobii ab",
    "dolby laboratories",
    "dolby",
    "waves audio",
    "realtek",
    "realtek semiconductor",
    "fitbit",
    "fitbit, inc.",
    "booking.com",
    "spotify ab",
    "amazon.com services llc",
    "king",
    "king.com",
    "bubble witch",
    "candy crush",
    "disney",
    "microsoft advertising",
    "dropbox, inc.",
    "linkedin",
    "skype",
}

OEM_BLOATWARE_NAME_PATTERNS = [
    "trial",
    "trialware",
    "mcafee",
    "norton",
    "wildtangent",
    "candy crush",
    "bubble witch",
    "hidden city",
    "march of empires",
    "disney magic",
    "farmville",
    "cooking fever",
    "phototastic",
    "xbox game bar",
]
