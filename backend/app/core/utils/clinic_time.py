"""The clinic's calendar, which is the only one its books are kept on.

A clinic records some things as **days** — the day money was taken, the day
a report covers — and others as **instants**: a refund was issued at a
moment, a treatment was performed at a moment. Wherever the two meet, the
day boundary has to be the clinic's, never UTC's and never the reader's.

Using UTC's instead shifts every boundary by the clinic's offset: payments
read a day early west of Greenwich, and a report "1-30 September" runs from
1 Sept 02:00 to 1 Oct 02:00 in Madrid, quietly swapping each end's small
hours. That was a real bug in `payments`, fixed there and now shared rather
than re-derived — `cashbox` needs exactly the same boundaries to decide
which refunds belong to the day it is counting, and a second copy of this
reasoning is a second chance to get it wrong.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


def clinic_zone(tz_name: str) -> ZoneInfo:
    """The clinic's zone, falling back to UTC on an unusable id.

    Degrades rather than raising: a wrong day boundary is a nuisance, a
    ledger or a report that will not load is not.
    """
    try:
        return ZoneInfo(tz_name) if tz_name else UTC
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unusable clinic timezone %r; falling back to UTC", tz_name)
        return UTC


def clinic_midnight(day: date, tz_name: str) -> datetime:
    """A calendar day as the instant it began in the clinic's zone.

    ``payments.payment_date`` is a DATE: the clinic took the money on a
    day, not at a moment. To sit on a timeline beside real instants it has
    to become one, and the start of that day where the clinic keeps its
    books is the only defensible choice.
    """
    return datetime.combine(day, datetime.min.time(), tzinfo=clinic_zone(tz_name)).astimezone(UTC)


def clinic_day_window(date_from: date, date_to: date, tz_name: str) -> tuple[datetime, datetime]:
    """Half-open ``[start, end)`` in UTC covering those clinic days, inclusive.

    Half-open on purpose: the old form compared against ``datetime.max``,
    which is 23:59:59.999999 and drops anything landing in the last
    microsecond of the day. The next day's midnight has no such gap.
    """
    return (
        clinic_midnight(date_from, tz_name),
        clinic_midnight(date_to + timedelta(days=1), tz_name),
    )


def clinic_date(moment: datetime, tz_name: str) -> date:
    """Which day an instant fell on, in the clinic's calendar."""
    return moment.astimezone(clinic_zone(tz_name)).date()
