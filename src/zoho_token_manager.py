"""
Zoho Token Manager - Centralized OAuth token management.

This singleton manages OAuth tokens for all Zoho API clients:
- Thread-safe token cache (RLock)
- File persistence (.token_cache.json)
- Rate limiting (minimum 2s between refreshes per credential set)
- Exponential backoff on rate limit errors
- Shared across all ZohoAPIClient instances

Usage:
    from src.zoho_token_manager import get_token_manager

    token_manager = get_token_manager()
    access_token = token_manager.get_token(
        client_id="...",
        client_secret="...",
        refresh_token="...",
        accounts_url="https://accounts.zoho.eu"
    )
"""
import json
import logging
import threading
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

import requests

logger = logging.getLogger(__name__)


class ZohoRateLimitError(Exception):
    """Raised when Zoho API returns a rate limit error."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class TokenManager:
    """
    Singleton manager for Zoho OAuth tokens.

    Features:
    - Caches tokens by credential set (client_id + refresh_token)
    - Thread-safe with RLock
    - Persists tokens to disk for cross-session caching
    - Rate-limits refresh calls to prevent API abuse
    """

    _instance: Optional["TokenManager"] = None
    _lock = threading.RLock()

    # Cache file location (relative to project root)
    CACHE_FILE = Path(__file__).parent.parent / ".token_cache.json"

    # Minimum seconds between token refreshes for the same credential set
    MIN_REFRESH_INTERVAL = 2.0

    # Buffer before token expiration (refresh 5 minutes early)
    EXPIRATION_BUFFER_SECONDS = 300

    # Rate limit handling
    RATE_LIMIT_WAIT_SECONDS = 60  # Wait time when rate limited
    MAX_REFRESH_ATTEMPTS = 3  # Max retry attempts for token refresh
    BACKOFF_MULTIPLIER = 2  # Exponential backoff multiplier

    def __new__(cls) -> "TokenManager":
        """Ensure only one instance exists (singleton pattern)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize the token manager (only runs once due to singleton)."""
        if self._initialized:
            return

        self._tokens: Dict[str, Dict[str, Any]] = {}  # {key: {token, expires_at}}
        self._last_refresh_time: Dict[str, float] = {}  # {key: timestamp}
        self._refresh_count = 0  # Monitoring: total refreshes
        self._cache_hits = 0  # Monitoring: cache hits

        # Load persisted tokens from disk
        self._load_cache()

        self._initialized = True
        logger.info("TokenManager initialized (singleton)")

    def _get_cache_key(
        self,
        client_id: str,
        refresh_token: str
    ) -> str:
        """
        Generate a cache key for a credential set.

        Uses first 8 chars of hash to identify the credential set
        without storing sensitive data in logs.
        """
        combined = f"{client_id}:{refresh_token}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def get_token(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        accounts_url: str
    ) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            refresh_token: Zoho OAuth refresh token
            accounts_url: Zoho accounts URL (e.g., https://accounts.zoho.eu)

        Returns:
            Valid access token string

        Raises:
            Exception if token refresh fails after all retries
        """
        cache_key = self._get_cache_key(client_id, refresh_token)

        with self._lock:
            # Check if we have a valid cached token
            if cache_key in self._tokens:
                token_data = self._tokens[cache_key]
                expires_at = token_data.get("expires_at")

                if expires_at and datetime.now() < expires_at:
                    self._cache_hits += 1
                    logger.debug(f"Token cache hit for {cache_key[:8]}... (hits: {self._cache_hits})")
                    return token_data["access_token"]

            # Need to refresh - apply rate limiting
            self._apply_rate_limit(cache_key)

            # Refresh the token with retry and exponential backoff
            token_data = self._refresh_token_with_retry(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                accounts_url=accounts_url,
                cache_key=cache_key
            )

            # Cache the new token
            self._tokens[cache_key] = token_data
            self._last_refresh_time[cache_key] = time.time()
            self._refresh_count += 1

            # Persist to disk
            self._save_cache()

            logger.info(f"Token refresh #{self._refresh_count} for {cache_key[:8]}...")

            return token_data["access_token"]

    def _refresh_token_with_retry(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        accounts_url: str,
        cache_key: str
    ) -> Dict[str, Any]:
        """
        Refresh token with custom retry logic and exponential backoff.

        Handles rate limit errors specially by waiting longer.
        """
        last_exception = None
        wait_time = 2  # Initial wait time in seconds

        for attempt in range(1, self.MAX_REFRESH_ATTEMPTS + 1):
            try:
                return self._refresh_token(
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token,
                    accounts_url=accounts_url
                )

            except ZohoRateLimitError as e:
                last_exception = e
                wait_time = e.retry_after
                logger.warning(
                    f"Rate limited on attempt {attempt}/{self.MAX_REFRESH_ATTEMPTS}. "
                    f"Waiting {wait_time}s before retry..."
                )
                time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.MAX_REFRESH_ATTEMPTS:
                    logger.warning(
                        f"Token refresh failed on attempt {attempt}/{self.MAX_REFRESH_ATTEMPTS}: {e}. "
                        f"Waiting {wait_time}s before retry..."
                    )
                    time.sleep(wait_time)
                    wait_time *= self.BACKOFF_MULTIPLIER  # Exponential backoff

        # All retries exhausted
        logger.error(f"Token refresh failed after {self.MAX_REFRESH_ATTEMPTS} attempts")
        raise last_exception

    def _apply_rate_limit(self, cache_key: str) -> None:
        """
        Apply rate limiting to prevent too frequent refresh calls.

        Sleeps if the last refresh for this credential set was too recent.
        """
        if cache_key in self._last_refresh_time:
            elapsed = time.time() - self._last_refresh_time[cache_key]
            if elapsed < self.MIN_REFRESH_INTERVAL:
                sleep_time = self.MIN_REFRESH_INTERVAL - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {cache_key[:8]}...")
                time.sleep(sleep_time)

    def _refresh_token(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        accounts_url: str
    ) -> Dict[str, Any]:
        """
        Call Zoho OAuth API to refresh the access token.

        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            refresh_token: Zoho OAuth refresh token
            accounts_url: Zoho accounts URL

        Returns:
            Dict with access_token and expires_at

        Raises:
            ZohoRateLimitError: If rate limited by Zoho
            requests.exceptions.RequestException: For other HTTP errors
        """
        url = f"{accounts_url}/oauth/v2/token"
        params = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token"
        }

        logger.info(f"Refreshing Zoho access token via {accounts_url}")

        try:
            # Explicitly disable proxy for Zoho API calls
            response = requests.post(
                url,
                params=params,
                proxies={"http": None, "https": None},
                timeout=30
            )

            # Check for rate limiting BEFORE raise_for_status
            if response.status_code in (429, 400):
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error_description", "")
                    error_code = error_data.get("error", "")

                    # Detect rate limiting errors
                    if "too many requests" in error_msg.lower() or error_code == "Access Denied":
                        retry_after = int(response.headers.get("Retry-After", self.RATE_LIMIT_WAIT_SECONDS))
                        logger.warning(f"Zoho OAuth rate limited: {error_msg}")
                        raise ZohoRateLimitError(
                            f"Rate limited: {error_msg}",
                            retry_after=retry_after
                        )
                except (json.JSONDecodeError, ValueError):
                    pass  # Not a JSON response, continue with normal error handling

            response.raise_for_status()
            data = response.json()

            access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)

            # Calculate expiration time with buffer
            expires_at = datetime.now() + timedelta(
                seconds=expires_in - self.EXPIRATION_BUFFER_SECONDS
            )

            logger.info("Access token refreshed successfully")

            return {
                "access_token": access_token,
                "expires_at": expires_at
            }

        except ZohoRateLimitError:
            # Re-raise rate limit errors (don't wrap them)
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    def _load_cache(self) -> None:
        """Load persisted tokens from disk cache file."""
        if not self.CACHE_FILE.exists():
            logger.debug("No token cache file found")
            return

        try:
            with open(self.CACHE_FILE, "r") as f:
                cache_data = json.load(f)

            # Restore tokens, converting expires_at back to datetime
            for key, data in cache_data.items():
                if "expires_at" in data and data["expires_at"]:
                    data["expires_at"] = datetime.fromisoformat(data["expires_at"])
                self._tokens[key] = data

            logger.info(f"Loaded {len(self._tokens)} token(s) from cache")

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not load token cache: {e}")
            self._tokens = {}

    def _save_cache(self) -> None:
        """Persist tokens to disk cache file."""
        try:
            # Convert datetime to ISO format for JSON serialization
            cache_data = {}
            for key, data in self._tokens.items():
                cache_data[key] = {
                    "access_token": data["access_token"],
                    "expires_at": data["expires_at"].isoformat() if data.get("expires_at") else None
                }

            with open(self.CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(f"Saved {len(cache_data)} token(s) to cache")

        except Exception as e:
            logger.warning(f"Could not save token cache: {e}")

    def invalidate(self, client_id: str, refresh_token: str) -> None:
        """
        Invalidate a cached token, forcing refresh on next get_token call.

        Args:
            client_id: Zoho OAuth client ID
            refresh_token: Zoho OAuth refresh token
        """
        cache_key = self._get_cache_key(client_id, refresh_token)

        with self._lock:
            if cache_key in self._tokens:
                del self._tokens[cache_key]
                self._save_cache()
                logger.info(f"Invalidated token for {cache_key[:8]}...")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get token manager statistics for monitoring.

        Returns:
            Dict with refresh_count, cache_hits, cached_tokens
        """
        with self._lock:
            return {
                "refresh_count": self._refresh_count,
                "cache_hits": self._cache_hits,
                "cached_tokens": len(self._tokens),
                "cache_file": str(self.CACHE_FILE)
            }

    def clear_all(self) -> None:
        """Clear all cached tokens (useful for testing)."""
        with self._lock:
            self._tokens = {}
            self._last_refresh_time = {}
            self._refresh_count = 0
            self._cache_hits = 0

            # Remove cache file
            if self.CACHE_FILE.exists():
                self.CACHE_FILE.unlink()

            logger.info("Cleared all cached tokens")


def get_token_manager() -> TokenManager:
    """
    Get the singleton TokenManager instance.

    This is the recommended way to access the TokenManager.

    Returns:
        TokenManager singleton instance
    """
    return TokenManager()


# Module-level singleton for convenient import
_token_manager = get_token_manager()
