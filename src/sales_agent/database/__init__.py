"""
Database module for PostgreSQL operations.

Provides database initialization and migration management.
"""

from .init import init_database

__all__ = ["init_database"]
