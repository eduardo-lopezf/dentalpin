"""Module plugin system public API."""

from .base import BaseModule
from .context import ModuleContext
from .gate import module_gate
from .loader import (
    discover_and_register,
    load_modules,
    mount_active,
    unmount_module,
)
from .manifest import Manifest, ManifestError
from .registry import module_registry
from .service import DoctorReport, ModuleInfo, ModuleOperationError, ModuleService
from .state import ModuleCategory, ModuleState

__all__ = [
    "BaseModule",
    "DoctorReport",
    "Manifest",
    "ManifestError",
    "ModuleCategory",
    "ModuleContext",
    "ModuleInfo",
    "ModuleOperationError",
    "ModuleService",
    "ModuleState",
    "discover_and_register",
    "load_modules",
    "module_gate",
    "module_registry",
    "mount_active",
    "unmount_module",
]
