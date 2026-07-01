"""GUI components for AppList — customtkinter-based dark-themed application window."""

import os
import subprocess
import threading
import webbrowser
import json
import csv
from datetime import datetime
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
from typing import Optional, Dict, List, Any

import customtkinter as ctk

from . import APP_NAME, APP_VERSION, APP_SUBTITLE
from .constants import (
    COLORS,
    TYPE_FILTERS,
    SOURCE_FILTERS,
    UPGRADE_FILTERS,
    split_windows_command_line,
    is_shell_host_command,
)
from .models import Application, ScanDiagnostic
from .scanner import ApplicationScanner
from .exports import (
    write_txt_export,
    write_csv_export,
    write_markdown_export,
    write_json_export,
    write_winget_export,
    write_html_export,
    write_pip_requirements_export,
    write_choco_export,
    write_powershell_export,
    write_restore_bundle_export,
    diff_json_snapshots,
    write_diff_report,
)

PAGE_SIZE = 500


def get_page_bounds(total_rows: int, current_page: int, page_size: int = PAGE_SIZE):
    """Return a clamped page index plus start/end offsets for a filtered row count."""
    if page_size <= 0:
        page_size = PAGE_SIZE
    if total_rows <= 0:
        return 0, 0, 0
    max_page = (total_rows - 1) // page_size
    page = max(0, min(current_page, max_page))
    start = page * page_size
    end = min(start + page_size, total_rows)
    return page, start, end


def get_source_group_counts(apps: List[Application]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for app in apps:
        source = app.source or "Unknown"
        counts[source] = counts.get(source, 0) + 1
    return counts


try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]


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
# MAIN APPLICATION WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class AppListWindow(ctk.CTk):
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
        self.scan_diagnostics: List[ScanDiagnostic] = []
        self.tree_iid_to_index: Dict[str, int] = {}
        self.scan_thread = None
        self.sort_column = "name"
        self.sort_reverse = False
        self.current_page = 0
        self.page_size = PAGE_SIZE
        self.group_by_source_var = tk.BooleanVar(value=False)
        self.group_by_var = tk.StringVar(value="None")
        self.is_scanning = False
        self.scan_has_run = False
        self._baseline_path = os.path.join(os.environ.get("APPDATA", ""), "AppList", "baseline.json")
        self._layout_path = os.path.join(os.environ.get("APPDATA", ""), "AppList", "layout.json")
        self._all_columns = (
            "name", "publisher", "version", "install_date", "last_used_date",
            "type", "source", "upgrade_available", "pin_status", "winget_id",
            "sha256_hash", "virustotal", "consistency", "size", "architecture",
            "install_location", "registry_key",
        )
        self._default_visible = {
            "name", "publisher", "version", "install_date", "type", "source",
            "upgrade_available", "winget_id", "size",
        }
        self._visible_columns = self._load_column_layout()

        # Build UI
        self._create_header()
        self._create_stats_panel()
        self._create_toolbar()
        self._create_main_content()
        self._create_status_bar()
        self._set_export_buttons_enabled(False)
        self._update_pagination_controls(0, 0)
        self._show_empty_state(
            "No inventory yet",
            "Run a scan to discover installed apps, package inventory, and recent-use signals.",
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
            import ctypes as _ctypes
            self.update()
            hwnd = _ctypes.windll.user32.GetParent(self.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            _ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                _ctypes.byref(_ctypes.c_int(1)), _ctypes.sizeof(_ctypes.c_int)
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

        group_label = ctk.CTkLabel(
            top_row,
            text="Group:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        group_label.pack(side="left", padx=(10, 4))

        self.group_by_dropdown = ctk.CTkOptionMenu(
            top_row,
            values=["None", "Source", "Publisher", "Install Year", "Drive"],
            variable=self.group_by_var,
            command=lambda _: self._on_grouping_changed(),
            width=130,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_primary"],
            button_hover_color=COLORS["accent_secondary"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["accent_primary"],
        )
        self.group_by_dropdown.pack(side="left")

        export_hint = ctk.CTkLabel(
            bottom_row,
            text="Exports use the current filtered view.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        export_hint.pack(side="left")

        self.pagination_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        self.pagination_frame.pack(side="left", padx=(18, 0))

        self.prev_page_btn = SecondaryButton(
            self.pagination_frame, text="Previous", width=92, command=self._previous_page
        )
        self.prev_page_btn.pack(side="left", padx=(0, 6))

        self.page_label = ctk.CTkLabel(
            self.pagination_frame,
            text="Page 0/0",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORS["text_muted"],
        )
        self.page_label.pack(side="left", padx=(0, 6))

        self.next_page_btn = SecondaryButton(
            self.pagination_frame, text="Next", width=72, command=self._next_page
        )
        self.next_page_btn.pack(side="left")

        export_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        export_frame.pack(side="right")

        self.export_txt_btn = SecondaryButton(export_frame, text="TXT", width=66, command=self._export_txt)
        self.export_txt_btn.pack(side="left", padx=(0, 6))

        self.export_csv_btn = SecondaryButton(export_frame, text="CSV", width=66, command=self._export_csv)
        self.export_csv_btn.pack(side="left", padx=(0, 6))

        self.export_md_btn = SecondaryButton(export_frame, text="MD", width=60, command=self._export_markdown)
        self.export_md_btn.pack(side="left", padx=(0, 6))

        self.export_json_btn = SecondaryButton(export_frame, text="JSON", width=70, command=self._export_json)
        self.export_json_btn.pack(side="left", padx=(0, 6))

        self.export_html_btn = SecondaryButton(export_frame, text="HTML", width=70, command=self._export_html)
        self.export_html_btn.pack(side="left", padx=(0, 6))

        self.export_winget_btn = SecondaryButton(export_frame, text="Winget", width=80, command=self._export_winget)
        self.export_winget_btn.pack(side="left", padx=(0, 6))

        self.export_pip_btn = SecondaryButton(export_frame, text="pip", width=60, command=self._export_pip)
        self.export_pip_btn.pack(side="left", padx=(0, 6))

        self.export_choco_btn = SecondaryButton(export_frame, text="Choco", width=72, command=self._export_choco)
        self.export_choco_btn.pack(side="left", padx=(0, 6))

        self.export_ps1_btn = SecondaryButton(export_frame, text="PS1", width=54, command=self._export_ps1)
        self.export_ps1_btn.pack(side="left", padx=(0, 6))

        self.export_bundle_btn = SecondaryButton(export_frame, text="Bundle", width=84, command=self._export_bundle)
        self.export_bundle_btn.pack(side="left", padx=(0, 6))

        self.diagnostics_btn = SecondaryButton(export_frame, text="Diag", width=60, command=self._show_diagnostics)
        self.diagnostics_btn.pack(side="left", padx=(0, 6))

        self.baseline_btn = SecondaryButton(export_frame, text="Baseline", width=84, command=self._save_baseline)
        self.baseline_btn.pack(side="left", padx=(0, 6))

        self.compare_btn = SecondaryButton(export_frame, text="Compare", width=84, command=self._compare_baseline)
        self.compare_btn.pack(side="left", padx=(0, 6))

        self.columns_btn = SecondaryButton(export_frame, text="Columns", width=84, command=self._show_column_chooser)
        self.columns_btn.pack(side="left")

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
            "name", "publisher", "version", "install_date", "last_used_date",
            "type", "source", "upgrade_available", "pin_status", "winget_id",
            "sha256_hash", "virustotal", "consistency", "size", "architecture", "install_location", "registry_key",
        )

        # Create treeview with scrollbar
        tree_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Scrollbars
        y_scroll = ctk.CTkScrollbar(
            tree_frame, orientation="vertical", width=12, corner_radius=4,
            fg_color=COLORS["bg_secondary"], button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
        )
        x_scroll = ctk.CTkScrollbar(
            tree_frame, orientation="horizontal", height=12, corner_radius=4,
            fg_color=COLORS["bg_secondary"], button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["bg_hover"],
        )

        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="tree headings",
            style="Premium.Treeview",
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set,
        )

        y_scroll.configure(command=self.tree.yview)
        x_scroll.configure(command=self.tree.xview)

        # Configure columns
        column_config = {
            "name": ("Application", 260),
            "publisher": ("Publisher", 180),
            "version": ("Version", 100),
            "install_date": ("Installed", 105),
            "last_used_date": ("Last Used", 145),
            "type": ("Type", 132),
            "source": ("Source", 132),
            "upgrade_available": ("Upgrade", 175),
            "pin_status": ("Pin", 120),
            "winget_id": ("Winget ID", 200),
            "sha256_hash": ("SHA-256", 240),
            "virustotal": ("VirusTotal", 105),
            "consistency": ("Consistency", 170),
            "size": ("Size", 90),
            "architecture": ("Arch", 80),
            "install_location": ("Location", 280),
            "registry_key": ("Registry Key", 320),
        }

        for col, (heading, width) in column_config.items():
            self.tree.heading(col, text=heading, anchor="w", command=lambda c=col: self._sort_by_column(c))
            self.tree.column(col, width=width, minwidth=80, anchor="w")
        self.tree.heading("#0", text="Group", anchor="w")
        self.tree.column("#0", width=0, minwidth=0, stretch=False, anchor="w")

        self._apply_column_visibility()

        # Pack treeview and scrollbars
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.tag_configure("ghost", foreground=COLORS["accent_warning"])
        self.tree.tag_configure("update", foreground=COLORS["accent_secondary"])
        self.tree.tag_configure("group", foreground=COLORS["accent_primary"])

        self.empty_state_frame = ctk.CTkFrame(content_frame, fg_color="transparent", corner_radius=0, border_width=0)
        self.empty_icon = ctk.CTkLabel(
            self.empty_state_frame, text="AppList",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["accent_primary"],
        )
        self.empty_icon.pack(padx=28, pady=(24, 8))

        self.empty_title = ctk.CTkLabel(
            self.empty_state_frame, text="No inventory yet",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self.empty_title.pack(padx=28)

        self.empty_body = ctk.CTkLabel(
            self.empty_state_frame, text="Run a scan to discover installed applications.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"], wraplength=420, justify="center",
        )
        self.empty_body.pack(padx=28, pady=(8, 18))

        self.empty_action = SecondaryButton(
            self.empty_state_frame, text="Scan System", width=142, command=self._start_scan,
        )
        self.empty_action.pack(padx=28, pady=(0, 24))

        # Context menu
        self.context_menu = tk.Menu(
            self, tearoff=0,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["bg_hover"], activeforeground=COLORS["text_primary"],
            disabledforeground=COLORS["text_muted"],
        )
        self.context_menu.add_command(label="Copy Name", command=self._copy_name)
        self.context_menu.add_command(label="Copy Install Location", command=self._copy_location)
        self.context_menu.add_command(label="Copy Registry Key", command=self._copy_registry)
        self.context_menu.add_command(label="Copy Uninstall Command", command=self._copy_uninstall)
        self.context_menu.add_command(label="Copy SHA-256", command=self._copy_sha256)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open Install Location", command=self._open_location)
        self.context_menu.add_command(label="Open Registry Key in Regedit", command=self._open_registry_key)
        self.context_menu.add_command(label="Lookup on Winget", command=self._lookup_winget)
        self.context_menu.add_command(label="Open VirusTotal Report", command=self._open_virustotal)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Uninstall", command=self._uninstall_app)

        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _create_status_bar(self):
        """Create the status bar at the bottom."""
        status_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=52)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)

        inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=30)

        self.status_dot = ctk.CTkLabel(inner, text="●", font=ctk.CTkFont(size=12), text_color=COLORS["accent_success"])
        self.status_dot.pack(side="left", pady=13, padx=(0, 10))

        self.status_label = ctk.CTkLabel(
            inner, text="Ready to scan",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        self.status_label.pack(side="left", pady=13)

        self.count_label = ctk.CTkLabel(
            inner, text="No scan performed yet",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self.count_label.pack(side="left", padx=(22, 0), pady=13)

        self.progress_percent_label = ctk.CTkLabel(
            inner, text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["accent_primary"],
        )
        self.progress_percent_label.pack(side="right", pady=13)

        self.progress_bar = ctk.CTkProgressBar(
            inner, width=260, height=6,
            fg_color=COLORS["bg_tertiary"], progress_color=COLORS["accent_primary"], corner_radius=3,
        )
        self.progress_bar.pack(side="right", padx=(12, 12), pady=13)
        self.progress_bar.set(0)

        progress_label = ctk.CTkLabel(
            inner, text="Progress",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        progress_label.pack(side="right", pady=13)

    # ══════════════════════════════════════════════════════════════════════════
    # STATE HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _set_export_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for button in (
            self.export_txt_btn, self.export_csv_btn, self.export_md_btn,
            self.export_json_btn, self.export_winget_btn, self.export_html_btn,
            self.export_pip_btn, self.export_choco_btn, self.export_ps1_btn,
            self.export_bundle_btn, self.baseline_btn, self.compare_btn,
        ):
            button.configure(state=state)

    def _update_pagination_controls(self, start: int, end: int):
        total = len(self.filtered_apps)
        page_count = 0 if total == 0 else ((total - 1) // self.page_size) + 1
        if total == 0:
            self.page_label.configure(text="Page 0/0")
        else:
            self.page_label.configure(
                text=f"Page {self.current_page + 1}/{page_count} ({start + 1}-{end})"
            )

        can_page = total > self.page_size and not self.is_scanning
        self.prev_page_btn.configure(state="normal" if can_page and self.current_page > 0 else "disabled")
        self.next_page_btn.configure(
            state="normal" if can_page and self.current_page < page_count - 1 else "disabled"
        )

    def _set_status_tone(self, tone: str):
        color_map = {
            "idle": COLORS["accent_success"],
            "progress": COLORS["accent_primary"],
            "warning": COLORS["accent_warning"],
            "error": COLORS["accent_error"],
        }
        self.status_dot.configure(text_color=color_map.get(tone, COLORS["text_muted"]))

    def _show_empty_state(self, title: str, body: str,
                          action_text: Optional[str] = None, action_command: Optional[Any] = None,
                          tone: str = "idle"):
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
        self.empty_state_frame.place_forget()

    def _clear_filters(self):
        self.search_var.set("")
        self.filter_var.set("All Types")
        self.source_filter_var.set("All Sources")
        self.upgrade_filter_var.set("Any Upgrade State")
        self.current_page = 0
        self._apply_filters()

    # ══════════════════════════════════════════════════════════════════════════
    # SCANNING LOGIC
    # ══════════════════════════════════════════════════════════════════════════

    def _start_scan(self):
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
            "Collecting registry, Store, package-manager, winget, and recent-use details.",
            tone="progress",
        )

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.applications = []
        self.filtered_apps = []
        self.scan_diagnostics = []
        self.tree_iid_to_index = {}
        self.current_page = 0

        self.stats_total.set_value("...")
        self.stats_desktop.set_value("...")
        self.stats_store.set_value("...")
        self.stats_unregistered.set_value("...")

        self.scanner = ApplicationScanner(
            progress_callback=self._update_progress,
            status_callback=self._update_status,
        )

        self.scan_thread = threading.Thread(target=self._run_scan, daemon=True)
        self.scan_thread.start()

    def _run_scan(self):
        try:
            apps = self.scanner.scan_all()
            self.after(0, lambda: self._on_scan_complete(apps))
        except (OSError, PermissionError, subprocess.SubprocessError,
                json.JSONDecodeError, ValueError) as e:
            self.after(0, lambda: self._on_scan_error(str(e)))

    def _cancel_scan(self):
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
                action_text="Scan System", action_command=self._start_scan, tone="warning",
            )

    def _on_scan_complete(self, apps: List[Application]):
        was_cancelled = bool(self.scanner and self.scanner._cancelled)
        self.is_scanning = False
        self.scan_has_run = True
        self.applications = apps
        self.filtered_apps = apps.copy()
        self.scan_diagnostics = self.scanner.scan_diagnostics if self.scanner else []
        self.current_page = 0

        desktop_count = sum(1 for a in apps if a.app_type == "Desktop")
        store_count = sum(1 for a in apps if a.app_type == "Store App")
        other_count = sum(1 for a in apps if a.app_type not in ("Desktop", "Store App"))

        self.stats_total.set_value(str(len(apps)))
        self.stats_desktop.set_value(str(desktop_count))
        self.stats_store.set_value(str(store_count))
        self.stats_unregistered.set_value(str(other_count))

        self._apply_filters()

        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self._set_export_buttons_enabled(bool(self.filtered_apps))
        self.diagnostics_btn.configure(state="normal" if self.scan_diagnostics else "disabled")
        self._save_scan_log()

        if was_cancelled:
            self._update_status(f"Scan cancelled. Captured {len(apps)} applications before stopping.")
            self._set_status_tone("warning")
        else:
            self.progress_bar.set(1)
            self.progress_percent_label.configure(text="100%")
            diagnostic_count = sum(
                1 for diagnostic in self.scan_diagnostics
                if diagnostic.status in {"skipped", "warning", "failed"} or diagnostic.warnings
            )
            if diagnostic_count:
                self._update_status(
                    f"Scan complete with {diagnostic_count} diagnostic notices. "
                    f"Found {len(apps)} applications."
                )
                self._set_status_tone("warning")
            else:
                self._update_status(f"Scan complete. Found {len(apps)} applications.")
                self._set_status_tone("idle")

    def _on_scan_error(self, error: str):
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
            action_text="Scan System", action_command=self._start_scan, tone="error",
        )
        self._update_status("Scan failed. See error message.")

    def _update_progress(self, value: float, maximum: float = 100):
        ratio = 0 if maximum <= 0 else max(0, min(value / maximum, 1))
        percent = int(round(ratio * 100))
        self.after(0, lambda: (
            self.progress_bar.set(ratio),
            self.progress_percent_label.configure(text=f"{percent}%"),
        ))

    def _update_status(self, status: str):
        self.after(0, lambda: self.status_label.configure(text=status))

    # ══════════════════════════════════════════════════════════════════════════
    # FILTERING & SORTING
    # ══════════════════════════════════════════════════════════════════════════

    def _get_group_key_func(self):
        mode = self.group_by_var.get()
        if mode == "Source":
            return lambda app: app.source or "Unknown"
        elif mode == "Publisher":
            return lambda app: app.publisher or "(No Publisher)"
        elif mode == "Install Year":
            return lambda app: app.install_date[:4] if app.install_date and len(app.install_date) >= 4 else "(Unknown Year)"
        elif mode == "Drive":
            return lambda app: (app.install_location[:3] if app.install_location and len(app.install_location) >= 3 and app.install_location[1] == ":" else "(No Location)")
        return None

    def _populate_treeview(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_iid_to_index = {}

        self.current_page, start, end = get_page_bounds(
            len(self.filtered_apps), self.current_page, self.page_size
        )
        page_apps = self.filtered_apps[start:end]

        self._sync_group_column()
        group_key_func = self._get_group_key_func()
        if group_key_func is not None:
            self._populate_grouped_rows(page_apps, start, group_key_func)
        else:
            self._populate_flat_rows(page_apps, start)

        if self.applications:
            if self.filtered_apps:
                self.count_label.configure(
                    text=f"Showing {start + 1}-{end} of {len(self.filtered_apps)} filtered / {len(self.applications)} total"
                )
            else:
                self.count_label.configure(text=f"Showing 0 of {len(self.applications)}")
        elif self.scan_has_run:
            self.count_label.configure(text="0 applications found")
        else:
            self.count_label.configure(text="No scan performed yet")

        self._set_export_buttons_enabled(bool(self.filtered_apps) and not self.is_scanning)
        self._update_pagination_controls(start, end)

        if self.is_scanning:
            self._show_empty_state(
                "Scanning system",
                "Collecting registry, Store, package-manager, winget, and recent-use details.",
                tone="progress",
            )
        elif not self.applications and self.scan_has_run:
            self._show_empty_state(
                "No applications found",
                "The scan completed, but no matching applications were detected from the enabled sources.",
                action_text="Scan Again", action_command=self._start_scan, tone="warning",
            )
        elif not self.applications:
            self._show_empty_state(
                "No inventory yet",
                "Run a scan to discover installed apps, package inventory, and recent-use signals.",
                action_text="Scan System", action_command=self._start_scan,
            )
        elif not self.filtered_apps:
            self._show_empty_state(
                "No matches",
                "Clear the search or filters to return to the full inventory.",
                action_text="Clear filters", action_command=self._clear_filters, tone="warning",
            )
        else:
            self._hide_empty_state()

    def _sync_group_column(self):
        if self.group_by_source_var.get():
            self.tree.column("#0", width=190, minwidth=130, stretch=False, anchor="w")
        else:
            self.tree.column("#0", width=0, minwidth=0, stretch=False, anchor="w")

    def _row_values(self, app: Application):
        status = ""
        row_tags = ()
        if app.ghost:
            status = "Missing path"
            row_tags = ("ghost",)
        elif app.upgrade_available:
            status = app.upgrade_available
            row_tags = ("update",)

        values = (
            app.name, app.publisher, app.version, app.install_date,
            app.last_used_date,
            app.app_type, app.source, status, app.pin_status,
            app.winget_id, app.sha256_hash, "Report" if app.virustotal_url else "",
            app.consistency_status,
            app.estimated_size, app.architecture,
            app.install_location, app.uninstall_registry_key,
        )
        return values, row_tags

    def _populate_flat_rows(self, page_apps: List[Application], start: int):
        for offset, app in enumerate(page_apps):
            index = start + offset
            values, row_tags = self._row_values(app)
            iid = f"app-{index}"
            self.tree_iid_to_index[iid] = index
            self.tree.insert("", "end", iid=iid, text="", values=values, tags=row_tags)

    def _populate_grouped_rows(self, page_apps: List[Application], start: int, key_func=None):
        if key_func is None:
            key_func = lambda app: app.source or "Unknown"

        group_counts: Dict[str, int] = {}
        for app in self.filtered_apps:
            g = key_func(app)
            group_counts[g] = group_counts.get(g, 0) + 1

        group_nodes: Dict[str, str] = {}
        blank_values = ("", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "")

        for offset, app in enumerate(page_apps):
            index = start + offset
            group = key_func(app)
            if group not in group_nodes:
                group_iid = f"group-{len(group_nodes)}-{self._normalize_tree_iid(group)}"
                group_nodes[group] = group_iid
                self.tree.insert(
                    "",
                    "end",
                    iid=group_iid,
                    text=f"{group} ({group_counts.get(group, 0)})",
                    values=blank_values,
                    open=True,
                    tags=("group",),
                )

            values, row_tags = self._row_values(app)
            iid = f"app-{index}"
            self.tree_iid_to_index[iid] = index
            self.tree.insert(group_nodes[group], "end", iid=iid, text="", values=values, tags=row_tags)

    def _normalize_tree_iid(self, value: str) -> str:
        return "".join(ch if ch.isalnum() else "-" for ch in value.lower())[:40] or "unknown"

    def _previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._populate_treeview()

    def _next_page(self):
        page_count = 0 if not self.filtered_apps else ((len(self.filtered_apps) - 1) // self.page_size) + 1
        if self.current_page < page_count - 1:
            self.current_page += 1
            self._populate_treeview()

    def _apply_filters(self):
        self.current_page = 0
        search_text = self.search_var.get().lower()
        filter_type = self.filter_var.get()
        source_filter = self.source_filter_var.get()
        upgrade_filter = self.upgrade_filter_var.get()

        self.filtered_apps = []

        for app in self.applications:
            if search_text:
                searchable = (
                    f"{app.name} {app.publisher} {app.version} {app.install_location} "
                    f"{app.uninstall_registry_key} {app.source} {app.app_type} {app.winget_id} "
                    f"{app.last_used_date} {app.executable_path} {app.sha256_hash} {app.virustotal_url} "
                    f"{app.consistency_status}"
                ).lower()
                if search_text not in searchable:
                    continue

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

            if upgrade_filter == "Updates Available" and not app.upgrade_available:
                continue
            elif upgrade_filter == "Pinned" and not app.pin_status:
                continue
            elif upgrade_filter == "Missing Install Path" and not app.ghost:
                continue
            elif upgrade_filter == "Winget Matched" and not app.winget_id:
                continue
            elif upgrade_filter == "No Winget Match" and app.winget_id:
                continue

            self.filtered_apps.append(app)

        self._apply_sort()
        self._populate_treeview()

    def _on_search_changed(self, *args):
        self._apply_filters()

    def _on_filter_changed(self, *args):
        self._apply_filters()

    def _on_grouping_changed(self):
        self.group_by_source_var.set(self.group_by_var.get() != "None")
        self.current_page = 0
        self._populate_treeview()

    def _sort_by_column(self, column: str):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self._apply_sort()
        self._populate_treeview()

    def _apply_sort(self):
        attr_map = {
            "name": "name", "publisher": "publisher", "version": "version",
            "install_date": "install_date", "last_used_date": "last_used_date",
            "install_location": "install_location",
            "registry_key": "uninstall_registry_key", "type": "app_type",
            "source": "source", "size": "estimated_size", "architecture": "architecture",
            "winget_id": "winget_id", "upgrade_available": "upgrade_available",
            "pin_status": "pin_status", "sha256_hash": "sha256_hash",
            "virustotal": "virustotal_url", "consistency": "consistency_status",
        }
        attr = attr_map.get(self.sort_column, "name")
        self.filtered_apps.sort(key=lambda x: getattr(x, attr, "").lower(), reverse=self.sort_reverse)

    def _ensure_exportable_rows(self) -> bool:
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
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=f"AppList_Export_{timestamp}.txt", title="Export as Text File",
        )
        if not filepath:
            return
        try:
            write_txt_export(self.filtered_apps, filepath, self.scan_diagnostics)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to TXT.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")
        except OSError as e:
            self._update_status("TXT export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_csv(self):
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"AppList_Export_{timestamp}.csv", title="Export as CSV File",
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
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".md", filetypes=[("Markdown Files", "*.md"), ("All Files", "*.*")],
            initialfile=f"AppList_Export_{timestamp}.md", title="Export as Markdown Report",
        )
        if not filepath:
            return
        try:
            write_markdown_export(self.filtered_apps, filepath, self.scan_diagnostics)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to Markdown.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")
        except OSError as e:
            self._update_status("Markdown export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_json(self):
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=f"AppList_Export_{timestamp}.json", title="Export as JSON",
        )
        if not filepath:
            return
        try:
            write_json_export(self.filtered_apps, filepath, self.scan_diagnostics)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to JSON.")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}")
        except (OSError, TypeError, ValueError) as e:
            self._update_status("JSON export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_html(self):
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")],
            initialfile=f"AppList_Dashboard_{timestamp}.html", title="Export as HTML Dashboard",
        )
        if not filepath:
            return
        try:
            write_html_export(self.filtered_apps, filepath, self.scan_diagnostics)
            self._update_status(f"Exported {len(self.filtered_apps)} rows to HTML.")
            messagebox.showinfo("Export Complete",
                f"Successfully exported {len(self.filtered_apps)} applications to:\n{filepath}\n\n"
                "Open the file in any browser to view the interactive dashboard.")
        except OSError as e:
            self._update_status("HTML export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_winget(self):
        if not self._ensure_exportable_rows():
            return
        winget_apps = [a for a in self.filtered_apps if a.winget_id]
        if not winget_apps:
            self._update_status("No winget package IDs in the current filtered view.")
            messagebox.showwarning("No Winget IDs",
                "None of the scanned applications could be matched to a winget package ID.\n\n"
                "Ensure winget is installed and run a fresh scan.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=f"WingetPackages_{timestamp}.json", title="Export Winget Package List",
        )
        if not filepath:
            return
        try:
            exported_count = write_winget_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {exported_count} winget packages.")
            messagebox.showinfo("Export Complete",
                f"Exported {exported_count} matched packages to:\n{filepath}\n\n"
                f"To restore, run:\n  winget import -i \"{filepath}\"")
        except (OSError, TypeError, ValueError) as e:
            self._update_status("Winget export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_pip(self):
        if not self._ensure_exportable_rows():
            return
        pip_apps = [a for a in self.filtered_apps if a.app_type == "Python Package"]
        if not pip_apps:
            self._update_status("No Python (pip) packages in the current filtered view.")
            messagebox.showwarning("No pip Packages",
                "None of the filtered applications are Python (pip) packages.\n\n"
                "Include pip packages in your scan or clear filters.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=f"requirements_{timestamp}.txt", title="Export pip Requirements",
        )
        if not filepath:
            return
        try:
            count = write_pip_requirements_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {count} pip packages to requirements.txt.")
            messagebox.showinfo("Export Complete",
                f"Exported {count} pip packages to:\n{filepath}\n\n"
                f"To restore, run:\n  pip install -r \"{filepath}\"")
        except (OSError, ValueError) as e:
            self._update_status("pip export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_choco(self):
        if not self._ensure_exportable_rows():
            return
        choco_apps = [a for a in self.filtered_apps if a.app_type == "Chocolatey"]
        if not choco_apps:
            self._update_status("No Chocolatey packages in the current filtered view.")
            messagebox.showwarning("No Chocolatey Packages",
                "None of the filtered applications are Chocolatey packages.\n\n"
                "Include Chocolatey packages in your scan or clear filters.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".config",
            filetypes=[("Config Files", "*.config"), ("XML Files", "*.xml"), ("All Files", "*.*")],
            initialfile=f"packages_{timestamp}.config", title="Export Chocolatey Packages",
        )
        if not filepath:
            return
        try:
            count = write_choco_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {count} Chocolatey packages.")
            messagebox.showinfo("Export Complete",
                f"Exported {count} Chocolatey packages to:\n{filepath}\n\n"
                f"To restore, run:\n  choco install packages.config")
        except (OSError, ValueError) as e:
            self._update_status("Chocolatey export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _export_ps1(self):
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".ps1",
            filetypes=[("PowerShell Scripts", "*.ps1"), ("All Files", "*.*")],
            initialfile=f"AppList_Install_{timestamp}.ps1",
            title="Export PowerShell Install Script",
        )
        if not filepath:
            return
        try:
            count = write_powershell_export(self.filtered_apps, filepath)
            self._update_status(f"Exported {count} install commands to PS1.")
            messagebox.showinfo("Export Complete",
                f"Exported {count} install commands to:\n{filepath}")
        except (OSError, ValueError) as e:
            self._update_status("PowerShell export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    # ══════════════════════════════════════════════════════════════════════════
    # CONTEXT MENU ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _export_bundle(self):
        if not self._ensure_exportable_rows():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Zip Files", "*.zip"), ("All Files", "*.*")],
            initialfile=f"AppList_Restore_{timestamp}.zip",
            title="Export Restore Bundle",
        )
        if not filepath:
            return
        try:
            manifest = write_restore_bundle_export(self.filtered_apps, filepath, self.scan_diagnostics)
            self._update_status(f"Exported restore bundle with {manifest['application_count']} applications.")
            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported restore bundle to:\n{filepath}\n\n"
                "Review unmatched-skipped.md and restore-commands.ps1 before reinstalling.",
            )
        except (OSError, TypeError, ValueError) as e:
            self._update_status("Restore bundle export failed.")
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def _lookup_winget(self):
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
        app = self._get_selected_app()
        if not app:
            return
        uninstall_str = app.uninstall_command or app.uninstall_registry_key
        if not uninstall_str:
            messagebox.showwarning("No Uninstall", f"No uninstall information available for {app.name}.")
            return
        response = messagebox.askyesno("Confirm Uninstall",
            f"Are you sure you want to uninstall {app.name}?\n\nCommand:\n{uninstall_str}")
        if not response:
            return
        try:
            if app.app_type == "Store App" and uninstall_str.startswith("Remove-AppxPackage "):
                package_name = uninstall_str[len("Remove-AppxPackage "):].strip()
                command = ["powershell", "-NoProfile", "-Command",
                           "Remove-AppxPackage -Package $args[0]", package_name]
            else:
                command = split_windows_command_line(uninstall_str)
                if not command:
                    raise ValueError("No executable found in uninstall command.")
                if is_shell_host_command(command[0]):
                    raise ValueError(
                        "Shell-based uninstall commands are not executed automatically. "
                        "Copy the uninstall command and review it before running manually.")
            subprocess.Popen(command, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
            self._update_status(f"Uninstall command launched for {app.name}.")
            messagebox.showinfo("Uninstall",
                f"Uninstall command for {app.name} executed.\nPlease complete the uninstall wizard.")
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            messagebox.showerror("Uninstall Error", f"Failed to execute uninstall:\n{e}")

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            app = self._get_selected_app()
            if not app:
                return
            self._sync_context_menu_state(app)
            self.context_menu.post(event.x_root, event.y_root)

    def _sync_context_menu_state(self, app: Optional[Application]):
        if not app:
            return
        has_location = bool(app.install_location and os.path.exists(app.install_location))
        has_registry = bool(app.uninstall_registry_key)
        has_uninstall = bool(app.uninstall_command)
        has_hash = bool(app.sha256_hash)
        has_virustotal = bool(app.virustotal_url)
        self.context_menu.entryconfig(1, state="normal" if app.install_location else "disabled")
        self.context_menu.entryconfig(2, state="normal" if has_registry else "disabled")
        self.context_menu.entryconfig(3, state="normal" if has_uninstall else "disabled")
        self.context_menu.entryconfig(4, state="normal" if has_hash else "disabled")
        self.context_menu.entryconfig(6, state="normal" if has_location else "disabled")
        self.context_menu.entryconfig(7, state="normal" if has_registry else "disabled")
        self.context_menu.entryconfig(9, state="normal" if has_virustotal else "disabled")
        self.context_menu.entryconfig(11, state="normal" if has_uninstall else "disabled")

    def _get_selected_app(self) -> Optional[Application]:
        selection = self.tree.selection()
        if not selection:
            return None
        index = self.tree_iid_to_index.get(selection[0])
        if index is not None and 0 <= index < len(self.filtered_apps):
            return self.filtered_apps[index]
        return None

    def _copy_name(self):
        app = self._get_selected_app()
        if app:
            self._copy_to_clipboard(app.name, "Application name")

    def _copy_location(self):
        app = self._get_selected_app()
        if app and app.install_location:
            self._copy_to_clipboard(app.install_location, "Install location")

    def _copy_registry(self):
        app = self._get_selected_app()
        if app and app.uninstall_registry_key:
            self._copy_to_clipboard(app.uninstall_registry_key, "Registry key")

    def _copy_sha256(self):
        app = self._get_selected_app()
        if app and app.sha256_hash:
            self._copy_to_clipboard(app.sha256_hash, "SHA-256 hash")

    def _copy_to_clipboard(self, value: str, label: str):
        self.clipboard_clear()
        self.clipboard_append(value)
        self._update_status(f"{label} copied to clipboard.")

    def _open_location(self):
        app = self._get_selected_app()
        if app and app.install_location and os.path.exists(app.install_location):
            os.startfile(app.install_location)
            self._update_status(f"Opened install location for {app.name}.")
        else:
            messagebox.showinfo("Not Available", "Install location not available or does not exist.")

    def _copy_uninstall(self):
        app = self._get_selected_app()
        if app and app.uninstall_command:
            self._copy_to_clipboard(app.uninstall_command, "Uninstall command")
        else:
            messagebox.showinfo("Not Available", "No uninstall command available for this application.")

    def _open_virustotal(self):
        app = self._get_selected_app()
        if app and app.virustotal_url:
            webbrowser.open(app.virustotal_url)
            self._update_status(f"Opened VirusTotal report for {app.name}.")

    def _open_registry_key(self):
        app = self._get_selected_app()
        if not app or not app.uninstall_registry_key:
            messagebox.showinfo("Not Available", "No registry key available for this application.")
            return
        reg_key = app.uninstall_registry_key
        try:
            if winreg:
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
            messagebox.showinfo("Registry Key Copied",
                f"Could not open Regedit automatically.\n\n"
                f"Key copied to clipboard:\n{reg_key}")

    def _save_baseline(self):
        if not self._ensure_exportable_rows():
            return
        try:
            os.makedirs(os.path.dirname(self._baseline_path), exist_ok=True)
            write_json_export(self.filtered_apps, self._baseline_path, self.scan_diagnostics)
            self._update_status(f"Baseline saved ({len(self.filtered_apps)} apps).")
            messagebox.showinfo("Baseline Saved",
                f"Snapshot saved to:\n{self._baseline_path}\n\n"
                f"{len(self.filtered_apps)} applications captured.\n"
                "Run a new scan after changes, then click Compare.")
        except OSError as e:
            messagebox.showerror("Baseline Error", f"Failed to save baseline:\n{e}")

    def _compare_baseline(self):
        if not self._ensure_exportable_rows():
            return
        if not os.path.isfile(self._baseline_path):
            messagebox.showwarning("No Baseline",
                "No baseline snapshot found.\n\n"
                "Click Baseline to save the current state first.")
            return
        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
                tmp_path = tmp.name
            write_json_export(self.filtered_apps, tmp_path, self.scan_diagnostics)
            diff = diff_json_snapshots(self._baseline_path, tmp_path)
            report = write_diff_report(diff)
            s = diff["summary"]
            self._update_status(
                f"Diff: +{s['added']} added, -{s['removed']} removed, ~{s['version_changed']} changed"
            )
            messagebox.showinfo("Before vs After", report[:2000])
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Compare Error", f"Failed to compare:\n{e}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _show_diagnostics(self):
        if not self.scan_diagnostics:
            messagebox.showinfo("Diagnostics", "No scan diagnostics available. Run a scan first.")
            return
        lines = []
        for d in self.scan_diagnostics:
            status_icon = {"ok": "✓", "skipped": "—", "warning": "⚠", "failed": "✗"}.get(d.status, "?")
            line = f"{status_icon} {d.source}: {d.status}"
            if d.row_count:
                line += f" ({d.row_count} rows)"
            if d.duration_seconds:
                line += f" [{d.duration_seconds:.3f}s]"
            lines.append(line)
            for w in d.warnings:
                lines.append(f"    {w}")
        messagebox.showinfo("Scan Diagnostics", "\n".join(lines))

    def _save_scan_log(self):
        try:
            appdata = os.environ.get("APPDATA", "")
            if not appdata:
                return
            log_dir = os.path.join(appdata, "AppList")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "last_scan.json")
            log_data = {
                "generated": datetime.now().isoformat(),
                "application_count": len(self.applications),
                "diagnostics": [d.to_dict() for d in self.scan_diagnostics],
            }
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _load_column_layout(self) -> set:
        try:
            if os.path.isfile(self._layout_path):
                with open(self._layout_path, encoding="utf-8") as f:
                    data = json.load(f)
                visible = set(data.get("visible_columns", []))
                if visible:
                    return visible & set(self._all_columns)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return set(self._default_visible)

    def _save_column_layout(self):
        try:
            os.makedirs(os.path.dirname(self._layout_path), exist_ok=True)
            with open(self._layout_path, "w", encoding="utf-8") as f:
                json.dump({"visible_columns": sorted(self._visible_columns)}, f, indent=2)
        except OSError:
            pass

    def _apply_column_visibility(self):
        column_config = {
            "name": 260, "publisher": 180, "version": 100, "install_date": 105,
            "last_used_date": 145, "type": 132, "source": 132, "upgrade_available": 175,
            "pin_status": 120, "winget_id": 200, "sha256_hash": 240, "virustotal": 105,
            "consistency": 170, "size": 90, "architecture": 80, "install_location": 280,
            "registry_key": 320,
        }
        for col in self._all_columns:
            if col in self._visible_columns:
                self.tree.column(col, width=column_config.get(col, 120), minwidth=80)
            else:
                self.tree.column(col, width=0, minwidth=0)

    def _show_column_chooser(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Column Chooser")
        dialog.geometry("320x500")
        dialog.resizable(False, True)
        dialog.transient(self)
        dialog.grab_set()

        heading_names = {
            "name": "Application", "publisher": "Publisher", "version": "Version",
            "install_date": "Installed", "last_used_date": "Last Used", "type": "Type",
            "source": "Source", "upgrade_available": "Upgrade", "pin_status": "Pin",
            "winget_id": "Winget ID", "sha256_hash": "SHA-256", "virustotal": "VirusTotal",
            "consistency": "Consistency", "size": "Size", "architecture": "Arch",
            "install_location": "Location", "registry_key": "Registry Key",
        }

        check_vars = {}
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        for col in self._all_columns:
            var = tk.BooleanVar(value=col in self._visible_columns)
            check_vars[col] = var
            ctk.CTkCheckBox(
                scroll, text=heading_names.get(col, col),
                variable=var, width=280,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_secondary"],
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", pady=2)

        def apply():
            self._visible_columns = {col for col, var in check_vars.items() if var.get()}
            if not self._visible_columns:
                self._visible_columns = {"name"}
            self._apply_column_visibility()
            self._save_column_layout()
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="Apply", command=apply, width=100).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, width=100,
                       fg_color=COLORS["bg_elevated"]).pack(side="right")

    def _on_double_click(self, event):
        self._open_location()

    def _on_close(self):
        if self.scanner:
            self.scanner.cancel()
        self.destroy()
