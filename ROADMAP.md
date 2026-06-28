# AppList Roadmap

Remaining incomplete work only. Completed items are deleted. Blocked items belong in `Roadmap_Blocked.md`.

## Tier 3 - Medium Impact / Moderate Effort

- [ ] **PowerShell one-liner export** - emit equivalent PS command for each app. (Effort: 2h)
- [ ] **Searchable group-by** - group by Publisher, Install Year, and Location drive with search. (Effort: 4h)
- [ ] **Before vs After mode** - snapshot before and after an install/uninstall session, auto-diff. (Effort: 4h)
- [ ] **Standalone winget-only entries** - include apps installed via winget but not present in registry. (Effort: 4h)

## Tier 4 - Nice-to-Have / Long-term

- [ ] **OEM bloatware flagging** - curated signature list of known OEM trialware and bloatware publishers with visual badge. (Effort: 4h + ongoing curation)
- [ ] **Product-key recovery** - use `windows-tools.product-key` PyPI package or registry heuristics for Windows/Office keys. Sensitive data must require explicit opt-in. (Effort: 6h)
- [ ] **WSL distro inventory** - `wsl --list --verbose` plus per-distro Linux package counts. (Effort: 4h)
- [ ] **Portable-app detection** - scan `%LOCALAPPDATA%\Programs\`, `%USERPROFILE%\Portable\`, and common portable-app signatures. (Effort: 4h)
- [ ] **Driver + Windows Feature pass** - parse `Get-WindowsOptionalFeature -Online` and `pnputil /enum-drivers` into app list. (Effort: 4h)
- [ ] **MSIX Store distribution** - wrap output with Py2MSIX for Microsoft Store listing. Requires code-signing certificate. (Effort: 8h)
- [ ] **Startup-item export** - scan registry Run keys, Startup folders, and Task Scheduler for auto-start entries. (Effort: 4h)
- [ ] **Column chooser + save layout** - let users show/hide columns and persist selection to a local JSON config. (Effort: 4h)
- [ ] **DPI-aware icon cache** - extract `.exe` icons via `win32gui`/`PIL` and cache to `%APPDATA%\AppList\icons\`. (Effort: 8h)
- [ ] **Cloud-sync baselines to GitHub Gist** - export JSON snapshot to a private Gist for cross-machine diff. (Effort: 6h)
- [ ] **Last-used date per app** - via Prefetch and AppCompatCache parsing. (Effort: 6h)
- [ ] **App size re-measurement** - measure install directories because many publishers misreport `EstimatedSize`. (Effort: 4h)
- [ ] **Start Menu pin + Taskbar pin export**. (Effort: 2h)
- [ ] **Intune-style compliance report** - flag missing required apps from a reference list. (Effort: 6h)

## Research-Driven Additions

- [ ] P1 - Package-manager consistency audit
  Why: stale Chocolatey/Scoop/winget metadata can claim software is installed after the real app was removed, causing restore/update confusion.
  Evidence: https://github.com/Devolutions/UniGetUI/issues/5020; `applist/scanner.py` package-manager scanners; current ghost flag only covers missing install paths.
  Touches: `applist/scanner.py`, `applist/models.py`, `applist/ui.py`, exports, tests
  Acceptance: AppList flags package-manager rows with no matching registry/app executable evidence as inconsistent and exports that state.
  Complexity: M

- [ ] P1 - AppList JSON schema and migration fixtures
  Why: snapshot diffing depends on stable JSON, but schema compatibility is only implicit in `write_json_export()` and `diff_json_snapshots()`.
  Evidence: `applist/exports.py`; Microsoft winget JSON schema docs; existing AppList JSON diff workflow.
  Touches: `applist/exports.py`, `applist/models.py`, `tests/fixtures/`, README
  Acceptance: versioned JSON schema documentation and fixtures cover v1.5-v1.6 snapshots, missing optional fields, and future field additions without breaking diffs.
  Complexity: M

- [ ] P1 - Offline inventory import
  Why: migration users often have an old Windows drive or exported registry hives rather than a running source PC.
  Evidence: NirSoft UninstallView remote/offline-style inventory positioning; AppList's registry scanner is currently live-system only.
  Touches: `applist/scanner.py`, `applist/cli.py`, `applist/ui.py`, tests
  Acceptance: CLI and GUI can scan a mounted Windows directory plus exported HKLM/HKCU uninstall hives and label results as offline inventory.
  Complexity: XL

- [ ] P2 - Custom detector rule file
  Why: business and portable applications are often absent from winget/Chocolatey/Scoop and need user-maintained detection hints.
  Evidence: https://github.com/Devolutions/UniGetUI/issues/4645; https://github.com/Devolutions/UniGetUI/issues/4648; BCUninstaller portable detection.
  Touches: `applist/scanner.py`, `applist/models.py`, `applist/constants.py`, README, tests
  Acceptance: a JSON/YAML rules file can add name, publisher, path glob, executable glob, and restore note detectors; matches show rule IDs and confidence.
  Complexity: L

- [ ] P2 - Accessibility and localization pass
  Why: competitors ship broad translations, while AppList hardcodes English UI/export strings and has no accessibility smoke coverage.
  Evidence: BCUninstaller and Geek Uninstaller translation coverage; `applist/ui.py` hardcoded text; README current Windows audience.
  Touches: `applist/ui.py`, `applist/exports.py`, resource files, tests
  Acceptance: user-facing strings are centralized, core controls have accessible labels where supported by tkinter/customtkinter, and high-contrast text checks pass for the major UI states.
  Complexity: L

- [ ] P2 - Release checksum and signature manifest
  Why: the build script may produce unsigned executables when no local certificate is present, and users need a way to verify downloaded artifacts.
  Evidence: `tools/build_exe.ps1`; PyInstaller changelog/advisory history; current local artifact workflow.
  Touches: `tools/build_exe.ps1`, README, CHANGELOG
  Acceptance: each build emits SHA-256 checksums, signature status, PyInstaller version, Python version, dependency versions, and a machine-readable release manifest beside `dist/AppList.exe`.
  Complexity: S
