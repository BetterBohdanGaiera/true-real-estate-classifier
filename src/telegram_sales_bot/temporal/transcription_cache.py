"""
JSON-based cache for media transcription/analysis results.

Bridges real-time media analysis with the chat history fetcher: when a new
message gets analyzed (voice transcription, photo description, etc.), the
result is cached here so that subsequent chat history fetches can substitute
rich text instead of placeholders like "[Voice message]".

Cache file is stored alongside other config JSON files in CONFIG_DIR.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from telegram_sales_bot.core.models import TranscriptionCacheEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config directory resolution (same pattern as core/daemon.py)
# ---------------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).parent.parent  # src/telegram_sales_bot/

if Path("/app/config").exists():
    CONFIG_DIR = Path("/app/config")
else:
    PROJECT_ROOT = PACKAGE_DIR.parent.parent  # project root
    CONFIG_DIR = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config"


class TranscriptionCache:
    """JSON-based cache for media transcription/analysis results.

    Stores results keyed by ``(chat_id, message_id)`` so the chat history
    fetcher can retrieve rich text descriptions for media messages without
    re-analyzing them.

    The cache is persisted as a single JSON file and loaded into memory on
    initialization. Every :meth:`store` call triggers an automatic save to
    disk so that the cache survives process restarts.

    Attributes:
        _cache_file: Path to the JSON file backing the cache.
        _cache: In-memory dict mapping ``"{chat_id}:{message_id}"`` keys
            to :class:`TranscriptionCacheEntry` instances.
    """

    def __init__(self, cache_file: Optional[Path] = None) -> None:
        """Initialize cache, loading existing entries from disk if the file exists.

        Args:
            cache_file: Optional explicit path for the JSON cache file.
                When ``None`` (default), the cache is stored at
                ``CONFIG_DIR / "transcription_cache.json"``.
        """
        if cache_file is None:
            cache_file = CONFIG_DIR / "transcription_cache.json"
        self._cache_file: Path = cache_file
        self._cache: dict[str, TranscriptionCacheEntry] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(chat_id: int | str, message_id: int) -> str:
        """Create a cache key from *chat_id* and *message_id*.

        Args:
            chat_id: Telegram chat/user ID (numeric or string).
            message_id: Telegram message ID within that chat.

        Returns:
            A string key in the format ``"{chat_id}:{message_id}"``.
        """
        return f"{chat_id}:{message_id}"

    def _load(self) -> None:
        """Load cache entries from the JSON file on disk.

        If the file does not exist or is malformed the cache starts empty.
        """
        if not self._cache_file.exists():
            logger.debug("No transcription cache file at %s - starting empty", self._cache_file)
            return

        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, entry_data in data.items():
                self._cache[key] = TranscriptionCacheEntry(**entry_data)
            logger.debug(
                "Loaded %d transcription cache entries from %s",
                len(self._cache),
                self._cache_file,
            )
        except Exception as e:
            logger.warning("Failed to load transcription cache from %s: %s", self._cache_file, e)
            self._cache = {}

    def _save(self) -> None:
        """Persist the in-memory cache to the JSON file on disk."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                key: entry.model_dump(mode="json")
                for key, entry in self._cache.items()
            }
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save transcription cache to %s: %s", self._cache_file, e)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(
        self,
        chat_id: int | str,
        message_id: int,
        media_type: str,
        transcription: str,
    ) -> None:
        """Store a transcription/analysis result and persist to disk.

        Args:
            chat_id: Telegram chat/user ID.
            message_id: Telegram message ID.
            media_type: Media type string (e.g. ``"voice"``, ``"photo"``).
            transcription: The transcribed text or media description.
        """
        key = self._make_key(chat_id, message_id)
        self._cache[key] = TranscriptionCacheEntry(
            message_id=message_id,
            telegram_chat_id=chat_id,
            media_type=media_type,
            transcription=transcription,
        )
        self._save()
        logger.debug(
            "Cached %s transcription for message %d in chat %s",
            media_type,
            message_id,
            chat_id,
        )

    def get(self, chat_id: int | str, message_id: int) -> Optional[str]:
        """Get cached transcription text, or ``None`` if not cached.

        Args:
            chat_id: Telegram chat/user ID.
            message_id: Telegram message ID.

        Returns:
            The transcription string if present, otherwise ``None``.
        """
        key = self._make_key(chat_id, message_id)
        entry = self._cache.get(key)
        return entry.transcription if entry else None

    def has(self, chat_id: int | str, message_id: int) -> bool:
        """Check whether a transcription is cached for the given message.

        Args:
            chat_id: Telegram chat/user ID.
            message_id: Telegram message ID.

        Returns:
            ``True`` if a cache entry exists, ``False`` otherwise.
        """
        return self._make_key(chat_id, message_id) in self._cache

    def get_for_chat(self, chat_id: int | str) -> dict[int, str]:
        """Get all cached transcriptions for a specific chat.

        Args:
            chat_id: Telegram chat/user ID.

        Returns:
            A dict mapping ``message_id`` to its transcription string for
            every cached entry belonging to *chat_id*.
        """
        prefix = f"{chat_id}:"
        result: dict[int, str] = {}
        for key, entry in self._cache.items():
            if key.startswith(prefix):
                result[entry.message_id] = entry.transcription
        return result

    def clear(self) -> None:
        """Remove all entries from the cache and persist the empty state."""
        self._cache.clear()
        self._save()

    @property
    def size(self) -> int:
        """Number of entries currently in the cache."""
        return len(self._cache)
