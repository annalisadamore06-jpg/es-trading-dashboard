"""ES Trading Dashboard - Real-time options trading dashboard."""

__version__ = "0.1.0"
__author__ = "Your Name"

from es_trading_dashboard.core.config import Settings
from es_trading_dashboard.core.ib_client import IBClient

__all__ = ["Settings", "IBClient", "__version__"]
