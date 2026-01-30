import random
import logging
import threading
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class ProxyManager:
    """
    Manages proxy rotation, ban detection, and request configuration.
    Supports HTTP/SOCKS proxies.
    """

    def __init__(self, proxies: List[str] = None):
        """
        Initialize proxy manager.

        Args:
            proxies: List of proxy strings (e.g., "http://user:pass@host:port")
        """
        self.proxies = proxies or []
        self.banned_proxies = set()
        self.current_index = 0
        self.lock = threading.Lock()

        if self.proxies:
            logger.info(f"ProxyManager initialized with {len(self.proxies)} proxies.")
        else:
            logger.info("ProxyManager initialized with NO proxies (Direct connection).")

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get next available proxy in rotation.

        Returns:
            Dict compatible with Playwright (server, username, password) or None
        """
        with self.lock:
            if not self.proxies:
                return None

            # Simple Round Robin for now
            # In future: Check health status, filter banned
            attempts = 0
            while attempts < len(self.proxies):
                proxy_str = self.proxies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.proxies)

                if proxy_str in self.banned_proxies:
                    attempts += 1
                    continue

                return self._parse_proxy(proxy_str)

            # If all banned, reset bans and try again (fail-open strategy)
            logger.warning("All proxies banned! Resetting ban list.")
            self.banned_proxies.clear()
            return self._parse_proxy(self.proxies[0])

    def mark_banned(self, proxy_server: str):
        """Mark a proxy as banned/throttled."""
        if not proxy_server:
            return

        # Find original proxy string causing this
        # This is a simplification; in production we'd map server -> config
        logger.warning(f"🚫 Marking proxy as BANNED: {proxy_server}")
        # For now, we won't permanently ban without a robust mapping mechanism
        # But we would add to self.banned_proxies here

    def _parse_proxy(self, proxy_str: str) -> Dict:
        """Parse proxy string into Playwright config."""
        try:
            # Format: protocol://user:pass@host:port
            # Playwright expects: { "server": "...", "username": "...", "password": "..." }

            import urllib.parse

            parsed = urllib.parse.urlparse(proxy_str)

            config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}

            if parsed.username:
                config["username"] = parsed.username
                config["password"] = parsed.password

            return config
        except Exception as e:
            logger.error(f"Failed to parse proxy '{proxy_str}': {e}")
            return None
