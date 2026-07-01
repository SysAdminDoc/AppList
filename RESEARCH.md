# Research — AppList

## Executive Summary
AppList is a local-first Windows application inventory and rebuild-planning tool: it scans registry, Store/AppX, Program Files, Chocolatey, Scoop, pip, winget, recent-use artifacts, executable hashes, and package-manager consistency, then exports reports, diffs, and restore bundles. Its strongest current shape is not package installation or cleanup; it is trustworthy, read-mostly software-state capture for rebuilds, audits, and migration handoffs. Highest-value direction: harden data safety and packaged-EXE reliability first, then add privacy-safe sharing, validated restore bundles, operator-visible diagnostics, standard SBOM output, and remote/offline collection paths without turning AppList into a destructive uninstaller.

Top opportunities, in priority order:
- Guard frozen EXE pip scanning so `AppList.exe` never recursively launches itself through `sys.executable -m pip`.
- Make restore bundle writes non-destructive and atomic for existing folders.
- Add a restore-bundle validator that proves generated winget, pip, Chocolatey, manifest, and restore scripts are internally consistent.
- Add scan modes for offline/no-network/no-hash runs with visible per-source durations and warnings.
- Add redacted exports for reports that can be shared without machine names, user paths, registry keys, uninstall commands, and hashes.
- Surface scan diagnostics in the GUI and CLI as first-class results, not only status text and optional export sections.
- Add CycloneDX/PURL export for security/compliance tooling while preserving AppList JSON as the native snapshot format.
- Add remote live inventory as a separate connector, distinct from the existing offline-import roadmap item.

## Product Map
- Core workflows: run a local scan; filter, sort, group, and inspect installed apps; export TXT/CSV/Markdown/JSON/HTML/package-manager files; diff AppList JSON snapshots; create restore bundles with reinstall inputs and unmatched-package reports.
- User personas: Windows rebuild users, IT operators preparing reinstall kits, sysadmins auditing a single machine, power users checking package-manager coverage, maintainers validating local software state before replacement or repair.
- Platforms and distribution: Windows 10/11, Python/customtkinter/tkinter desktop GUI, CLI mode, PyInstaller one-file Windows executable, MIT license.
- Key integrations and data flows: Windows uninstall registry keys, `Get-AppxPackage`, Program Files/local app path scans, Chocolatey `.nuspec`, Scoop manifests, `pip list --format=json`, `Microsoft.WinGet.Client`, `winget.exe`, UserAssist, Prefetch, SHA-256 executable hashes, VirusTotal URLs, AppList JSON, winget import JSON, pip requirements, Chocolatey `packages.config`, restore bundle ZIP/folder output.

## Competitive Landscape
- BCUninstaller: does broad installed-app detection, portable/orphaned app detection, batch uninstall, leftover cleanup, startup management, console automation, and filter presets well. AppList should learn its detector breadth and export/script discipline; avoid destructive cleanup and bulk uninstall as default workflows.
- UniGetUI: does multi-package-manager GUI breadth, update/install/uninstall operations, translations, package details, package-manager backups, and enterprise stewardship well. AppList should learn from its package-manager breadth, diagnostics, and localization; avoid background update behavior and package-manager mutation because AppList's safer value is inventory and migration evidence.
- NirSoft UninstallView: does fast portable software inventory, remote-machine inventory, external-drive/offline-style inventory, command-line export, and multi-format output well. AppList should learn remote/offline collection and headless reporting; avoid a bare table-only UX that loses restore context.
- Geek Uninstaller and Revo Uninstaller Pro: do forced uninstall, leftover scanning, Store-app handling, portability, install tracing, and clear user-facing state labels well. AppList should learn clear state/recovery labels; avoid traced installs and leftover deletion unless explicitly opt-in and reversible.
- Belarc Advisor: does local-only PC profile reports with software, hardware, missing hotfixes, antivirus status, security benchmarks, and license details well. AppList should learn privacy-forward local report positioning and compliance summaries; avoid collecting license keys or secrets by default.
- PDQ Inventory and Lansweeper: do device grouping, custom scanners, software counts, version risk, usage/license correlation, vulnerability correlation, and centralized reports well. AppList should learn custom scanners, validated inventory, and compliance deltas; avoid server enrollment and backend requirements.
- osquery/Fleet and OCS Inventory: do structured table schemas, cross-platform inventory, plugins, agents, and remote collection well. AppList should learn schema discipline and pluggable source adapters; avoid becoming a long-running fleet agent.

## Security, Privacy, and Reliability
- Verified: `applist/scanner.py:907-918` calls `[sys.executable, "-m", "pip", "list", "--format=json"]`; PyInstaller documents that `sys.executable` is the bundled app executable in frozen apps, and pip documents `py -m pip list` as the Windows command. This is a packaged-EXE reliability risk.
- Verified: `applist/exports.py:342-346` deletes an existing restore-bundle output folder with `shutil.rmtree(root)` before writing. A mistyped or reused folder path can destroy user data; bundle writes need explicit overwrite handling and temp-then-rename behavior.
- Verified: `write_json_export()` includes `machine`, full install paths, executable paths, registry keys, uninstall commands, hashes, and VirusTotal URLs (`applist/exports.py:196-209`; `applist/models.py:47-68`). Default exports are useful but not privacy-safe for sharing.
- Verified: full scans always run last-used activity and executable hashing (`applist/scanner.py:1369-1378`) after source scans. There is no GUI/CLI no-network or no-hash scan mode even though winget has an open request for inventory without network/source lookup.
- Verified: winget structured reads are attempted first, but scanner fallback still parses winget text/table output (`applist/scanner.py:946-1186`). Current winget issues show automation failures in system context and noninteractive/source contexts, so AppList should keep structured-first behavior and report capability failures clearly.
- Verified: local `python -m pip_audit -r requirements.txt --format=json` found no known vulnerabilities in the pinned dependency set on 2026-07-01. The verification command emitted cache-deserialization warnings from CacheControl, but returned success and no vulnerable dependencies.
- Verified: `python -m unittest discover -s tests` passed 26 tests on 2026-07-01; one expected scanner warning appeared from a mocked registry denial.
- Missing guardrails: no redaction mode, no bundle validator, no non-destructive bundle folder overwrite policy, no packaged-EXE pip guard test, no durable scan log, no first-class GUI diagnostic table, and no source adapter contract to keep new detectors from further expanding the scanner monolith.

## Architecture Assessment
- Scanner boundary: `applist/scanner.py` has useful per-source methods and diagnostics, but orchestration, source adapters, enrichment, winget matching, hashing, and package consistency still live in one class. A `SourceResult`/adapter contract would let each source report rows, duration, warnings, capability checks, and recovery hints consistently.
- Export boundary: `applist/exports.py` has focused writer functions, but restore bundles need a coordinator-level safety layer: validate before writing, write to a temporary directory, refuse existing non-empty folders without an explicit overwrite flag, and emit a machine-readable validation report.
- Data model: `Application` is flat and export-friendly, but it lacks source confidence, detector ID, restore eligibility, privacy classification, and last verification timestamps. Add optional fields only after the existing "AppList JSON schema and migration fixtures" roadmap item lands.
- UI boundary: `applist/ui.py` combines layout, filtering, pagination, scan orchestration, export commands, and context-menu actions. Diagnostics, settings, and restore validation should move into smaller helpers before the GUI grows further.
- Test gaps: add tests for `sys.frozen` pip behavior, bundle overwrite refusal, bundle validation failures, redacted export output, no-network/no-hash modes, diagnostics serialization, and source adapter compatibility fixtures.
- Documentation gaps: README documents current features well, but implementation work should update CLI examples for scan modes, redaction, bundle validation, and SBOM output when those land. Existing roadmap items for JSON schema, offline inventory import, custom detector rules, accessibility/localization, and release checksum manifests remain supported by current research and are not duplicated below.

## Rejected Ideas
- Batch uninstall and leftover deletion: BCUninstaller, Geek Uninstaller, and Revo prove demand, but default destructive cleanup contradicts AppList's safer inventory/migration role.
- Automatic app updates or "update all" operations: UniGetUI and winget cover this; AppList should report update state and restore plans, not mutate packages by default.
- Product-key recovery by default: Belarc-style license visibility is useful, but keys are secrets; keep the existing opt-in roadmap item constrained and excluded from default exports.
- Cloud sync as the primary baseline store: useful eventually, but local redacted exports and restore bundles are safer first; default cloud upload would weaken local-first trust.
- Full enterprise agent/backend: PDQ, Lansweeper, osquery/Fleet, Intune, and OCS already own continuous fleet inventory; AppList should stay useful without services, enrollment, or a server.
- Mobile companion app: public sources did not show a credible mobile workflow that improves Windows-local inventory, rebuild planning, or restore validation better than redacted exports and remote/offline collection.
- Forking or replacing CustomTkinter now: accessibility and scaling gaps are real, but AppList can first improve focus order, high-DPI smoke checks, and string centralization within the existing stack.

## Sources
### Direct OSS and adjacent OSS
- https://github.com/BCUninstaller/Bulk-Crap-Uninstaller
- https://github.com/Devolutions/UniGetUI
- https://github.com/microsoft/winget-cli
- https://github.com/osquery/osquery
- https://fleetdm.com/tables/programs
- https://ocsinventory-ng.org/?lang=en

### Commercial and freeware competitors
- https://www.nirsoft.net/utils/uninstall_view.html
- https://geekuninstaller.com/
- https://www.revouninstaller.com/products/revo-uninstaller-pro/
- https://www.belarc.com/products/belarc-advisor
- https://www.pdq.com/pdq-inventory/
- https://www.lansweeper.com/solutions/use-cases/software-asset-management/

### Platform docs, standards, and ecosystem signal
- https://learn.microsoft.com/en-us/windows/package-manager/winget/list
- https://learn.microsoft.com/en-us/windows/package-manager/winget/export
- https://learn.microsoft.com/en-us/windows/package-manager/winget/import
- https://learn.microsoft.com/en-us/intune/app-management/deployment/enhanced-app-inventory
- https://docs.chocolatey.org/en-us/choco/commands/export/
- https://github.com/ScoopInstaller/Scoop/wiki/Commands
- https://pip.pypa.io/en/stable/cli/pip_list/
- https://cyclonedx.org/specification/overview/
- https://www.packageurl.org/
- https://pypi.org/project/pip-audit/
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
- https://pyinstaller.org/en/stable/runtime-information.html
- https://github.com/TomSchimansky/CustomTkinter/issues/2786
- https://github.com/TomSchimansky/CustomTkinter/wiki/Scaling
- https://github.com/microsoft/winget-cli/issues/4449
- https://github.com/microsoft/winget-cli/issues/5572
- https://github.com/microsoft/winget-cli/issues/5991
- https://github.com/microsoft/winget-cli/discussions/6192

## Open Questions
- None that block prioritization.
