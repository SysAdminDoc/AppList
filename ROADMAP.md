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
