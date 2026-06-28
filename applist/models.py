"""Application data model."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List


@dataclass
class ScanDiagnostic:
    """Per-source scan status for partial-failure reporting."""
    source: str
    status: str
    row_count: int = 0
    duration_seconds: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class Application:
    """Represents an installed application with all metadata."""
    name: str
    publisher: str = ""
    version: str = ""
    install_date: str = ""
    last_used_date: str = ""
    install_location: str = ""
    executable_path: str = ""
    uninstall_registry_key: str = ""
    uninstall_command: str = ""
    estimated_size: str = ""
    source: str = ""
    architecture: str = ""
    app_type: str = "Desktop"
    winget_id: str = ""
    upgrade_available: str = ""  # "Update Available" if newer version exists in winget, else ""
    ghost: bool = False  # True if install_location doesn't exist on disk
    pin_status: str = ""  # "Pinned", "Gating X.Y.*", "Blocking" — from winget pin list
    sha256_hash: str = ""
    virustotal_url: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def to_export_row(self) -> List[str]:
        return [
            self.name,
            self.publisher,
            self.version,
            self.install_date,
            self.last_used_date,
            self.install_location,
            self.executable_path,
            self.uninstall_registry_key,
            self.uninstall_command,
            self.estimated_size,
            self.source,
            self.architecture,
            self.app_type,
            self.winget_id,
            self.upgrade_available,
            self.pin_status,
            self.sha256_hash,
            self.virustotal_url,
        ]
