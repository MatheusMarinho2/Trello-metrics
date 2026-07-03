from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MonthPeriod:
    label: str
    timezone: str
    start: datetime
    end: datetime

    def contains(self, moment: datetime | None) -> bool:
        if moment is None:
            return False
        local = moment.astimezone(self.start.tzinfo)
        return self.start <= local < self.end


def parse_month(month: str, timezone_name: str = "America/Sao_Paulo") -> MonthPeriod:
    year_str, month_str = month.split("-", 1)
    year = int(year_str)
    month_num = int(month_str)
    tz = ZoneInfo(timezone_name)
    start = datetime(year, month_num, 1, tzinfo=tz)
    if month_num == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month_num + 1, 1, tzinfo=tz)
    return MonthPeriod(label=month, timezone=timezone_name, start=start, end=end)


def month_range(
    anchor_month: str,
    history_months: int,
    timezone_name: str = "America/Sao_Paulo",
) -> list[MonthPeriod]:
    anchor = parse_month(anchor_month, timezone_name)
    year = anchor.start.year
    month_num = anchor.start.month
    periods: list[MonthPeriod] = []
    for _ in range(history_months):
        label = f"{year:04d}-{month_num:02d}"
        periods.append(parse_month(label, timezone_name))
        month_num -= 1
        if month_num == 0:
            month_num = 12
            year -= 1
    periods.reverse()
    return periods


def to_utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc)
