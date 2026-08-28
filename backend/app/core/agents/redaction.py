"""PHI redaction boundary for the agentic layer.

No patient identifier leaves the server in cleartext toward a cloud LLM.
A per-session :class:`SymbolTable` maps real values to stable opaque
tokens (``NAME_a1b2c3``, ``PHONE_…``, ``PATIENT_…``); outgoing payloads
are tokenized, assistant output and tool-call arguments are rehydrated.

Tokens are **deterministic** (a short hash of the real value), so the
same value always maps to the same token. That lets a resumed turn
rebuild an equivalent table by re-redacting the loaded history — tokens
the model emitted in an earlier request still restore.

v1 scope (see ``docs/technical/copilot-agentic-architecture.md`` §2.3):

* structured tool inputs/results — key-based redaction over the JSON;
* seeded context entities — pre-loaded at session start;
* user free text — substring replacement of entities *already* in the
  table. **Known gap:** a name the user types for an entity not yet
  loaded cannot be caught without NER. Tools that return free prose set
  ``Tool.exposes_free_text=True`` and are excluded from the cloud path
  by the orchestrator while redaction is enabled.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Final

from app.core.llm.base import (
    ContentBlock,
    ProviderMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from app.core.privacy import PrivacyPolicy, pii_columns

logger = logging.getLogger(__name__)

# Keys a *tool payload* uses that no column carries: names composed by a
# handler (``full_name`` from first + last), and the aliases a JSON
# response may pick for a column (``mobile`` for ``phone``). Everything
# else comes from the schema itself — see ``pii_columns()``.
_SYNTHETIC_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "full_name": "NAME",
        "patient_name": "NAME",
        "name": "NAME",
        "mobile": "PHONE",
        "telephone": "PHONE",
        "phone_number": "PHONE",
        "email_address": "EMAIL",
        # ``accounting_export`` emits ``nif`` as a CSV row key and
        # ``verifactu`` carries it as a schema field; neither is a column.
        "nif": "NATID",
    }
)

# The *document* names of a jurisdiction, for payloads that name a field
# after the document itself rather than after the column that stores it.
# Which ones apply is ``PrivacyPolicy.jurisdictions`` on the tenant
# (ADR 0023), not a property of the code.
_ID_KEYS_BY_JURISDICTION: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "ES": frozenset({"dni", "nif", "nie", "cif"}),
        "MX": frozenset({"ine", "curp", "rfc"}),
    }
)

ALL_JURISDICTIONS: Final = frozenset(_ID_KEYS_BY_JURISDICTION)
"""Every jurisdiction this module knows document names for.

The default when no policy is supplied. Redacting a key that never
appears in a payload costs nothing, so the safe default is *all* of them
— a caller that forgets to pass its jurisdictions over-redacts instead of
leaking a document type it did not think to name.
"""


@lru_cache(maxsize=32)
def _jurisdiction_keys(jurisdictions: frozenset[str]) -> Mapping[str, str]:
    """Document-name keys that apply under ``jurisdictions``.

    Cached because a tenant's set is stable. A consequence: the
    unknown-jurisdiction warning is emitted once per distinct set, not
    once per session.
    """
    keys: dict[str, str] = {}
    for code in sorted(jurisdictions):
        known = _ID_KEYS_BY_JURISDICTION.get(code)
        if known is None:
            # Not fatal: the schema's own classified columns still
            # tokenize. But a field named after a local document (say a
            # Brazilian ``cpf``) would pass through in cleartext.
            logger.warning(
                "No PII key set for jurisdiction %r; only classified columns are redacted",
                code,
            )
            continue
        for key in known:
            keys[key] = "NATID"
    return MappingProxyType(keys)


def _kind_for_key(jurisdictions: frozenset[str]) -> Mapping[str, str]:
    """Build the key -> token-kind map for one redactor.

    Three sources, most authoritative last: the tenant's jurisdiction
    document names, the payload-only aliases above, and the columns the
    schema classifies with ``pii()``. The schema wins because it is the
    only one that cannot drift from what is actually stored.

    Not cached: ``pii_columns()`` reflects the modules mounted right now,
    and freezing that would make an install invisible to redaction.
    """
    mapping: dict[str, str] = {}
    mapping.update(_jurisdiction_keys(jurisdictions))
    mapping.update(_SYNTHETIC_KEYS)
    for column, kind in pii_columns().items():
        mapping[column] = kind.value
    return MappingProxyType(mapping)


# UUID-valued reference keys -> kind
_ID_KIND = {
    "id": "REF",
    "patient_id": "PATIENT",
    "appointment_id": "APPT",
}


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _token_for(real: str, kind: str) -> str:
    digest = hashlib.sha1(real.encode("utf-8")).hexdigest()[:6]  # noqa: S324 - non-crypto use
    return f"{kind}_{digest}"


@dataclass
class SymbolTable:
    """Bidirectional, deterministic map between real values and tokens."""

    _to_token: dict[str, str] = field(default_factory=dict)
    _to_real: dict[str, str] = field(default_factory=dict)

    def tokenize(self, real: str, kind: str) -> str:
        token = self._to_token.get(real)
        if token is None:
            token = _token_for(real, kind)
            self._to_token[real] = token
            self._to_real[token] = real
        return token

    def restore_text(self, text: str) -> str:
        if not text or not self._to_real:
            return text
        # Replace longest tokens first to avoid prefix collisions.
        for token in sorted(self._to_real, key=len, reverse=True):
            if token in text:
                text = text.replace(token, self._to_real[token])
        return text

    def replace_known(self, text: str) -> str:
        """Tokenize occurrences of already-known real values in free text."""
        if not text or not self._to_token:
            return text
        for real in sorted(self._to_token, key=len, reverse=True):
            if real and real in text:
                text = text.replace(real, self._to_token[real])
        return text


class Redactor:
    """Applies the redaction boundary over neutral messages and JSON.

    When ``enabled`` is ``False`` every method is the identity — useful
    for tests and the (deferred) self-hosted path where data never
    leaves the clinic.

    ``jurisdictions`` selects which government-document names count as
    identifiers. It comes from the tenant's
    :class:`~app.core.privacy.PrivacyPolicy` — build through
    :meth:`for_policy` rather than passing the set by hand. Omitting it
    falls back to every jurisdiction this module knows, which
    over-redacts rather than under-redacts.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        jurisdictions: frozenset[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self.jurisdictions = ALL_JURISDICTIONS if jurisdictions is None else jurisdictions
        self._kind_for_key = _kind_for_key(self.jurisdictions)
        self.table = SymbolTable()

    @classmethod
    def for_policy(cls, policy: PrivacyPolicy, *, enabled: bool = True) -> Redactor:
        """Build a redactor bound to a tenant's declared jurisdictions."""
        return cls(enabled=enabled, jurisdictions=policy.jurisdictions)

    # --- seeding --------------------------------------------------------

    def seed(self, context: dict[str, Any] | None) -> None:
        """Pre-load known entities from a conversation's context blob."""
        if not self.enabled or not context:
            return
        self._redact_obj(dict(context))  # populates the table as a side-effect

    # --- outgoing (server -> provider) ---------------------------------

    def redact_outgoing(self, messages: list[ProviderMessage]) -> list[ProviderMessage]:
        """Return a tokenized copy of ``messages``; never mutates input."""
        if not self.enabled:
            return messages
        return [self._redact_message(m) for m in messages]

    def _redact_message(self, msg: ProviderMessage) -> ProviderMessage:
        new_content: list[ContentBlock] = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                new_content.append(TextBlock(self.table.replace_known(block.text)))
            elif isinstance(block, ToolUseBlock):
                new_content.append(
                    ToolUseBlock(block.id, block.name, self._redact_obj(block.input))
                )
            elif isinstance(block, ToolResultBlock):
                new_content.append(
                    ToolResultBlock(
                        block.tool_call_id,
                        self._redact_obj(block.content),
                        block.is_error,
                    )
                )
        return ProviderMessage(role=msg.role, content=new_content)

    def redact_result(self, content: Any) -> Any:
        """Tokenize a single tool result before it is fed back / streamed."""
        if not self.enabled:
            return content
        return self._redact_obj(content)

    def _redact_obj(self, obj: Any, key: str | None = None) -> Any:
        if isinstance(obj, dict):
            return {k: self._redact_obj(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._redact_obj(v, key) for v in obj]
        if isinstance(obj, str):
            return self._redact_scalar(key, obj)
        return obj

    def _redact_scalar(self, key: str | None, value: str) -> str:
        if not value:
            return value
        lkey = (key or "").lower()
        kind = self._kind_for_key.get(lkey)
        if kind is not None:
            return self.table.tokenize(value, kind)
        if lkey in _ID_KIND and _UUID_RE.match(value):
            return self.table.tokenize(value, _ID_KIND[lkey])
        return value

    # --- incoming (provider -> server / display) -----------------------

    def rehydrate(self, text: str) -> str:
        """Restore tokens to real values for display."""
        if not self.enabled:
            return text
        return self.table.restore_text(text)

    def resolve_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Restore tokens inside model-produced tool arguments before exec."""
        if not self.enabled:
            return args
        return self._restore_obj(args)

    def _restore_obj(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._restore_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._restore_obj(v) for v in obj]
        if isinstance(obj, str):
            return self.table.restore_text(obj)
        return obj
