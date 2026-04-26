# Changelog

All notable changes to AppList will be documented in this file.

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
