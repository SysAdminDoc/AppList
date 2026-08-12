# Changelog

All notable changes to AppList will be documented in this file.

## [v1.9.1] - 2026-08-11

### Changed
- Debounced search, type, source, and upgrade filter refreshes to keep large inventories responsive during rapid input changes.
- Bounded measured directory-size scans to 100,000 files or two seconds; incomplete measurements are omitted and surfaced as diagnostics instead of reporting partial totals.
- Re-ran the release dependency verifier and end-to-end PyInstaller build after the scanner and UI changes.

## [v1.9.0] - 2026-07-10

Merged the retired **SoftwareScannerGUI** (PowerShell/WPF debloat-aid) into AppList.
Its unique scan sources and removal-script generation are now part of AppList's
Python engine, CLI, and GUI.

### Added
- **Windows services** scan source (`services`) — each row carries a safe
  `Set-Service … -StartupType Disabled` command.
- **Scheduled tasks** scan source (`scheduled_tasks`) — non-Microsoft, non-disabled
  tasks, each with a `Disable-ScheduledTask` command.
- **AppX provisioned packages** scan source (`provisioned`) — the system-wide debloat
  surface that reinstalls for new users, with `Remove-AppxProvisionedPackage`
  commands. Needs administrator rights; degrades gracefully with a diagnostic warning.
- **Startup impact rating** — Startup items are now rated High/Low against a curated
  heavy-hitter list, exposed as a new `Startup Impact` column (CSV + GUI) and model field.
- **Removal / disable script export** (`--export removal`, GUI "Removal" button) — a
  per-source uninstall/disable PowerShell script. Ships as a **dry run by default**
  (`$DryRun = $true`, `#Requires -RunAsAdministrator`); services and scheduled tasks
  are disabled rather than deleted.
- `debloat` source alias (store + provisioned + services + scheduled_tasks + startup)
  mirroring SoftwareScannerGUI's default surface.
- New type filters: Service, Scheduled Task, Provisioned Package.

### Changed
- JSON schema version bumped to 1.2 (adds `startup_impact`; new app types).

## [v1.8.0] - 2026-07-01

- Added: WSL distribution inventory via `wsl --list --verbose` with version and state
- Added: Portable-app detection scanning `%LOCALAPPDATA%\Programs`, `%USERPROFILE%\Portable`, `Tools`, `Apps`, and `C:\PortableApps`
- Added: Driver inventory via `pnputil /enum-drivers` with provider, version, and date
- Added: Windows optional feature inventory via `Get-WindowsOptionalFeature -Online`
- Added: Column chooser dialog with persistent layout saved to `%APPDATA%\AppList\layout.json`
- Added: AppCompatCache (ShimCache) as third last-used signal source alongside UserAssist and Prefetch
- Added: Start Menu and Taskbar pin detection annotating matching apps in pin_status
- Added: Intune-style compliance report via `--compliance` flag checking installed apps against a reference list
- Added: CLI sources `--include wsl`, `--include portable`, `--include drivers`, `--include features`

## [v1.7.0] - 2026-07-01

- Fixed: pip scanner no longer relaunches the packaged executable in frozen (PyInstaller) builds; uses an external Python interpreter or skips with a diagnostic
- Fixed: Restore bundle export no longer deletes existing non-empty folders; refuses by default with a clear error, supports `--overwrite` flag in CLI
- Changed: Bundle writes use a staging directory with atomic replace for both zip and folder destinations
- Added: Versioned JSON schema (1.1) with cross-version migration test fixtures
- Added: Restore bundle validator via `--validate-bundle` CLI and `validate_restore_bundle()` API
- Added: Scan mode controls (`--skip-network`, `--skip-hashing`, `--skip-last-used`) for fast/private/offline scans
- Added: Privacy-safe redacted exports via `--redact` flag stripping machine names, paths, registry keys, hashes, and URLs
- Added: GUI diagnostics panel with Diag button and durable scan log saved to `%APPDATA%\AppList\last_scan.json`
- Added: CLI `--emit-diagnostics` writes scan diagnostics as JSON
- Added: Release checksum and signature manifest in build script (`release-manifest.json`, `AppList.exe.sha256`)
- Added: PowerShell install script export (`--export ps1`) with winget/pip/choco/scoop one-liners per app
- Added: Searchable group-by dropdown (Source, Publisher, Install Year, Drive) replacing the Group by Source checkbox
- Added: Before-vs-After baseline mode with Baseline/Compare buttons for install/uninstall session diffing
- Added: Standalone winget-only entries for apps installed via winget but not present in registry
- Added: Measured directory size enrichment for apps with install locations (independent of EstimatedSize)
- Added: OEM bloatware flagging with curated publisher signature list (McAfee, Norton, WildTangent, CyberLink, etc.)
- Added: Startup-item scanner for registry Run keys and Startup folders

## [v1.6.10] - 2026-06-28

- Added: Package-manager consistency audit for Chocolatey and Scoop rows with no matching registry, Store, Program Files, path, or executable evidence
- Added: Consistency status in GUI table search/sort, TXT, CSV, Markdown, JSON, and HTML exports
- Changed: Restore bundle AppList JSON/report artifacts now carry package-manager consistency state for manual review

## [v1.6.9] - 2026-06-28

- Added: Restore bundle export as a ZIP or folder containing AppList JSON, Winget import JSON, pip requirements, Chocolatey config, Markdown/HTML reports, restore commands, manifest, and unmatched/skipped report
- Added: CLI `--export bundle` and GUI Bundle export action for migration-ready reinstall packages
- Changed: Bundle exports reuse scan diagnostics in report artifacts and manifest data when sources are skipped or degraded

## [v1.6.8] - 2026-06-28

- Added: Per-source scan diagnostics with status, warnings, durations, and row counts for source phases, winget matching, last-used enrichment, and hashing
- Added: JSON, TXT, Markdown, and HTML exports now include diagnostics when a scan source is skipped, degraded, or failed
- Changed: GUI status now warns when a scan completes with diagnostic notices instead of presenting a silently complete inventory

## [v1.6.7] - 2026-06-28

- Added: Exact-pinned release dependency lock with `pip-audit` included in local release verification
- Added: Clean-venv dependency verifier that installs the lock file, audits it, runs tests, and imports the GUI against customtkinter 5.2.2
- Changed: PyInstaller build script installs from the pinned dependency lock before producing `dist/AppList.exe`

## [v1.6.6] - 2026-06-28

- Fixed: Winget fallback parsing now handles nested JSON shapes and localized table headers by package identifier
- Changed: Unparseable winget text output now emits an explicit warning instead of silently producing an empty match set

## [v1.6.5] - 2026-06-27

- Added: Optional source-grouped Treeview mode with expandable source parent rows and per-source counts
- Changed: App context actions are suppressed on group parent rows while remaining available on application rows

## [v1.6.4] - 2026-06-27

- Added: Treeview pagination that inserts 500 filtered rows at a time with Previous/Next controls
- Changed: Status/count text now reports the visible page range while exports continue to use the full filtered result set

## [v1.6.3] - 2026-06-27

- Changed: Winget package ID and upgrade cross-reference now prefers structured `Microsoft.WinGet.Client` / `Get-WinGetPackage` output on PowerShell 7+
- Changed: Existing `winget.exe` JSON/text parsing remains as the fallback when PS7 or the module is unavailable

## [v1.6.2] - 2026-06-27

- Added: SHA-256 hashing for discovered primary executables with cached results in `%APPDATA%\AppList\wingetlist-sha-cache.json`
- Added: VirusTotal report deep-links in GUI context actions plus TXT, CSV, Markdown, JSON, and HTML exports
- Changed: GUI table now exposes SHA-256 and VirusTotal columns for rows with hashable executables

## [v1.6.1] - 2026-06-27

- Added: Last-used date enrichment from UserAssist launch history and Windows Prefetch parser data when accessible
- Changed: TXT, CSV, Markdown, JSON, HTML, and GUI table output now include a `Last Used` field/column

## [v1.6.0] - 2026-06-27

- Changed: Split the tracked application into `applist` modules for scanner, model, export, CLI, constants, and GUI code with a thin `AppList.py` entrypoint
- Added: Unit tests for scanner parsing/deduplication, subprocess-backed scanners, export writers, JSON diffing, and CLI diff mode
- Added: Local PyInstaller build script with a multiprocessing runtime hook and optional local certificate signing
- Changed: Runtime dependency setup now follows normal Python packaging via `requirements.txt` instead of installing packages at launch

## [v1.5.0] - 2026-06-19

- Added: HTML single-file dashboard export with sortable, searchable table and Catppuccin Mocha styling
- Added: JSON snapshot diff via CLI (`--diff old.json new.json`) with Added/Removed/VersionChanged report (text or JSON output)
- Added: Pin awareness column showing Pinned/Gating/Blocking status from `winget pin list`
- Added: pip `requirements.txt` export for Python package restoration
- Added: Chocolatey `packages.config` export for choco-first environments
- Added: "Pinned" option in the upgrade/data-quality filter dropdown
- Changed: Theme replaced with Catppuccin Mocha color palette for consistency with global design standard
- Changed: CLI now supports `--export html`, `--export pip`, `--export choco`, and `--diff` modes
- Changed: Export toolbar buttons use shorter labels to accommodate the expanded format menu
- Changed: CSV export now includes "Pin Status" column
- Changed: Treeview includes "Pin" column between Upgrade and Winget ID

## [v1.4.1] - 2026-06-16

- Changed: Refined the GUI with a tighter dark theme, compact stat cards, a clearer command bar, and a more polished table shell
- Added: Type, source, and upgrade/data-quality filters in the GUI
- Added: First-run, scanning, no-match, error, and zero-result empty states
- Added: Source column visibility and package-manager source labels for Chocolatey, Scoop, and Python package rows
- Changed: Export buttons now stay disabled until the filtered view has rows, with clearer no-data feedback
- Changed: Context-menu actions now disable when unavailable and report copy/open feedback in the status bar

## [v1.4.0] - 2026-06-16

- Added: Headless CLI mode with `--export`, `--output`, and `--include` for scripted inventory exports without opening the GUI
- Added: Source filtering for CLI scans (`all`, `desktop`, `registry`, `store`, `program_files`, `chocolatey`, `scoop`, `pip`, `winget`)
- Changed: GUI and CLI exports now use shared writer functions for TXT, CSV, Markdown, JSON, and winget import formats

## [v1.3.1] - 2026-06-16

- Fixed: Uninstall commands no longer execute through `cmd.exe`; registry commands are parsed and launched with `shell=False`
- Fixed: Markdown export now includes Chocolatey, Scoop, Python, and any other detected app types instead of silently omitting them
- Fixed: Version strings are synced to v1.3.1
- Fixed: Removed duplicated v1.0.0 content from README.md
- Changed: Recoverable scanner failures now use narrower exception handling and write warnings to stderr
- Fixed: Context-menu actions now resolve selected rows by treeview item ID instead of display name
- Fixed: First-run dependency setup no longer crashes on CP1252 consoles while printing Unicode banner characters

## [v1.3.0] - 2026-05-03

- Added: Upgrade-available column — shows "Update Available (X.Y.Z)" when `winget upgrade` detects newer versions
- Added: Ghost entry detection — flags applications with registry entries but missing install locations with "⚠ Missing" badge
- Added: "Uninstall" context menu item — invokes the app's uninstall command with confirmation dialog
- Changed: CSV export now includes "Update Available" column
- Changed: Treeview column for upgrade status with visual indicator badges

## [v1.2.0] - 2026-05-01

- Added: Chocolatey scanner (Phase 4/7) — scans `%PROGRAMDATA%\chocolatey\lib\` and parses `.nuspec` for name/version/publisher
- Added: Scoop scanner (Phase 5/7) — scans `~\scoop\apps\` and reads `current\manifest.json` for version
- Added: pip scanner (Phase 6/7) — runs `python -m pip list --format=json` and adds Python packages
- Added: Export Winget — exports matched apps as official `winget import`-compatible JSON (`winget-packages.schema.2.0.json`)
- Added: "Lookup on Winget" context menu — opens winstall.app (if winget ID known) or winget.run search
- Added: Filter dropdown options for Chocolatey, Scoop, and Python (pip)
- Changed: Stats panel "Unregistered" card now counts all non-Desktop/non-Store apps (Unregistered + Chocolatey + Scoop + pip); relabeled "Unregistered / Other"
- Changed: Scan pipeline updated to Phase 1/7–7/7 messaging with rescaled progress percentages

## [v1.1.0] - 2026-04-26

- Added: winget cross-reference (Phase 4 scan) — populates Winget ID on matched registry apps
- Added: Export Markdown — grouped report (Desktop / Store / Unregistered) with pipe tables
- Added: Export JSON — full AppList schema, round-trippable
- Added: Size, Architecture, and Winget ID columns in the application table
- Added: "Copy Uninstall Command" context menu item
- Added: "Open Registry Key in Regedit" context menu item (navigates Regedit to the app's key)
- Changed: CSV export now includes Winget ID column
- Changed: Scan pipeline updated to Phase 1/4–4/4 messaging

## [v1.0.0] - 2025-01-01

- Added: Registry scanning (HKLM 64-bit, HKLM 32-bit WOW6432Node, HKCU)
- Added: Microsoft Store / UWP app scanning via Get-AppxPackage
- Added: Program Files directory scanning for unregistered apps
- Added: TXT and CSV export
- Added: Dark theme GUI with sortable columns, live search, and category filter
- Added: Stats dashboard (total, desktop, store, unregistered counts)
- Added: Context menu (copy name/location/registry key, open install location)

## Roadmap archive — 2026-08-10 — ROADMAP.md

<details>
<summary>Original roadmap snapshot</summary>

```markdown
# AppList Roadmap

Remaining incomplete work only. Completed items are deleted. Blocked items belong in `Roadmap_Blocked.md`.

## Audit Findings (deferred)

- [ ] P2 — Verify release build scripts with end-to-end PyInstaller build after audit changes
  Why: `tools/build_exe.ps1` and `tools/verify_release_dependencies.ps1` were reviewed but not re-run after audit modifications.
  Where: `tools/build_exe.ps1`, `tools/verify_release_dependencies.ps1`

- [ ] P3 — Debounce filter dropdown changes
  Why: Type, source, and upgrade filter dropdown changes trigger immediate `_apply_filters` without debounce (unlike search which is now debounced). Large inventories could stutter on rapid filter switching.
  Where: `applist/ui.py` `_on_filter_changed`

- [ ] P3 — Measure and bound directory size scan time
  Why: `_measure_directory_size_kb` walks entire install trees with no file-count or timeout guard. Very large installs (game directories) could cause long scan pauses.
  Where: `applist/scanner.py` `_measure_directory_size_kb`
```

</details>
