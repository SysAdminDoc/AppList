# AppList — Roadmap

Windows tool that scans registry + WOW6432Node + HKCU + UWP + Program Files, exports installed app inventory to TXT/CSV/MD/JSON. PyQt-style dark GUI with sortable columns, filtering, and context actions.

## Completed (v1.1.0)
- [x] winget cross-reference — Phase 4 scan populates Winget ID on matched registry apps
- [x] Export: Markdown grouped report (Desktop / Store / Unregistered, pipe-table)
- [x] Export: JSON full AppList schema (round-trippable)
- [x] Size + Architecture + Winget ID columns in treeview
- [x] Context menu: Copy Uninstall Command
- [x] Context menu: Open Registry Key in Regedit

## Planned Features

### Scanners
- Add standalone winget-only entries (apps installed via winget but not in registry)
- Chocolatey + Scoop + `pip` user-site + `cargo install` inventories
- WSL distro inventory (name, version, installed packages via `apt list --installed` per distro)
- Portable-app detection — scan `%LOCALAPPDATA%\Programs\`, `%USERPROFILE%\Portable\`, common flashdrive signatures
- Driver + Windows Feature pass (`Get-WindowsOptionalFeature`, `pnputil /enum-drivers`)

### Export
- **winget import** format (`.json`) so a new machine reinstalls with one command
- **Chocolatey `packages.config`** for choco-first environments
- **PowerShell one-liner** equivalent for each app (auditor-friendly)

### Diff / Compare
- Save a snapshot, run on a different machine, diff — show Added / Removed / UpgradedVersion
- "Before vs After" mode around an install/uninstall session
- Highlight OEM crapware via a curated signature list

### UI / UX
- Virtualized list so 5,000+ entries scroll at 60 FPS
- Column chooser + save layout
- Right-click: Uninstall, Lookup on winget
- Searchable group-by (Publisher, Install Year, Location drive)
- Progress bar with cancelable per-source pipeline
- DPI-aware icon cache — extract `.exe` icons for each entry
- Upgrade-available column (cross-reference `winget upgrade` output)

### Packaging
- PyInstaller single-exe + code-signing hook
- MSIX for Store distribution
- CLI mode — `AppList.py --export csv --output apps.csv --include store,winget`

## Competitive Research
- **Geek Uninstaller** — portable single-exe, HTML export via `Ctrl+S`. Target to match on ease + polish. Our edge: structured CSV/JSON that Geek can't produce and UWP + winget in one view.
- **Belarc Advisor** — exhaustive audit including product keys, hotfixes, last-usage heuristic. Worth mirroring the last-usage signal via `Prefetch\*.pf` and AppCompatCache.
- **NirSoft UninstallView** — HTML/XML/CSV/TXT exports; no UWP. Our edge is native UWP scan + better GUI.
- **`Get-ItemProperty HKLM:\...\Uninstall\*`** — baseline PowerShell one-liner; AppList should optionally emit equivalent PS for auditors.

## Nice-to-Haves
- Cloud-sync baselines to GitHub Gist for cross-machine diff
- Detect "ghost" entries (registry uninstall key but no files on disk)
- Last-used date per app via Prefetch + AppCompatCache parsing
- App size re-measurement (many publishers lie in `EstimatedSize`)
- Start Menu pin + Taskbar pin export
- Intune-style compliance report — flag missing required apps from a reference list

## Open-Source Research (Round 2)

### Related OSS Projects
- **bfcns/wingetlist** — https://github.com/bfcns/wingetlist — PowerShell inventory grouped by source with VirusTotal-hash lookups, Markdown/HTML report export.
- **microsoft/winget-cli** — https://github.com/microsoft/winget-cli — Official winget CLI + PowerShell module + COM API; source of truth for `winget list` / `winget export` JSON schema.
- **4lrick/winget-export** — https://github.com/4lrick/winget-export — UI for browsing the daily-refreshed winget catalog and exporting JSON / PowerShell / cmdline imports.
- **shanselman/winget-tui** — https://github.com/shanselman/winget-tui — Terminal UI: search, install, upgrade, pin-awareness, source filtering, sortable columns.
- **microsoft/winget-pkgs** — https://github.com/microsoft/winget-pkgs — Community manifest repo; canonical data source for matching uninstall entries back to winget package IDs.
- **ChrisTitusTech/winutil** — https://github.com/ChrisTitusTech/winutil — Reference for mass install/uninstall UX over winget.

### Features to Borrow
- **VirusTotal hash lookup per installer** (wingetlist) — cache SHA-256 of each `QuietUninstallString` installer path to a local JSON and deep-link to VT reports. Critical for migration audits.
- **Source-grouped view** (wingetlist) — group the list by `Source` column: winget / msstore / none / Chocolatey / direct-install, with expand/collapse.
- **Upgrade-available column** (wingetlist, winget-cli) — cross-reference each entry with `winget upgrade` output and flag stale versions.
- **Export to winget JSON schema** (winget-cli export) — follow the official import/export schema so AppList exports re-import cleanly into winget itself, not just a proprietary CSV.
- **Pin awareness** (winget-tui) — show whether a package is pinned (via `winget pin list`) and warn before attempting to export/reinstall.
- **Browse full winget catalog for missing installs** (4lrick/winget-export) — when cataloging a machine, flag apps that *could* be managed by winget but aren't, showing the canonical winget ID.
- **Markdown + HTML report export** (wingetlist) — dual-format reports that paste cleanly into ticketing systems and render in browsers. ✓ Markdown done in v1.1.0

### Patterns & Architectures Worth Studying
- **SHA-256 cache JSON to avoid VT rate limits** (wingetlist) — `applist-sha-cache.json` keyed by install-path keeps scans fast after the first run and keeps the free VT tier viable.
- **Microsoft.WinGet.Client PowerShell module** (winget-cli) — move off `winget.exe` subprocess calls to the module for structured output and faster calls.
- **JSON schema as the export primary** (winget-cli) — treat CSV/XLSX as derived formats; JSON round-trips cleanly and versions well in git. ✓ Done in v1.1.0
- **TUI + GUI dual frontend over the same core library** (winget-tui + 4lrick/winget-export) — keep AppList's core as a PS module, with both the Windows WPF GUI and a Terminal.Gui / `Out-ConsoleGridView` TUI rendering the same data.
- **Cross-source deduplication by display name + publisher** (winget-pkgs matching) — one app often appears in MSIX + registry + Chocolatey; match-and-collapse so the count isn't inflated.

- WSL distro inventory (name, version, installed packages via `apt list --installed` per distro)
- Portable-app detection — scan `%LOCALAPPDATA%\Programs\`, `%USERPROFILE%\Portable\`, common flashdrive signatures
- Driver + Windows Feature pass (`Get-WindowsOptionalFeature`, `pnputil /enum-drivers`)

### Export
- **Markdown** report with grouped sections (Desktop / Store / Unregistered / winget)
- **JSON** schema that round-trips back in (diff tool)
- **HTML** single-file dashboard (sortable, searchable, no server)
- **winget import** format (`.json`) so a new machine reinstalls with one command
- **Chocolatey `packages.config`** for choco-first environments

### Diff / Compare
- Save a snapshot, run on a different machine, diff — show Added / Removed / UpgradedVersion
- "Before vs After" mode around an install/uninstall session
- Highlight OEM crapware via a curated signature list

### UI / UX
- Virtualized list so 5,000+ entries scroll at 60 FPS
- Column chooser + save layout
- Right-click: Uninstall, Open registry key, Copy uninstall string, Lookup on winget
- Searchable group-by (Publisher, Install Year, Location drive)
- Progress bar with cancelable per-source pipeline
- DPI-aware icon cache — extract `.exe` icons for each entry

### Packaging
- PyInstaller single-exe + code-signing hook
- MSIX for Store distribution
- CLI mode — `AppList.py --export csv --output apps.csv --include store,winget`

## Competitive Research
- **Geek Uninstaller** — portable single-exe, HTML export via `Ctrl+S`. Target to match on ease + polish. Our edge: structured CSV/JSON that Geek can't produce and UWP + winget in one view.
- **Belarc Advisor** — exhaustive audit including product keys, hotfixes, last-usage heuristic. Worth mirroring the last-usage signal via `Prefetch\*.pf` and AppCompatCache.
- **NirSoft UninstallView** — HTML/XML/CSV/TXT exports; no UWP. Our edge is native UWP scan + better GUI.
- **`Get-ItemProperty HKLM:\...\Uninstall\*`** — baseline PowerShell one-liner; AppList should optionally emit equivalent PS for auditors.

## Nice-to-Haves
- Cloud-sync baselines to GitHub Gist for cross-machine diff
- Detect "ghost" entries (registry uninstall key but no files on disk)
- Last-used date per app via Prefetch + AppCompatCache parsing
- App size re-measurement (many publishers lie in `EstimatedSize`)
- Start Menu pin + Taskbar pin export
- Intune-style compliance report — flag missing required apps from a reference list

## Open-Source Research (Round 2)

### Related OSS Projects
- **bfcns/wingetlist** — https://github.com/bfcns/wingetlist — PowerShell inventory grouped by source with VirusTotal-hash lookups, Markdown/HTML report export.
- **microsoft/winget-cli** — https://github.com/microsoft/winget-cli — Official winget CLI + PowerShell module + COM API; source of truth for `winget list` / `winget export` JSON schema.
- **4lrick/winget-export** — https://github.com/4lrick/winget-export — UI for browsing the daily-refreshed winget catalog and exporting JSON / PowerShell / cmdline imports.
- **shanselman/winget-tui** — https://github.com/shanselman/winget-tui — Terminal UI: search, install, upgrade, pin-awareness, source filtering, sortable columns.
- **microsoft/winget-pkgs** — https://github.com/microsoft/winget-pkgs — Community manifest repo; canonical data source for matching uninstall entries back to winget package IDs.
- **ChrisTitusTech/winutil** — https://github.com/ChrisTitusTech/winutil — Reference for mass install/uninstall UX over winget.

### Features to Borrow
- **VirusTotal hash lookup per installer** (wingetlist) — cache SHA-256 of each `QuietUninstallString` installer path to a local JSON and deep-link to VT reports. Critical for migration audits.
- **Source-grouped view** (wingetlist) — group the list by `Source` column: winget / msstore / none / Chocolatey / direct-install, with expand/collapse.
- **Upgrade-available column** (wingetlist, winget-cli) — cross-reference each entry with `winget upgrade` output and flag stale versions.
- **Export to winget JSON schema** (winget-cli export) — follow the official import/export schema so AppList exports re-import cleanly into winget itself, not just a proprietary CSV.
- **Pin awareness** (winget-tui) — show whether a package is pinned (via `winget pin list`) and warn before attempting to export/reinstall.
- **Browse full winget catalog for missing installs** (4lrick/winget-export) — when cataloging a machine, flag apps that *could* be managed by winget but aren't, showing the canonical winget ID.
- **Markdown + HTML report export** (wingetlist) — dual-format reports that paste cleanly into ticketing systems and render in browsers.
- **Chocolatey + Scoop + Microsoft Store enumeration** (winget-tui source filter) — broaden beyond the three registry hives to catch Chocolatey's `lib`, Scoop's `~/scoop/apps`, and AppX fully.

### Patterns & Architectures Worth Studying
- **SHA-256 cache JSON to avoid VT rate limits** (wingetlist) — `applist-sha-cache.json` keyed by install-path keeps scans fast after the first run and keeps the free VT tier viable.
- **Microsoft.WinGet.Client PowerShell module** (winget-cli) — move off `winget.exe` subprocess calls to the module for structured output and faster calls.
- **JSON schema as the export primary** (winget-cli) — treat CSV/XLSX as derived formats; JSON round-trips cleanly and versions well in git.
- **TUI + GUI dual frontend over the same core library** (winget-tui + 4lrick/winget-export) — keep AppList's core as a PS module, with both the Windows WPF GUI and a Terminal.Gui / `Out-ConsoleGridView` TUI rendering the same data.
- **Cross-source deduplication by display name + publisher** (winget-pkgs matching) — one app often appears in MSIX + registry + Chocolatey; match-and-collapse so the count isn't inflated.
