"""Base module abstract class for the plugin system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import APIRouter
from sqlalchemy.orm import DeclarativeBase

from .manifest import Manifest

if TYPE_CHECKING:
    from app.core.agents.base import BaseAgent
    from app.core.agents.tools.tool import Tool
    from app.core.privacy import SubjectContributor
    from app.core.record import RecordSection
    from app.core.scheduling import ScheduledJob

    from .context import ModuleContext


class BaseModule(ABC):
    """Abstract base class that all modules must inherit from.

    Each module is a self-contained feature that provides:
    - SQLAlchemy models
    - FastAPI router
    - Event handlers (optional)
    - RBAC permissions (optional)
    - AI agent tools (optional)
    - Lifecycle hooks (optional: install, uninstall, post_upgrade)

    Modules declare metadata through a class-level ``manifest`` dict with at
    least ``name`` and ``version``. The dict is the single source of truth
    for identity and policy — :meth:`get_manifest` parses it via
    :meth:`Manifest.from_dict`, which raises :class:`ManifestError` on
    missing required keys.
    """

    manifest: ClassVar[dict[str, Any]] = {}

    # --- Identity (read directly from the manifest dict) ----------------

    @property
    def name(self) -> str:
        return str(self.manifest["name"])

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @property
    def dependencies(self) -> list[str]:
        return list(self.manifest.get("depends") or [])

    # --- Core contract ---------------------------------------------------

    @abstractmethod
    def get_models(self) -> list[type[DeclarativeBase]]:
        """Return SQLAlchemy models to register with the database."""

    @abstractmethod
    def get_router(self) -> APIRouter:
        """Return FastAPI router to mount at ``/api/v1/{module_name}/``."""

    def get_event_handlers(self) -> dict[str, Callable[..., Any]]:
        """Return map of event_name -> handler function.

        Handlers receive event data as a dict (and optionally a DB session
        when async). They should not return anything.
        """
        return {}

    def get_permissions(self) -> list[str]:
        """Return custom permissions this module adds to RBAC.

        Format: ``'resource.action'`` (no module prefix). The registry
        namespaces them automatically, e.g. ``'patients.read'`` from
        ``clinical`` becomes ``'clinical.patients.read'``.
        """
        return []

    # --- AI agent contract ----------------------------------------------

    def get_tools(self) -> list[Tool]:
        """Return callable actions this module exposes to AI agents.

        Default is an empty list. Tool names are namespaced automatically:
        a tool named ``create_appointment`` from module ``agenda`` is
        registered as ``agenda.create_appointment`` in the global
        :class:`~app.core.agents.tools.registry.ToolRegistry`. See
        ``docs/technical/creating-modules.md`` for the full contract.
        """
        return []

    def get_providers(self) -> dict[type, object]:
        """Implementations of core contracts this module supplies.

        ``{ContractProtocol: instance}`` — see :mod:`app.core.contracts`.
        Consumers reach them through ``contracts.provider()``, which only
        looks at running modules, so supplying one is also how a module
        says "this is available" (ADR 0039). Default: none.
        """
        return {}

    def get_agents(self) -> list[type[BaseAgent]]:
        """Return :class:`~app.core.agents.base.BaseAgent` subclasses
        this module registers.

        Default is an empty list. Override only if the module ships
        agents itself (as opposed to merely exposing tools).
        """
        return []

    # --- Subject rights contract -----------------------------------------

    def get_subject_contributors(self) -> list[SubjectContributor]:
        """Return this module's answers about the data it holds on a patient.

        Default is an empty list, which is only correct for a module that
        stores nothing about a patient. Any module that does **must**
        contribute: core cannot export or erase what it is forbidden to
        import (ADR 0001), so a silent module is data that quietly
        survives an erasure request.

        Each contributor exports its rows and either anonymizes them or
        states a ``retention_reason`` explaining why it legally cannot —
        invoices outlive erasure requests. See
        :mod:`app.core.privacy.subject` and ADR 0026.
        """
        return []

    # --- Clinical record contract ----------------------------------------

    def get_record_sections(self) -> list[RecordSection]:
        """Return what of this module's data belongs in a clinical record.

        Default is an empty list, which is right for most modules: a record is
        what one clinician hands another, so billing, payments and the fiscal
        modules contribute **nothing** even though they hold plenty about the
        patient. That is a different question, answered by
        ``get_subject_contributors()``.

        A module that holds clinical facts — history, notes, charting, images,
        plans — contributes one section per coherent part of them. The
        ``record`` module composes the sections of the modules
        ``core_module.state`` says are installed; when it is not installed,
        nothing calls this.

        See :mod:`app.core.record` for why the vocabulary lives in core, and
        `docs/features/expediente-clinico.md` §2 for the contract's shape.
        """
        return []

    # --- Background jobs -------------------------------------------------

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        """Return periodic jobs this module wants the scheduler to run.

        Default is an empty list. The scheduler registers jobs only for
        *installed/registered* modules, so the scheduler no longer imports
        module task functions directly. See
        :class:`~app.core.scheduling.ScheduledJob`.
        """
        return []

    # --- Lifecycle hooks (v1 defaults are no-ops) ------------------------

    async def install(self, ctx: ModuleContext) -> None:
        """Called on first install after migrations ran.

        Typical use: load ``data/*.yaml`` seed files, provision data.
        """

    async def uninstall(self, ctx: ModuleContext) -> None:
        """Called before Alembic downgrade and data removal.

        Typical use: clean up external resources, stop background tasks.
        """

    async def post_upgrade(self, ctx: ModuleContext, from_version: str) -> None:
        """Called after migrations when upgrading to a newer version.

        Typical use: re-run seeds with new ``noupdate`` flags, backfill.
        """

    # --- Manifest accessor ----------------------------------------------

    def get_manifest(self) -> Manifest:
        """Return the parsed manifest. Raises ``ManifestError`` when the
        ``manifest`` class attribute is missing required keys."""
        return Manifest.from_dict(self.manifest)
