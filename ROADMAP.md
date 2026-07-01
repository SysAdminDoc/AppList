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

- [ ] P0 — Frozen pip scan guard
  Why: packaged PyInstaller builds expose `sys.executable` as `AppList.exe`, but `scan_pip()` currently calls `sys.executable -m pip list`, which can relaunch or fail in the frozen app.
  Evidence: `applist/scanner.py:907-918`; PyInstaller runtime/common-issues docs; pip Windows CLI docs.
  Touches: `applist/scanner.py`, `applist/cli.py`, `tests/test_scanner.py`, `tools/build_exe.ps1`
  Acceptance: frozen-mode tests prove pip scanning uses an external Python launcher/interpreter or emits a clear skipped diagnostic without launching `AppList.exe`; normal source-mode pip scans still pass.
  Complexity: M

- [ ] P0 — Non-destructive restore bundle writes
  Why: restore bundle export deletes an existing output folder before writing, which can destroy user data if the destination is reused or mistyped.
  Evidence: `applist/exports.py:342-346`
  Touches: `applist/exports.py`, `applist/cli.py`, `applist/ui.py`, `tests/test_exports.py`
  Acceptance: existing non-empty folders are refused unless an explicit overwrite flag/path choice is provided; bundle writes use a temp directory and atomic replace where possible; tests cover folder and zip destinations.
  Complexity: M

- [ ] P1 — Restore bundle validator
  Why: bundles now contain multiple restore artifacts, but there is no command that proves the manifest, included files, winget JSON, pip requirements, Chocolatey config, and restore script are internally valid.
  Evidence: `applist/exports.py:330-384`; winget import docs; Chocolatey export/install docs; pip requirements workflow.
  Touches: `applist/exports.py`, `applist/cli.py`, `applist/ui.py`, `tests/test_exports.py`, README
  Acceptance: CLI and GUI can validate a bundle path and report missing files, malformed package-manager artifacts, skipped sections, and restore-script issues with a nonzero CLI exit on failure.
  Complexity: M

- [ ] P1 — Scan mode controls for offline, no-network, and no-hash runs
  Why: full scans always perform winget/source enrichment, last-used enrichment, and executable hashing, but operators need fast/private inventory modes for disconnected or sensitive systems.
  Evidence: `applist/scanner.py:1335-1378`; winget issue #4449; current hash and VirusTotal enrichment behavior.
  Touches: `applist/scanner.py`, `applist/cli.py`, `applist/ui.py`, `applist/models.py`, tests
  Acceptance: CLI flags and GUI controls can disable network/package-manager enrichment, last-used collection, and executable hashing independently; diagnostics record which enrichments were skipped and why.
  Complexity: M

- [ ] P1 — Privacy-safe redacted exports
  Why: default exports include machine name, full user paths, executable paths, registry keys, uninstall commands, hashes, and VirusTotal links that users may need to share safely.
  Evidence: `applist/exports.py:196-209`; `applist/models.py:47-68`; Belarc local privacy positioning.
  Touches: `applist/exports.py`, `applist/cli.py`, `applist/ui.py`, `tests/test_exports.py`, README
  Acceptance: TXT/CSV/Markdown/JSON/HTML exports support a redaction option that removes or masks machine names, usernames, local paths, registry keys, uninstall commands, hashes, and external lookup URLs while preserving app names, publishers, versions, source, and high-level status.
  Complexity: M

- [ ] P1 — First-class scan diagnostics panel and durable scan log
  Why: scan diagnostics exist internally and in some exports, but GUI users only see a summary count after partial failures.
  Evidence: `applist/ui.py:952-960`; `applist/exports.py:17-40`; `applist/scanner.py:70-97`
  Touches: `applist/ui.py`, `applist/models.py`, `applist/exports.py`, tests
  Acceptance: GUI shows a diagnostics view with source, status, row count, duration, warnings, and recovery hints; CLI can emit the same diagnostics as JSON; the last scan log is saved under `%APPDATA%\AppList`.
  Complexity: M

- [ ] P2 — CycloneDX and PURL SBOM export
  Why: security and compliance tools consume CycloneDX/PURL, and AppList already captures enough package/source metadata to emit a machine-readable software inventory BOM.
  Evidence: CycloneDX specification; Package-URL specification; `requirements.txt` includes `cyclonedx-python-lib` and `packageurl-python` through the audit toolchain.
  Touches: `applist/exports.py`, `applist/models.py`, `applist/cli.py`, `applist/ui.py`, tests, README
  Acceptance: AppList can export CycloneDX JSON with components for winget, Chocolatey, Scoop, pip, Store, and registry/program-file apps where identifiers exist; PURLs are emitted for supported ecosystems and AppList-specific properties preserve source evidence.
  Complexity: M

- [ ] P2 — Remote live inventory connector
  Why: comparable tools support remote Windows inventory, and this is distinct from the existing offline-import roadmap item for mounted drives or hives.
  Evidence: NirSoft UninstallView remote inventory; PDQ Inventory remote scanning; Intune app inventory collection model.
  Touches: `applist/scanner.py`, `applist/cli.py`, `applist/ui.py`, `applist/models.py`, tests, README
  Acceptance: CLI can scan a named remote Windows host using Remote Registry and/or PowerShell remoting when available, labels rows with the remote host, records unreachable/permission failures as diagnostics, and never mutates the remote machine.
  Complexity: XL

- [ ] P2 — Source adapter result contract
  Why: adding WSL, drivers, remote inventory, custom rules, SBOM metadata, and future detectors will keep expanding the scanner unless each source returns a structured result with common diagnostics.
  Evidence: `applist/scanner.py`; OCS Inventory plugin model; PDQ custom scanner model; existing `ScanDiagnostic` dataclass.
  Touches: `applist/scanner.py`, `applist/models.py`, `applist/cli.py`, `applist/ui.py`, tests
  Acceptance: each source adapter returns applications plus status, warnings, duration, capability checks, and recovery hints through one contract; existing exports and diagnostics consume the contract without source-specific branching.
  Complexity: L
