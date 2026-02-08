"""Sales rep registration subsystem."""

from telegram_sales_bot.registry.rep_manager import SalesRepManager
from telegram_sales_bot.registry.prospect_db import TestProspectManager

__all__ = [
    "SalesRepManager",
    "TestProspectManager",
]
