"""Application data model."""

import hashlib
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Mapping


def _identity_normalize(value: Any) -> str:
    """Normalize identity evidence without exposing the evidence itself."""
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text).casefold()


def _identity_path(value: Any) -> str:
    """Normalize a Windows path before hashing it into an identity."""
    text = str(value or "").strip()
    if not text:
        return ""
    return os.path.normcase(os.path.normpath(text))


def build_application_identity(
    *,
    name: Any = "",
    publisher: Any = "",
    version: Any = "",
    source: Any = "",
    architecture: Any = "",
    app_type: Any = "",
    install_location: Any = "",
    executable_path: Any = "",
    uninstall_registry_key: Any = "",
    uninstall_command: Any = "",
    winget_id: Any = "",
    identity_key: Any = "",
) -> str:
    """Return a stable, privacy-safe identity key for an application record.

    Native identifiers and installation evidence are preferred over display
    names. The evidence is hashed so registry keys and local paths do not leak
    into machine-readable exports.
    """
    existing = str(identity_key or "").strip()
    if existing:
        return existing

    source_value = _identity_normalize(source or app_type or "unknown")
    if uninstall_registry_key:
        evidence = f"registry:{_identity_normalize(uninstall_registry_key)}"
    elif winget_id:
        evidence = f"winget:{_identity_normalize(winget_id)}"
    elif install_location:
        evidence = f"location:{_identity_path(install_location)}"
    elif executable_path:
        evidence = f"executable:{_identity_path(executable_path)}"
    elif uninstall_command:
        evidence = f"command:{_identity_normalize(uninstall_command)}"
    else:
        evidence = "|".join(
            (
                "record",
                _identity_normalize(name),
                _identity_normalize(publisher),
                _identity_normalize(architecture),
            )
        )

    payload = f"{source_value}|{evidence}".encode("utf-8", errors="replace")
    return f"app:{hashlib.sha256(payload).hexdigest()}"


def application_identity(record: Mapping[str, Any]) -> str:
    """Resolve identity for current or legacy JSON application dictionaries."""
    return build_application_identity(**{
        field_name: record.get(field_name, "")
        for field_name in (
            "name",
            "publisher",
            "version",
            "source",
            "architecture",
            "app_type",
            "install_location",
            "executable_path",
            "uninstall_registry_key",
            "uninstall_command",
            "winget_id",
            "identity_key",
        )
    })


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
    identity_key: str = ""
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
    consistency_status: str = ""
    measured_size: str = ""
    bloatware: str = ""
    startup_impact: str = ""  # "High"/"Low" for Startup items (folded in from SoftwareScannerGUI)

    def __post_init__(self):
        self.identity_key = build_application_identity(
            name=self.name,
            publisher=self.publisher,
            version=self.version,
            source=self.source,
            architecture=self.architecture,
            app_type=self.app_type,
            install_location=self.install_location,
            executable_path=self.executable_path,
            uninstall_registry_key=self.uninstall_registry_key,
            uninstall_command=self.uninstall_command,
            winget_id=self.winget_id,
            identity_key=self.identity_key,
        )

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def to_export_row(self) -> List[str]:
        return [
            self.name,
            self.identity_key,
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
            self.consistency_status,
            self.measured_size,
            self.bloatware,
            self.startup_impact,
        ]
