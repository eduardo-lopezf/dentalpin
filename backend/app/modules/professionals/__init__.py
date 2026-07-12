"""Professionals module — clinic dentists and collaborators directory."""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import Professional
from .router import router


class ProfessionalsModule(BaseModule):
    """Owns the clinic-scoped directory of dentists and collaborators."""

    manifest = {
        "name": "professionals",
        "version": "0.1.0",
        "summary": "Dentists and collaborators directory with professional profiles.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "professionals.nav",
                    "icon": "i-lucide-stethoscope",
                    "to": "/professionals",
                    "permission": "professionals.read",
                    "order": 45,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [Professional]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
