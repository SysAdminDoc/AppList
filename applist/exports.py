"""Export writers for all supported output formats."""

import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import APP_NAME, APP_VERSION
from .models import Application


def write_txt_export(apps: List[Application], filepath: str):
    """Write applications to a TXT report."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write(f"  {APP_NAME} - Application Inventory Report\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Total Applications: {len(apps)}\n")
        f.write("=" * 100 + "\n\n")

        for i, app in enumerate(apps, 1):
            f.write(f"[{i:04d}] {app.name}\n")
            f.write("-" * 80 + "\n")
            if app.publisher:
                f.write(f"       Publisher:        {app.publisher}\n")
            if app.version:
                f.write(f"       Version:          {app.version}\n")
            if app.install_date:
                f.write(f"       Install Date:     {app.install_date}\n")
            if app.last_used_date:
                f.write(f"       Last Used:        {app.last_used_date}\n")
            if app.install_location:
                f.write(f"       Install Location: {app.install_location}\n")
            if app.uninstall_registry_key:
                f.write(f"       Registry Key:     {app.uninstall_registry_key}\n")
            if app.uninstall_command:
                f.write(f"       Uninstall Cmd:    {app.uninstall_command}\n")
            if app.estimated_size:
                f.write(f"       Size:             {app.estimated_size}\n")
            f.write(f"       Type:             {app.app_type}\n")
            f.write(f"       Source:           {app.source}\n")
            f.write("\n")

        f.write("=" * 100 + "\n")
        f.write("  End of Report\n")
        f.write("=" * 100 + "\n")


def write_csv_export(apps: List[Application], filepath: str):
    """Write applications to CSV."""
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Application Name",
            "Publisher",
            "Version",
            "Install Date",
            "Last Used",
            "Install Location",
            "Registry Key",
            "Uninstall Command",
            "Estimated Size",
            "Source",
            "Architecture",
            "Type",
            "Winget ID",
            "Update Available",
            "Pin Status",
        ])
        for app in apps:
            writer.writerow(app.to_export_row())


def get_markdown_groups(apps: List[Application]) -> List[Tuple[str, List[Application]]]:
    """Group applications for Markdown export without dropping unknown types."""
    group_titles = {
        "Desktop": "Desktop Apps",
        "Store App": "Store / UWP Apps",
        "Desktop (Unregistered)": "Unregistered (Program Files)",
        "Chocolatey": "Chocolatey Packages",
        "Scoop": "Scoop Apps",
        "Python Package": "Python Packages (pip)",
    }
    group_order = [
        "Desktop",
        "Store App",
        "Desktop (Unregistered)",
        "Chocolatey",
        "Scoop",
        "Python Package",
    ]
    groups: Dict[str, List[Application]] = {}
    for app in apps:
        groups.setdefault(app.app_type or "Unknown", []).append(app)

    ordered_types = [app_type for app_type in group_order if app_type in groups]
    ordered_types.extend(
        sorted(app_type for app_type in groups if app_type not in group_titles)
    )
    return [(group_titles.get(app_type, app_type), groups[app_type]) for app_type in ordered_types]


def write_markdown_export(apps: List[Application], filepath: str):
    """Write applications to a Markdown report grouped by type."""
    hostname = os.environ.get("COMPUTERNAME", "Unknown")
    username = os.environ.get("USERNAME", "Unknown")

    def _md_row(i: int, app: Application) -> str:
        name = app.name.replace("|", "\\|")
        pub = app.publisher.replace("|", "\\|")
        wid = app.winget_id if app.winget_id else ""
        return f"| {i} | {name} | {pub} | {app.version} | {app.install_date} | {app.last_used_date} | {app.estimated_size} | {wid} |\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Application Inventory — {hostname}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Machine:** `{hostname}` / `{username}`  \n")
        f.write(f"**Total:** {len(apps)} applications  \n\n")
        f.write("---\n\n")

        for group_name, group in get_markdown_groups(apps):
            if not group:
                continue
            f.write(f"## {group_name} ({len(group)})\n\n")
            f.write("| # | Name | Publisher | Version | Install Date | Last Used | Size | Winget ID |\n")
            f.write("|---|------|-----------|---------|--------------|-----------|------|-----------|\n")
            for i, app in enumerate(group, 1):
                f.write(_md_row(i, app))
            f.write("\n")


def write_json_export(apps: List[Application], filepath: str):
    """Write applications to AppList JSON."""
    hostname = os.environ.get("COMPUTERNAME", "Unknown")
    export_data = {
        "schema": f"AppList/{APP_VERSION}",
        "generated": datetime.now().isoformat(),
        "machine": hostname,
        "total": len(apps),
        "applications": [app.to_dict() for app in apps],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)


def write_winget_export(apps: List[Application], filepath: str) -> int:
    """Write matched apps as winget import-compatible JSON and return count."""
    winget_apps = [a for a in apps if a.winget_id]
    if not winget_apps:
        raise ValueError("No applications with winget IDs are available to export.")

    packages_list = [
        {
            "PackageIdentifier": a.winget_id,
            "PackageVersion": a.version,
            "PackageName": a.name,
            "PackageSource": "winget",
        }
        for a in winget_apps
    ]
    export_data = {
        "$schema": "https://aka.ms/winget-packages.schema.2.0.json",
        "CreationDate": datetime.now().isoformat(),
        "WinGetVersion": "1.0.0",
        "Sources": [
            {
                "SourceDetails": {
                    "Argument": "https://cdn.winget.microsoft.com/cache",
                    "Identifier": "Microsoft.Winget.Source_8wekyb3d8bbwe",
                    "Name": "winget",
                    "Type": "Microsoft.PreIndexed.Package",
                },
                "Packages": packages_list,
            }
        ],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    return len(winget_apps)


def write_pip_requirements_export(apps: List[Application], filepath: str) -> int:
    """Write pip packages as a requirements.txt (package==version per line)."""
    pip_apps = [a for a in apps if a.app_type == "Python Package"]
    if not pip_apps:
        raise ValueError("No Python (pip) packages are available to export.")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Generated by {APP_NAME} v{APP_VERSION}\n")
        f.write(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for app in sorted(pip_apps, key=lambda a: a.name.lower()):
            if app.version:
                f.write(f"{app.name}=={app.version}\n")
            else:
                f.write(f"{app.name}\n")
    return len(pip_apps)


def write_choco_export(apps: List[Application], filepath: str) -> int:
    """Write Chocolatey packages as a packages.config XML file."""
    import xml.etree.ElementTree as ET

    choco_apps = [a for a in apps if a.app_type == "Chocolatey"]
    if not choco_apps:
        raise ValueError("No Chocolatey packages are available to export.")

    root = ET.Element("packages")
    for app in sorted(choco_apps, key=lambda a: a.name.lower()):
        attrs = {"id": app.name}
        if app.version:
            attrs["version"] = app.version
        ET.SubElement(root, "package", **attrs)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with open(filepath, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
    return len(choco_apps)


def diff_json_snapshots(old_path: str, new_path: str) -> Dict[str, Any]:
    """Compare two AppList JSON snapshots and return Added/Removed/VersionChanged report."""
    with open(old_path, encoding="utf-8") as f:
        old_data = json.load(f)
    with open(new_path, encoding="utf-8") as f:
        new_data = json.load(f)

    old_apps = {a["name"]: a for a in old_data.get("applications", [])}
    new_apps = {a["name"]: a for a in new_data.get("applications", [])}

    added = []
    removed = []
    version_changed = []

    for name, app in new_apps.items():
        if name not in old_apps:
            added.append(app)
        else:
            old_ver = old_apps[name].get("version", "")
            new_ver = app.get("version", "")
            if old_ver != new_ver and (old_ver or new_ver):
                version_changed.append({
                    "name": name,
                    "publisher": app.get("publisher", ""),
                    "old_version": old_ver,
                    "new_version": new_ver,
                    "app_type": app.get("app_type", ""),
                    "source": app.get("source", ""),
                })

    for name, app in old_apps.items():
        if name not in new_apps:
            removed.append(app)

    return {
        "schema": f"AppList-Diff/{APP_VERSION}",
        "generated": datetime.now().isoformat(),
        "old_snapshot": {
            "file": old_path,
            "machine": old_data.get("machine", ""),
            "generated": old_data.get("generated", ""),
            "total": old_data.get("total", len(old_apps)),
        },
        "new_snapshot": {
            "file": new_path,
            "machine": new_data.get("machine", ""),
            "generated": new_data.get("generated", ""),
            "total": new_data.get("total", len(new_apps)),
        },
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "version_changed": len(version_changed),
        },
        "added": sorted(added, key=lambda a: a.get("name", "").lower()),
        "removed": sorted(removed, key=lambda a: a.get("name", "").lower()),
        "version_changed": sorted(version_changed, key=lambda a: a.get("name", "").lower()),
    }


def write_diff_report(diff: Dict[str, Any], filepath: Optional[str] = None) -> str:
    """Write a diff report to file or return as string."""
    lines = []
    lines.append("AppList Diff Report")
    lines.append(f"Generated: {diff['generated']}")
    lines.append("")
    lines.append(f"Old: {diff['old_snapshot']['file']} ({diff['old_snapshot']['machine']}, "
                 f"{diff['old_snapshot']['total']} apps, {diff['old_snapshot']['generated']})")
    lines.append(f"New: {diff['new_snapshot']['file']} ({diff['new_snapshot']['machine']}, "
                 f"{diff['new_snapshot']['total']} apps, {diff['new_snapshot']['generated']})")
    lines.append("")
    lines.append(f"Summary: +{diff['summary']['added']} added, "
                 f"-{diff['summary']['removed']} removed, "
                 f"~{diff['summary']['version_changed']} version changed")
    lines.append("=" * 80)

    if diff["added"]:
        lines.append("")
        lines.append(f"ADDED ({len(diff['added'])})")
        lines.append("-" * 40)
        for app in diff["added"]:
            pub = f" ({app.get('publisher', '')})" if app.get("publisher") else ""
            ver = f" v{app.get('version', '')}" if app.get("version") else ""
            lines.append(f"  + {app['name']}{ver}{pub}")

    if diff["removed"]:
        lines.append("")
        lines.append(f"REMOVED ({len(diff['removed'])})")
        lines.append("-" * 40)
        for app in diff["removed"]:
            pub = f" ({app.get('publisher', '')})" if app.get("publisher") else ""
            ver = f" v{app.get('version', '')}" if app.get("version") else ""
            lines.append(f"  - {app['name']}{ver}{pub}")

    if diff["version_changed"]:
        lines.append("")
        lines.append(f"VERSION CHANGED ({len(diff['version_changed'])})")
        lines.append("-" * 40)
        for app in diff["version_changed"]:
            lines.append(f"  ~ {app['name']}: {app['old_version']} -> {app['new_version']}")

    report = "\n".join(lines) + "\n"

    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)

    return report


def write_html_export(apps: List[Application], filepath: str):
    """Write a self-contained HTML dashboard with sortable, searchable table."""
    import html as html_mod
    hostname = os.environ.get("COMPUTERNAME", "Unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build table rows
    rows_html = []
    for app in apps:
        pin = html_mod.escape(app.pin_status) if app.pin_status else ""
        upgrade = html_mod.escape(app.upgrade_available) if app.upgrade_available else ""
        ghost_cls = ' class="ghost"' if app.ghost else (' class="update"' if app.upgrade_available else "")
        rows_html.append(
            f"<tr{ghost_cls}>"
            f"<td>{html_mod.escape(app.name)}</td>"
            f"<td>{html_mod.escape(app.publisher)}</td>"
            f"<td>{html_mod.escape(app.version)}</td>"
            f"<td>{html_mod.escape(app.install_date)}</td>"
            f"<td>{html_mod.escape(app.last_used_date)}</td>"
            f"<td>{html_mod.escape(app.app_type)}</td>"
            f"<td>{html_mod.escape(app.source)}</td>"
            f"<td>{html_mod.escape(app.estimated_size)}</td>"
            f"<td>{html_mod.escape(app.winget_id)}</td>"
            f"<td>{upgrade}</td>"
            f"<td>{pin}</td>"
            f"<td>{html_mod.escape(app.architecture)}</td>"
            f"<td>{html_mod.escape(app.install_location)}</td>"
            f"</tr>"
        )
    table_body = "\n".join(rows_html)

    type_counts: Dict[str, int] = {}
    for app in apps:
        type_counts[app.app_type] = type_counts.get(app.app_type, 0) + 1
    stat_cards = "".join(
        f'<div class="stat-card"><div class="stat-value">{count}</div>'
        f'<div class="stat-label">{html_mod.escape(app_type)}</div></div>'
        for app_type, count in sorted(type_counts.items(), key=lambda x: -x[1])
    )

    total = len(apps)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AppList - {html_mod.escape(hostname)}</title>
<style>
:root {{
  --bg: #1e1e2e; --surface: #313244; --overlay: #45475a;
  --text: #cdd6f4; --subtext: #a6adc8; --blue: #89b4fa;
  --green: #a6e3a1; --yellow: #f9e2af; --red: #f38ba8;
  --mauve: #cba6f7; --border: #585b70;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); }}
.header {{ background: var(--surface); padding: 24px 32px; border-bottom: 1px solid var(--border); }}
.header h1 {{ font-size: 22px; font-weight: 700; }}
.header .meta {{ color: var(--subtext); font-size: 13px; margin-top: 4px; }}
.stats {{ display: flex; gap: 12px; padding: 18px 32px; flex-wrap: wrap; }}
.stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 20px; min-width: 120px; }}
.stat-value {{ font-size: 24px; font-weight: 700; color: var(--blue); }}
.stat-label {{ font-size: 12px; color: var(--subtext); margin-top: 2px; }}
.toolbar {{ padding: 8px 32px 12px; display: flex; gap: 12px; align-items: center; }}
.toolbar input {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 6px; font-size: 14px; width: 320px; outline: none; }}
.toolbar input:focus {{ border-color: var(--blue); }}
.toolbar .count {{ color: var(--subtext); font-size: 13px; margin-left: auto; }}
.table-wrap {{ padding: 0 32px 32px; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: var(--surface); position: sticky; top: 0; cursor: pointer; user-select: none;
      padding: 10px 12px; text-align: left; border-bottom: 2px solid var(--border); white-space: nowrap; }}
th:hover {{ background: var(--overlay); }}
th.sorted-asc::after {{ content: ' \\25B2'; font-size: 10px; }}
th.sorted-desc::after {{ content: ' \\25BC'; font-size: 10px; }}
td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; max-width: 320px; overflow: hidden; text-overflow: ellipsis; }}
tr:hover td {{ background: var(--overlay); }}
tr.ghost td {{ color: var(--yellow); }}
tr.update td {{ color: var(--blue); }}
</style>
</head>
<body>
<div class="header">
  <h1>AppList &mdash; Application Inventory</h1>
  <div class="meta">Machine: {html_mod.escape(hostname)} &middot; Generated: {html_mod.escape(timestamp)} &middot; Total: {total} applications</div>
</div>
<div class="stats">
  <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">Total</div></div>
  {stat_cards}
</div>
<div class="toolbar">
  <input id="search" type="text" placeholder="Search applications..." oninput="filterTable()">
  <span class="count" id="count">Showing {total} of {total}</span>
</div>
<div class="table-wrap">
<table id="appTable">
<thead><tr>
  <th onclick="sortTable(0)">Application</th>
  <th onclick="sortTable(1)">Publisher</th>
  <th onclick="sortTable(2)">Version</th>
  <th onclick="sortTable(3)">Installed</th>
  <th onclick="sortTable(4)">Last Used</th>
  <th onclick="sortTable(5)">Type</th>
  <th onclick="sortTable(6)">Source</th>
  <th onclick="sortTable(7)">Size</th>
  <th onclick="sortTable(8)">Winget ID</th>
  <th onclick="sortTable(9)">Upgrade</th>
  <th onclick="sortTable(10)">Pin</th>
  <th onclick="sortTable(11)">Arch</th>
  <th onclick="sortTable(12)">Location</th>
</tr></thead>
<tbody>
{table_body}
</tbody>
</table>
</div>
<script>
let sortCol=-1, sortAsc=true;
function sortTable(col) {{
  const table = document.getElementById('appTable');
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const ths = table.tHead.rows[0].cells;
  for (let th of ths) th.className = '';
  if (sortCol === col) {{ sortAsc = !sortAsc; }} else {{ sortCol = col; sortAsc = true; }}
  ths[col].className = sortAsc ? 'sorted-asc' : 'sorted-desc';
  rows.sort((a, b) => {{
    let va = a.cells[col].textContent.toLowerCase();
    let vb = b.cells[col].textContent.toLowerCase();
    return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  const rows = document.getElementById('appTable').tBodies[0].rows;
  let visible = 0;
  for (let row of rows) {{
    const text = row.textContent.toLowerCase();
    const show = !q || text.includes(q);
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  }}
  document.getElementById('count').textContent = 'Showing ' + visible + ' of ' + {total};
}}
</script>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
