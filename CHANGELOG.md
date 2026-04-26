# Changelog

All notable changes to AppList will be documented in this file.

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
