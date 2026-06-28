# Research - AppList

## Executive Summary

AppList is a Windows application inventory tool for rebuild, migration, audit, and reinstall planning. Its strongest current shape is a local-first Python/customtkinter GUI plus headless CLI that scans registry, Store/AppX, Program Files, Chocolatey, Scoop, pip, and winget metadata, then exports structured reports and reinstall inputs. The highest-value direction is to become a trustworthy migration bundle generator: keep AppList read-mostly and inventory-first, but close reliability gaps around localized winget output, dependency drift, scan diagnostics, package-manager consistency, and restore verification. Top opportunities: locale-safe winget matching, locked/audited release dependencies, visible scan diagnostics, restore bundle generation, package-manager consistency checks, offline/remote inventory import, schema versioning for JSON snapshots, rule-based custom detectors, accessibility/i18n polish, and signed/checksummed artifact metadata.

## Product Map

- Core workflows: scan installed software; filter/search/group inventory; inspect app metadata and install paths; export human and machine-readable reports; diff AppList JSON snapshots; produce package-manager restore inputs.
- User personas: Windows rebuild/migration users; IT operators preparing reinstall kits; sysadmins auditing a single machine before replacement; power users tracking package-manager coverage; maintainers validating local software state.
- Platforms and distribution: Windows 10/11, Python 3.8+, customtkinter/tkinter GUI, CLI mode, local PyInstaller one-file build via `tools/build_exe.ps1`.
- Key integrations and data flows: Windows registry uninstall keys, AppX PowerShell output, filesystem scans under Program Files and local app paths, Chocolatey `.nuspec`, Scoop manifests, `pip list --format=json`, `Microsoft.WinGet.Client`, `winget.exe`, UserAssist, Prefetch, SHA-256 executable hashing, VirusTotal file report URLs.

## Competitive Landscape

- BCUninstaller: excels at broad installed-app detection, portable app detection, batch uninstall, leftover cleanup, startup management, and regex filtering. Learn from its source parity and diagnostics; avoid turning AppList into a destructive uninstaller because AppList's safer niche is audit and migration planning.
- UniGetUI: strong at multi-package-manager GUI workflows, custom install/update options, backup/recover lists, translation coverage, and package detail metadata. Learn from its backup/recover UX and package-manager breadth; avoid background auto-update behavior and package-manager mutation.
- wingetlist: narrow but relevant PowerShell inventory tool with source grouping, update grouping, Markdown/HTML export, and VirusTotal links. AppList already absorbed several ideas; keep learning from its focused report UX, but avoid becoming winget-only.
- NirSoft UninstallView: fast, portable installed-software viewer with remote-machine and multiple export formats. Learn from remote/offline inventory and command-line reporting; avoid UI minimalism that hides AppList's migration context.
- Belarc Advisor: broad PC profile including software, hotfixes, licenses, and security benchmarks. Learn from compliance-style summarization; avoid collecting sensitive product keys by default.
- Revo Uninstaller Pro and Geek Uninstaller: win on leftover cleanup, forced uninstall, Hunter Mode/window targeting, restore points, and portable single-exe distribution. Learn from recovery safeguards and clear state labels; avoid destructive cleanup workflows unless they are explicitly opt-in and reversible.
- Intune/PDQ/osquery: enterprise inventory systems emphasize per-device aggregation, refresh cadence, software counts, install locations, hashes, and exportable reports. Learn from schema stability, diagnostics, and compliance deltas; avoid server/backend requirements that would weaken AppList's local-first value.

## Security, Privacy, and Reliability

- Verified: `requirements.txt` uses lower bounds (`customtkinter>=5.2.0`, `pyinstaller>=6.8.0`, `windowsprefetch>=4.0.3`) with no lock file or hash-checked constraints. PyPI now serves customtkinter 6.0.0 released 2026-06-24, so a clean install can pull a major UI dependency without AppList validation.
- Verified: PyInstaller has had relevant Windows local-privilege advisories for older versions, and AppList packages a Windows executable. The current lower bound avoids the `<6.0.0` advisory range, but there is no `pip-audit` or release dependency audit gate.
- Verified: GUI scan failures are mostly warnings written by `ApplicationScanner._log_warning()` to stderr in `applist/scanner.py`; the GUI does not expose a diagnostics pane or durable scan log, so partial scans can look successful.
- Verified: `applist/scanner.py` falls back from structured `Microsoft.WinGet.Client` to parsing localized `winget list` table text in `_parse_winget_table()`. Public winget issues show CLI output can be localized unexpectedly, which makes table-header parsing fragile.
- Verified: executable hashing and VirusTotal URL enrichment run during full scans in `_apply_virustotal_hashes()`. This is useful for audit, but it can add scan time and writes a cache under `%APPDATA%\AppList`; the GUI has no privacy/performance toggle for hash enrichment.
- Verified: `write_winget_export()` writes a winget import JSON, but AppList does not validate it against current `winget import` behavior, generate recommended flags, or report unmatched packages in a restore plan.
- Missing guardrails: no visible per-source success/failure summary, no scan duration timeline, no dependency lock/audit step, no schema migration tests for older AppList JSON snapshots, no accessibility/i18n test pass, and no checksum manifest for built executables.

## Architecture Assessment

- Scanner boundary: `applist/scanner.py` is modular but still combines source adapters, enrichment, hashing, winget matching, and orchestration in one class. Extract source result objects with status/warnings so the UI and CLI can surface partial-failure diagnostics.
- Winget boundary: `_run_winget_client_packages()`, `_build_winget_map()`, `_build_upgrade_map()`, and `_parse_winget_table()` should move behind a winget adapter with capability detection, locale-safe parsing, and fixture-based tests.
- Export boundary: `applist/exports.py` has separate writers but no restore-bundle coordinator. Add a bundle writer that emits AppList JSON, winget JSON, pip requirements, Chocolatey config, Markdown/HTML reports, skipped/unmatched package report, and restore command scripts in one folder or zip.
- Data model: `Application` is flat and export-friendly, but it lacks scan confidence, source status, detector rule ID, last verification time, and restore eligibility fields. Add optional fields with JSON schema migration tests before expanding detectors.
- UI boundary: `applist/ui.py` is large and packs layout, state, filtering, exports, context menu actions, and scan orchestration. Diagnostics, settings, and restore-bundle workflow should be extracted into focused helpers before adding more controls.
- Tests: current unittest coverage checks parsing, exports, CLI diff, pagination, and source grouping. Needed next: localized winget fixtures, dependency/version gate tests, AppList JSON backwards compatibility, bundle output tests, failure diagnostics, and accessibility smoke checks for the major UI states.
- Documentation: README is current for v1.6.5, but RESEARCH.md was stale before this pass and ROADMAP.md still contains at least one completed item (`Last-used date per app`). Future roadmap maintenance should delete completed entries when implementation lands.

## Rejected Ideas

- Batch uninstall and leftover deletion: competitors prove demand, but this would change AppList from a low-risk inventory/migration tool into a destructive uninstaller; keep any uninstall support guarded and secondary.
- Real-time install monitor: Revo shows value, but a trace logger is invasive, long-running, and high-maintenance compared with AppList's snapshot/diff model.
- Product-key recovery by default: Belarc shows market demand, but keys are sensitive secrets; keep any implementation explicit opt-in with redaction and exclusion from default exports.
- Cloud sync as a default workflow: useful for multi-device baselines, but local-first export bundles and private user-chosen destinations are safer initial steps.
- Full enterprise agent/backend: Intune, PDQ, Wazuh, and osquery already cover fleet inventory; AppList should stay useful without enrollment, services, or servers.
- CustomTkinter fork/package workaround: PyPI has customtkinter-pyinstaller forks, but the current PyInstaller `--collect-data customtkinter` path is simpler and already aligned with the repo's build script.

## Sources

### Direct OSS and adjacent OSS
- https://github.com/BCUninstaller/Bulk-Crap-Uninstaller
- https://www.bcuninstaller.com/
- https://github.com/Devolutions/UniGetUI
- https://github.com/bfcns/wingetlist
- https://osquery.readthedocs.io/en/stable/deployment/file-integrity-monitoring/
- https://github.com/Awesome-Windows/Awesome

### Commercial and freeware competitors
- https://www.nirsoft.net/utils/uninstall_view.html
- https://www.belarc.com/products/belarc-advisor
- https://www.revouninstaller.com/products/revo-uninstaller-pro/
- https://geekuninstaller.com/
- https://www.pdq.com/pdq-inventory/

### Platform docs and standards
- https://learn.microsoft.com/en-us/windows/package-manager/winget/export
- https://learn.microsoft.com/en-us/windows/package-manager/winget/import
- https://learn.microsoft.com/en-us/windows/package-manager/winget/pinning
- https://learn.microsoft.com/en-us/windows/package-manager/configuration/
- https://learn.microsoft.com/en-us/intune/app-management/discovered-apps
- https://github.com/microsoft/winget-cli/issues/6282
- https://github.com/microsoft/winget-cli/issues/3674
- https://github.com/microsoft/winget-cli/issues/2569
- https://github.com/microsoft/winget-cli/issues/1951
- https://github.com/microsoft/winget-cli/issues/1257

### Community signal
- https://github.com/Devolutions/UniGetUI/issues/5020
- https://github.com/Devolutions/UniGetUI/issues/4645
- https://github.com/Devolutions/UniGetUI/issues/4648
- https://www.reddit.com/r/sysadmin/comments/ud45gh/winget_doesnt_get_enough_love_around_here/

### Dependencies and security
- https://pypi.org/project/customtkinter/
- https://pyinstaller.org/en/stable/CHANGES.html
- https://pypi.org/project/pip-audit/
- https://github.com/advisories/GHSA-p2xp-xx3r-mffc
- https://pip.pypa.io/en/stable/topics/secure-installs/

## Open Questions

- Which Windows versions and PowerShell versions should AppList officially test for v1.7.x: Windows 10 only, Windows 11 only, or both with PowerShell 5.1 and 7?
- Should hash/VirusTotal enrichment remain part of every full scan, or move behind an explicit "security enrichment" setting for speed and privacy?
