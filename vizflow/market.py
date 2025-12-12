"""Market session definitions and time handling."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Session:
    """A trading session.

    Attributes:
        start: Start time as "HH:MM"
        end: End time as "HH:MM"
    """

    start: str  # "HH:MM"
    end: str  # "HH:MM"


@dataclass
class Market:
    """Market definition with trading sessions.

    Attributes:
        name: Market identifier (e.g. "CN", "crypto")
        sessions: List of trading sessions
    """

    name: str
    sessions: list[Session]

    def elapsed_seconds(self, time: datetime) -> int:
        """Convert wall-clock time to continuous trading seconds.

        For CN market:
          Morning:   elapsed = (hour - 9) * 3600 + (minute - 30) * 60 + second
          Afternoon: elapsed = 7200 + (hour - 13) * 3600 + minute * 60 + second

        Examples (CN):
          09:30:00 → 0
          11:29:59 → 7199
          13:00:00 → 7200
          15:00:00 → 14400

        Args:
            time: datetime object

        Returns:
            Elapsed trading seconds from market open
        """
        h, m, s = time.hour, time.minute, time.second

        if self.name == "CN":
            # Morning session: 09:30 - 11:30
            if 9 <= h < 11 or (h == 11 and m < 30) or (h == 9 and m >= 30):
                if h == 9 and m >= 30:
                    return (m - 30) * 60 + s
                elif h == 10:
                    return 30 * 60 + m * 60 + s
                elif h == 11 and m < 30:
                    return 90 * 60 + m * 60 + s
            # Afternoon session: 13:00 - 15:00
            elif 13 <= h < 15 or (h == 15 and m == 0 and s == 0):
                return 7200 + (h - 13) * 3600 + m * 60 + s

        elif self.name == "crypto":
            # 24/7: simple seconds since midnight
            return h * 3600 + m * 60 + s

        elif self.name == "KR":
            # Korea: 09:00 - 15:30
            if 9 <= h < 15 or (h == 15 and m <= 30):
                return (h - 9) * 3600 + m * 60 + s

        raise ValueError(f"Time {time} is outside trading hours for market {self.name}")


# === Presets ===

CN = Market(
    name="CN",
    sessions=[
        Session(start="09:30", end="11:30"),  # Morning (2 hours)
        Session(start="13:00", end="15:00"),  # Afternoon (2 hours)
    ],
)
# Total: 4 hours = 14,400 seconds

CRYPTO = Market(
    name="crypto",
    sessions=[
        Session(start="00:00", end="24:00"),
    ],
)
