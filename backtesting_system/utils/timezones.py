from __future__ import annotations

from datetime import time

from backtesting_system.core.clock import SessionWindow


ASIA = SessionWindow("Asia", time(0, 0), time(9, 0))
LONDON = SessionWindow("London", time(8, 0), time(17, 0))
NY = SessionWindow("NY", time(13, 0), time(22, 0))
