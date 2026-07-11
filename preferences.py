"""Load and fingerprint the user's news preference profile."""

from __future__ import annotations

import hashlib
from pathlib import Path

from config import NEWS_PREFERENCES_PATH, USER_NEWS_PREFERENCES

MAX_PREFERENCES_CHARS = 12_000


class PreferencesError(RuntimeError):
    """Raised when the news preference profile cannot be used safely."""


def load_news_preferences(
    path: str | Path = NEWS_PREFERENCES_PATH,
    inline_preferences: str = USER_NEWS_PREFERENCES,
) -> str:
    """Return inline preferences or load the UTF-8 profile from disk."""
    text = inline_preferences.strip()
    if not text:
        profile_path = Path(path)
        if not profile_path.exists():
            raise PreferencesError(f"News preferences file does not exist: {profile_path}")
        try:
            text = profile_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise PreferencesError(f"Cannot read news preferences: {profile_path}") from exc

    if not text:
        raise PreferencesError("News preferences must not be empty.")
    if len(text) > MAX_PREFERENCES_CHARS:
        raise PreferencesError(
            f"News preferences exceed the {MAX_PREFERENCES_CHARS}-character limit."
        )
    return text


def preferences_fingerprint(preferences: str) -> str:
    """Build a stable key so changed preferences trigger fresh classification."""
    normalized = "\n".join(line.rstrip() for line in preferences.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
