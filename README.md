# AppList

**Professional Windows Application Inventory Scanner**

A premium-grade tool for scanning, cataloging, and exporting all installed applications on your Windows system. Perfect for system migrations, documentation, and reinstallation planning.

---

## Features

### Comprehensive Scanning
- **Registry Scanning** - Scans all uninstall registry keys:
  - HKEY_LOCAL_MACHINE (64-bit applications)
  - HKEY_LOCAL_MACHINE\WOW6432Node (32-bit applications)  
  - HKEY_CURRENT_USER (user-installed applications)
- **Microsoft Store Apps** - Detects UWP/AppX packages via PowerShell
- **Program Files Scanning** - Finds unregistered applications in Program Files directories

### Detailed Information Captured
- Application name
- Publisher/vendor
- Version number
- Installation date
- Installation location (disk path)
- Registry uninstall key path
- Uninstall command
- Estimated size
- Application type (Desktop/Store/Unregistered)
- Architecture (32-bit/64-bit/UWP)

### Premium Interface
- Dark theme with professional aesthetics
- Dark Windows title bar integration
- Real-time progress tracking
- Statistics dashboard with card widgets
- Sortable columns (click headers)
- Live search filtering
- Category filtering (Desktop/Store/Unregistered)
- Context menu with quick actions

### Export Options
- **TXT Export** - Formatted report with full details
- **CSV Export** - Spreadsheet-compatible for Excel/Google Sheets

---

## Installation

### Prerequisites
- Windows 10/11
- Python 3.8 or higher

### Run the Application

Simply run the script - dependencies are installed automatically on first launch:

```bash
python AppList.py
```

Or double-click `AppList.py` in Windows Explorer.

---

## Usage

1. **Launch** the application
2. Click **"Scan System"** to begin comprehensive scanning
3. Use the **search bar** to find specific applications
4. Use the **filter dropdown** to show only certain types
5. **Click column headers** to sort
6. **Right-click** any item for context menu options
7. **Double-click** to open the install location
8. **Export** your list as TXT or CSV for your records

---

## Export Formats

### TXT Format
Human-readable report with:
- Header with generation timestamp
- Numbered list of all applications
- Full details for each application
- Professional formatting

### CSV Format
Spreadsheet-ready with columns:
- Application Name, Publisher, Version, Install Date
- Install Location, Registry Key, Uninstall Command
- Estimated Size, Source, Architecture, Type

---

## Tips for Windows Reinstallation

1. Run a full scan before reinstalling Windows
2. Export to both TXT (for reading) and CSV (for tracking)
3. The TXT file serves as a checklist during reinstallation
4. Use the CSV in Excel to mark off apps as you reinstall them
5. Note the install locations - some apps may need special paths

---

## Technical Notes

- Runs with elevated privileges for complete registry access
- Automatically filters out:
  - System components
  - Windows updates
  - Framework packages
  - Duplicate entries
- DPI-aware for sharp rendering on high-resolution displays
- Thread-safe scanning with cancellation support
- Auto-installs dependencies on first run

---

## License

MIT License - Free for personal and commercial use.

---

*AppList v1.0.0*
