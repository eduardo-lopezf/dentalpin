"""A test cannot leave the event bus changed for the tests after it.

The two tests run in file order: the first drops a real subscriber the way
a careless cleanup used to, the second checks it is back. Without the
autouse restore in ``conftest.py`` the second fails — which is how the
reopen tests lost ``payments``' session charges in the full suite.
"""

from app.core.events import EventType, event_bus
from app.modules.payments.events import on_session_completed


def test_a_test_that_drops_subscribers() -> None:
    event_bus._handlers.pop(EventType.TREATMENT_PLAN_ITEM_SESSION_COMPLETED, None)  # noqa: SLF001
    assert on_session_completed not in event_bus._handlers.get(  # noqa: SLF001
        EventType.TREATMENT_PLAN_ITEM_SESSION_COMPLETED, []
    )


def test_the_next_test_still_has_them() -> None:
    assert on_session_completed in event_bus._handlers.get(  # noqa: SLF001
        EventType.TREATMENT_PLAN_ITEM_SESSION_COMPLETED, []
    )
