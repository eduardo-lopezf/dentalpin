#!/usr/bin/env python3
"""Coverage check for the documentation portal (ADR 0009 / issue #75).

For every module under ``backend/app/modules/<name>/``, verifies that
the documentation contract holds:

- ``docs/technical/<module>/overview.md`` exists.
- ``docs/technical/<module>/permissions.md`` exists when the module
  returns at least one permission from ``get_permissions()``.
- ``docs/technical/<module>/events.md`` exists when the module emits or
  subscribes events.
- Every Nuxt page under ``<module>/frontend/pages/**`` has a matching
  screen file in **both**
  ``docs/user-manual/en/<module>/screens/<slug>.md`` *and*
  ``docs/user-manual/es/<module>/screens/<slug>.md`` with frontmatter
  whose ``route`` field equals the page's route.
- Every ``/api/v1/<module>/...`` path named in **any** markdown under
  ``docs/`` is served by some module's router. Catches an ADR or a tech
  plan that outlives the endpoint it describes.
- Every screen file's frontmatter ``route`` resolves to a real page,
  ``related_endpoints`` (if present) reference paths that exist on the
  module's router, and ``related_permissions`` (if present) are
  returned by the module's ``get_permissions()`` (with the namespace
  prefix stripped or left as-is).

Default mode is **warning-only** (prints findings, exits 0). The
``--strict`` flag turns violations into an exit code 1 and is what the
backfill PR will switch CI to. Today, the warning-only mode runs in the
existing ``catalog-freshness`` CI job.

Companion to ``backend/scripts/generate_catalogs.py``. Shares its
bootstrap, but does **not** mutate any file.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _locate_repo_root() -> Path:
    """Resolve the repo root.

    Order:

    1. ``DENTALPIN_REPO_ROOT`` env var if set (useful in Docker where
       ``/app`` is the backend mount and ``/docs`` is mounted separately —
       set ``DENTALPIN_REPO_ROOT=/`` and ensure both ``/docs`` and
       ``/backend`` exist as symlinks or mounts).
    2. Walk up from this file until we find both ``docs/`` and ``backend/``.

    Works on the GitHub Actions runner (host layout), and in Docker when
    the env var is set.
    """
    override = os.environ.get("DENTALPIN_REPO_ROOT")
    if override:
        root = Path(override).resolve()
        if (root / "docs").is_dir() and (root / "backend").is_dir():
            return root
        raise RuntimeError(
            f"DENTALPIN_REPO_ROOT={override!r} but it doesn't contain both `docs/` and `backend/`."
        )
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "docs").is_dir() and (candidate / "backend").is_dir():
            return candidate
    raise RuntimeError(
        f"Could not locate repo root from {here}. "
        "Set DENTALPIN_REPO_ROOT or run the script from a checkout that "
        "contains both `docs/` and `backend/`."
    )


REPO_ROOT = _locate_repo_root()
BACKEND_ROOT = REPO_ROOT / "backend"
MODULES_ROOT = BACKEND_ROOT / "app" / "modules"
DOCS_ROOT = REPO_ROOT / "docs"
TECHNICAL_ROOT = DOCS_ROOT / "technical"
USER_MANUAL_ROOT = DOCS_ROOT / "user-manual"

LOCALES = ("en", "es")


def _bootstrap_env() -> None:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://stub:stub@localhost:5432/stub",
    )
    os.environ.setdefault("SECRET_KEY", "docs-coverage-stub-key-32chars-minimum")
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("DENTALPIN_DEV_MODULE_SCAN", "true")
    # Run from backend/, or `Settings` picks up the repo-root compose
    # `.env` and rejects its POSTGRES_*/API_BASE_URL keys as extras. See
    # generate_catalogs.py's `_bootstrap_env` for the full reasoning.
    # `scaffold_module_docs` imports this module before touching `app`,
    # so it inherits the fix.
    # Guarded because BACKEND_ROOT is derived from this file's location
    # and only resolves inside a checkout. In the container the script
    # lives at /app/scripts, so it computes a /backend that does not
    # exist — harmless while the value only fed sys.path, fatal the
    # moment something chdir'd to it. There the working directory is
    # already backend's, which is why the container never had the
    # problem this guard's chdir solves.
    if BACKEND_ROOT.is_dir():
        os.chdir(BACKEND_ROOT)
    sys.path.insert(0, str(BACKEND_ROOT))


_bootstrap_env()

from app.core.plugins.loader import discover_modules  # noqa: E402

# ---------------------------------------------------------------------------
# Tiny YAML frontmatter parser.
#
# We deliberately avoid pulling in PyYAML — the schema is fixed (strings,
# lists of strings) and a regex split is enough. If the contract grows
# nested objects, swap this for `yaml.safe_load`.
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    body = text[3:end].strip("\n")
    out: dict[str, object] = {}
    current_list_key: str | None = None
    for raw in body.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - "):
            if current_list_key is None:
                continue
            out.setdefault(current_list_key, [])
            assert isinstance(out[current_list_key], list)
            out[current_list_key].append(raw.removeprefix("  - ").strip())
            continue
        if raw.startswith("- "):  # top-level list — not in our schema
            continue
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            current_list_key = key
            out[key] = []
        else:
            current_list_key = None
            out[key] = value.strip("\"'")
    return out


# ---------------------------------------------------------------------------
# Module discovery + per-module facts
# ---------------------------------------------------------------------------


@dataclass
class ModuleFacts:
    name: str
    permissions: list[str]
    events_emitted: list[str]
    events_consumed: list[str]
    pages: dict[str, Path]  # route -> .vue path
    settings_routes: dict[str, Path]  # route -> plugin that registers it
    endpoints: list[tuple[str, str]]  # (METHOD, full path including /api/v1/<m>)
    has_frontend: bool


HTTP_METHODS = ("get", "post", "put", "patch", "delete")
ROUTER_DECORATOR_RE = re.compile(
    # ``@\w*router.`` and not ``@router.``: the budget module declares its
    # patient-facing endpoints on a second `public_router` that its
    # `get_router()` composes into the same mount (ADR 0006). Matching the
    # name literally made every one of those invisible, so a screen that
    # documented them was told they do not exist.
    r"@\w*router\.(?P<method>get|post|put|patch|delete)\(\s*[\"'](?P<path>[^\"']*)[\"']",
)
# First arg of an event_bus.publish(...) call. Captures the four shapes a
# module can publish through so the "events.md required" rule below fires
# for enum-based and dynamic publishers too, not just string literals
# (audit S4, #94 — the old regex only had a group for the literal case,
# so EventType.X publishers were invisible and the rule never triggered).
PUBLISH_RE = re.compile(
    # ``publish_after_commit(db, EventType.X, ...)`` puts the session first,
    # so the event type is the second argument there (ADR 0019).
    r"event_bus\.publish(?:_after_commit\s*\(\s*[\w.]+\s*,|\s*\()\s*(?:"
    r"EventType\.(?P<const>[A-Z_]+)"
    r"|(?P<enum>[A-Z]\w*\.[A-Z_]+)"
    r"|[\"'](?P<lit>[\w.]+)[\"']"
    r"|(?P<var>[a-z_]\w*)"
    r")"
)


def _scan_module_endpoints(mod_dir: Path, mount_prefix: str) -> list[tuple[str, str]]:
    """Return [(METHOD, '/api/v1/<m>/<path>')] for every router decorator."""
    endpoints: list[tuple[str, str]] = []
    for py_file in mod_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        # Cheap skip, and it has to agree with the decorator regex above:
        # keyed to "@router." it threw away `public_router.py` before the
        # widened pattern ever saw it, which is a quiet way to undo the fix.
        if "router." not in text:
            continue
        for match in ROUTER_DECORATOR_RE.finditer(text):
            method = match.group("method").upper()
            sub_path = match.group("path") or ""
            full = f"{mount_prefix}{sub_path}".rstrip("/") or mount_prefix
            endpoints.append((method, full))
    return endpoints


def _scan_module_publishers(mod_dir: Path) -> set[str]:
    """Best-effort grep of event_bus.publish callsites in the module."""
    out: set[str] = set()
    for py_file in mod_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        if "event_bus.publish" not in text:
            continue
        for match in PUBLISH_RE.finditer(text):
            token = (
                match.group("const")
                or match.group("lit")
                or match.group("enum")
                or match.group("var")
            )
            if token:
                out.add(token)
    return out


def _page_to_route(rel: Path) -> str:
    """Convert pages/foo/[id].vue → /foo/[id], pages/foo/index.vue → /foo."""
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts.pop()
    return "/" + "/".join(parts) if parts else "/"


def _scan_module_pages(mod_dir: Path) -> dict[str, Path]:
    pages_dir = mod_dir / "frontend" / "pages"
    out: dict[str, Path] = {}
    if not pages_dir.is_dir():
        return out
    for vue in pages_dir.rglob("*.vue"):
        rel = vue.relative_to(pages_dir)
        route = _page_to_route(rel)
        out[route] = vue
    return out


SETTINGS_PAGE_CALL = "registerSettingsPage("
SETTINGS_PATH_RE = re.compile(r"\bpath:\s*['\"]([^'\"]+)['\"]")
SETTINGS_CATEGORY_RE = re.compile(r"\bcategory:\s*['\"]([^'\"]+)['\"]")


def _scan_settings_pages(mod_dir: Path) -> dict[str, Path]:
    """Routes a module contributes through the settings registry.

    A module does not have to own a Nuxt page to own a screen: it can call
    ``registerSettingsPage({path, category})`` from a client plugin, and the
    host serves it from its own ``settings/[category]/[page].vue``. Those
    screens are documented like any other and have a real, reachable route,
    but nothing under ``<module>/frontend/pages/`` corresponds to them — so
    checking the frontmatter route against pages alone reported every one of
    them as unmatched.

    Read by scanning forward from each call rather than by matching the whole
    object literal: the options include an arrow function, and one plugin
    registers two pages in a row.
    """
    out: dict[str, Path] = {}
    plugins_dir = mod_dir / "frontend" / "plugins"
    if not plugins_dir.is_dir():
        return out
    for plugin in sorted(plugins_dir.rglob("*.ts")):
        text = plugin.read_text(encoding="utf-8", errors="replace")
        start = text.find(SETTINGS_PAGE_CALL)
        while start != -1:
            window = text[start : start + 1200]
            path = SETTINGS_PATH_RE.search(window)
            category = SETTINGS_CATEGORY_RE.search(window)
            if path and category:
                out[f"/settings/{category.group(1)}/{path.group(1)}"] = plugin
            start = text.find(SETTINGS_PAGE_CALL, start + len(SETTINGS_PAGE_CALL))
    return out


@lru_cache(maxsize=1)
def _all_app_routes() -> frozenset[str]:
    """Every route the app serves: host pages, module pages, settings screens.

    A module can own a screen without owning a page. `cashbox` is a tab on
    the host's own `/finanzas`; `periodontogram` is a view inside the
    `patients` module's `/patients/[id]`. Both are real places a user lands
    on, and neither is under the documenting module's `pages/`, so matching
    a frontmatter route against that module alone reported them as broken.
    """
    routes: set[str] = set()
    host_pages = REPO_ROOT / "frontend" / "app" / "pages"
    if host_pages.is_dir():
        for vue in host_pages.rglob("*.vue"):
            routes.add(_page_to_route(vue.relative_to(host_pages)))
    for mod_dir in sorted(MODULES_ROOT.iterdir()):
        if mod_dir.is_dir():
            routes.update(_scan_module_pages(mod_dir))
            routes.update(_scan_settings_pages(mod_dir))
    return frozenset(routes)


@lru_cache(maxsize=1)
def _all_app_endpoints() -> frozenset[str]:
    """Every endpoint the API serves, normalised, whichever module owns it.

    A screen is documented by the module that owns the *screen*, and that is
    not always the module that owns the data it reads: `billing`'s
    invoice-from-budget screen fetches the budget, `reports` reads
    `payments`' own report endpoints. Checking only the documenting module's
    router called every one of those a broken reference.
    """
    out: set[str] = set()
    for mod_dir in sorted(MODULES_ROOT.iterdir()):
        if not mod_dir.is_dir():
            continue
        prefix = f"/api/v1/{mod_dir.name}"
        for method, path in _scan_module_endpoints(mod_dir, mount_prefix=prefix):
            out.add(_normalise_endpoint(method, path))
    return frozenset(out)


@lru_cache(maxsize=1)
def _all_app_permissions() -> frozenset[str]:
    """Every permission any module declares, namespaced as `<module>.<perm>`.

    Same reason as the endpoints: a screen can be gated by another module's
    permission, and `catalog`'s treatments screen genuinely needs
    `treatment_plan.plans.read` to show a plan link.
    """
    out: set[str] = set()
    for module in discover_modules():
        for perm in getattr(module, "get_permissions", lambda: [])() or []:
            out.add(f"{module.name}.{perm}")
    return frozenset(out)


def _route_base(route: str) -> str:
    """The page a documented route lands on: no query, Nuxt's bracket params.

    The query is dropped rather than checked. `?tab=cashbox` names a tab
    inside the page, and proving that tab exists means reading the page's
    component state — brittle, and a wrong tab name is a far smaller error
    than a route that goes nowhere. The page itself is still verified.
    """
    base = route.split("?", 1)[0].rstrip("/") or "/"
    return re.sub(r"\{(\w+)\}", r"[\1]", base)


def _collect_facts(module) -> ModuleFacts:
    name = module.name
    mod_dir = MODULES_ROOT / name
    permissions = list(getattr(module, "get_permissions", lambda: [])() or [])
    handlers = getattr(module, "get_event_handlers", lambda: {})() or {}
    events_consumed = sorted(handlers.keys())
    events_emitted = sorted(_scan_module_publishers(mod_dir))
    pages = _scan_module_pages(mod_dir)
    settings_routes = _scan_settings_pages(mod_dir)
    endpoints = _scan_module_endpoints(mod_dir, mount_prefix=f"/api/v1/{name}")
    has_frontend = (mod_dir / "frontend").is_dir()
    return ModuleFacts(
        name=name,
        permissions=permissions,
        events_emitted=events_emitted,
        events_consumed=events_consumed,
        pages=pages,
        settings_routes=settings_routes,
        endpoints=endpoints,
        has_frontend=has_frontend,
    )


# ---------------------------------------------------------------------------
# Screen MD discovery
# ---------------------------------------------------------------------------


@dataclass
class ScreenDoc:
    locale: str  # 'en' | 'es'
    module: str
    path: Path
    frontmatter: dict[str, object]


def _collect_screens(module: str) -> dict[str, list[ScreenDoc]]:
    """{locale: [ScreenDoc, ...]} for every screen MD found for this module."""
    out: dict[str, list[ScreenDoc]] = {loc: [] for loc in LOCALES}
    for locale in LOCALES:
        screens_dir = USER_MANUAL_ROOT / locale / module / "screens"
        if not screens_dir.is_dir():
            continue
        for md in sorted(screens_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = _parse_frontmatter(text)
            out[locale].append(ScreenDoc(locale=locale, module=module, path=md, frontmatter=fm))
    return out


# ---------------------------------------------------------------------------
# The actual checks
# ---------------------------------------------------------------------------


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self) -> bool:
        return not self.errors and not self.warnings


def _normalise_endpoint(method: str, path: str) -> str:
    """`{patient_id}` and `:patient_id` and `[id]` all collapse to `<param>`."""
    norm = re.sub(r"\{[^}]+\}", "<param>", path)
    norm = re.sub(r":[a-zA-Z_][\w]*", "<param>", norm)
    norm = re.sub(r"\[[^\]]+\]", "<param>", norm)
    return f"{method.upper()} {norm.rstrip('/') or '/'}"


def _check_module(facts: ModuleFacts, findings: Findings) -> None:
    name = facts.name
    tech_dir = TECHNICAL_ROOT / name

    # 1. technical/overview.md
    if not (tech_dir / "overview.md").is_file():
        findings.err(
            f"{name}: missing docs/technical/{name}/overview.md "
            "(every module needs a technical overview)."
        )

    # 2. technical/permissions.md when permissions exist
    if facts.permissions and not (tech_dir / "permissions.md").is_file():
        findings.err(
            f"{name}: get_permissions() returns {facts.permissions!r} "
            f"but docs/technical/{name}/permissions.md is missing."
        )

    # 3. technical/events.md when events flow either way
    if (facts.events_emitted or facts.events_consumed) and not (tech_dir / "events.md").is_file():
        findings.err(
            f"{name}: emits/subscribes events "
            f"(emit={facts.events_emitted}, sub={facts.events_consumed}) "
            f"but docs/technical/{name}/events.md is missing."
        )

    # 4. Per-screen coverage in BOTH locales.
    screens_by_locale = _collect_screens(name)
    routes_by_locale = {
        locale: {str(s.frontmatter.get("route") or ""): s for s in docs}
        for locale, docs in screens_by_locale.items()
    }

    for route, page_path in sorted(facts.pages.items()):
        for locale in LOCALES:
            if route not in routes_by_locale[locale]:
                findings.err(
                    f"{name}: page {page_path.relative_to(REPO_ROOT)} "
                    f"(route {route}) has no screen file under "
                    f"docs/user-manual/{locale}/{name}/screens/ "
                    f"(frontmatter route: {route})."
                )

    # 5. Validate every screen MD frontmatter.
    valid_endpoints = {_normalise_endpoint(m, p) for m, p in facts.endpoints}
    for locale, docs in screens_by_locale.items():
        for screen in docs:
            fm = screen.frontmatter
            rel = screen.path.relative_to(REPO_ROOT)
            if "module" not in fm or fm["module"] != name:
                findings.err(
                    f"{rel}: frontmatter `module` must equal '{name}' (found {fm.get('module')!r})."
                )
            route = str(fm.get("route") or "")
            if not route:
                findings.err(f"{rel}: frontmatter `route` is required.")
            elif (
                route not in facts.pages
                and route not in facts.settings_routes
                and _route_base(route) not in _all_app_routes()
            ):
                findings.warn(
                    f"{rel}: frontmatter route {route!r} lands on "
                    f"{_route_base(route)!r}, which is not a page this module "
                    f"owns, a settings screen it registers, or any other page "
                    f"in the app."
                )
            if not fm.get("last_verified_commit"):
                findings.warn(f"{rel}: frontmatter `last_verified_commit` is empty.")

            for ep in fm.get("related_endpoints", []) or []:
                m = re.match(r"\s*([A-Z]+)\s+(.+)\s*$", str(ep))
                if not m:
                    findings.warn(
                        f"{rel}: malformed related_endpoint {ep!r} (expected 'METHOD /path')."
                    )
                    continue
                method, path = m.group(1), m.group(2).strip()
                key = _normalise_endpoint(method, path)
                if key not in valid_endpoints and key not in _all_app_endpoints():
                    findings.warn(
                        f"{rel}: related_endpoint {method} {path} is not on "
                        f"{name}'s router nor any other module's "
                        f"(after normalising path params)."
                    )

            for perm in fm.get("related_permissions", []) or []:
                # Accept both 'patients.read' and 'read'.
                bare = str(perm).split(".", 1)[-1]
                if bare not in facts.permissions and str(perm) not in _all_app_permissions():
                    findings.warn(
                        f"{rel}: related_permission {perm!r} is declared by "
                        f"neither {name} (= {facts.permissions}) nor any "
                        f"other module."
                    )


def _check_orphan_screens(modules: list[str], findings: Findings) -> None:
    """Find screen MDs whose module folder doesn't exist."""
    known = set(modules)
    for locale in LOCALES:
        loc_root = USER_MANUAL_ROOT / locale
        if not loc_root.is_dir():
            continue
        for module_dir in loc_root.iterdir():
            if not module_dir.is_dir():
                continue
            if module_dir.name in {"screens"}:
                continue  # not a module folder
            if module_dir.name not in known:
                findings.warn(
                    f"docs/user-manual/{locale}/{module_dir.name}/: "
                    f"no module called '{module_dir.name}' is loaded."
                )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


# `.` is inside the class so `/export.csv` is captured whole rather than
# truncated to `/export`, which would then look like a route that does
# not exist. Trailing sentence punctuation is stripped after the match.
API_PATH_IN_PROSE = re.compile(r"/api/v1/[A-Za-z0-9_][A-Za-z0-9_{}/.\-]*")


def _check_markdown_api_paths(findings: Findings) -> None:
    """Every ``/api/v1/...`` a markdown file mentions must be a real endpoint.

    The frontmatter check only covers screen docs, so an ADR, a tech plan or
    a module's CLAUDE.md could name a path that does not exist and nothing
    said so. Two did: the budget ADR and its tech plan kept
    ``/api/v1/public/budgets/...`` long after the module's mount made the
    real path ``/api/v1/budget/public/budgets/...``.

    Deliberately narrow, because the alternative is noise:

    * only paths addressed to a known module are checked. Core routers
      (``/api/v1/auth/...``, ``/api/v1/_meta/...``) declare their sub-paths
      away from their mount prefix, so there is no trustworthy surface to
      compare them against — a check that cannot be right is worse than none.
    * ``/api/v1/<module>`` on its own is a mount prefix, not an endpoint.
    * anything with a ``<placeholder>`` is a template in a guide.

    The built portal under ``docs/portal/.vitepress/`` is skipped: it is
    generated output, and its findings would be duplicates of the sources.
    """
    modules = {d.name for d in MODULES_ROOT.iterdir() if d.is_dir() and not d.name.startswith("_")}
    known = {
        _normalise_endpoint("GET", path).split(" ", 1)[1]
        for path in {key.split(" ", 1)[1] for key in _all_app_endpoints()}
    }

    for md in sorted(DOCS_ROOT.rglob("*.md")):
        if ".vitepress" in md.parts:
            continue
        rel = md.relative_to(REPO_ROOT)
        seen: set[str] = set()
        md_text = md.read_text(encoding="utf-8", errors="replace")
        for match in API_PATH_IN_PROSE.finditer(md_text):
            # A path that runs straight into `<token>` or `<id>` is a prose
            # prefix with a placeholder after it, not an endpoint.
            after = md_text[match.end() : match.end() + 1]
            if after in ("<", "*"):
                continue
            path = match.group(0).rstrip("/.,;:")
            # An unclosed `{` means the match ran into a template expression
            # in a code sample — `f"...{setup['patient_id']}..."` — and what
            # was captured is not the path the sample builds.
            if path.count("{") != path.count("}"):
                continue
            segments = path.split("/")
            if len(segments) <= 4 or segments[3] not in modules:
                continue
            if path in seen:
                continue
            seen.add(path)
            if _normalise_endpoint("GET", path).split(" ", 1)[1] not in known:
                findings.warn(f"{rel}: mentions {path}, which no module's router serves.")


def run(strict: bool) -> int:
    findings = Findings()

    modules = list(discover_modules())
    if not modules:
        findings.err(
            "No modules discovered. Ensure DENTALPIN_DEV_MODULE_SCAN=true and "
            "the backend is installed."
        )

    facts_by_name = {m.name: _collect_facts(m) for m in modules}
    for facts in facts_by_name.values():
        _check_module(facts, findings)

    _check_orphan_screens([m.name for m in modules], findings)
    _check_markdown_api_paths(findings)

    if findings.warnings:
        print("Documentation coverage warnings:", file=sys.stderr)
        for w in findings.warnings:
            print(f"  ⚠  {w}", file=sys.stderr)
    if findings.errors:
        print("Documentation coverage errors:", file=sys.stderr)
        for e in findings.errors:
            print(f"  ✗  {e}", file=sys.stderr)

    if findings.ok():
        print("docs coverage OK.")
        return 0

    if strict:
        if findings.errors:
            print(
                f"\nFAILED in --strict mode "
                f"({len(findings.errors)} error(s), {len(findings.warnings)} warning(s)).",
                file=sys.stderr,
            )
            return 1
        print(
            f"\nPASS in --strict mode "
            f"(0 error(s), {len(findings.warnings)} informational warning(s)).",
            file=sys.stderr,
        )
        return 0

    print(
        f"\n(warning-only mode — backfill in progress, "
        f"{len(findings.errors)} error(s) treated as warnings, "
        f"{len(findings.warnings)} warning(s)).",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on any violation. Default: warning-only.",
    )
    args = parser.parse_args()
    return run(strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
