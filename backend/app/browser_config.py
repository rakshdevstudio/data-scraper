import platform
import sys
from typing import Dict, List, Any


class BrowserConfig:
    """Platform-specific browser configuration for Playwright."""

    @staticmethod
    def get_os_info() -> Dict[str, str]:
        """Get detailed OS information."""
        return {
            "system": platform.system(),  # Darwin, Linux, Windows
            "machine": platform.machine(),  # arm64, x86_64
            "platform": platform.platform(),
            "python_version": sys.version,
        }

    @staticmethod
    def get_chromium_args() -> List[str]:
        """Get platform-specific Chromium launch arguments with anti-detection."""
        os_info = BrowserConfig.get_os_info()
        system = os_info["system"]

        # Base stealth args (all platforms)
        base_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--disable-web-security",
            "--disable-dev-shm-usage",
        ]

        if system == "Darwin":  # macOS
            return base_args
        elif system == "Linux":
            # Linux/Docker needs sandbox flags
            return base_args + [
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        else:  # Windows
            return base_args

    @staticmethod
    def get_firefox_args() -> List[str]:
        """Get Firefox launch arguments (fallback browser)."""
        return [
            "-private",
        ]

    @staticmethod
    def get_stealth_context_options() -> Dict[str, Any]:
        """Get stealth context options with randomized viewport and user agent."""
        import random

        # Randomize viewport to avoid fingerprinting
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
        ]

        # Realistic user agents
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

        return {
            "viewport": random.choice(viewports),
            "user_agent": random.choice(user_agents),
        }

    @staticmethod
    def log_browser_info(logger_func, browser_type: str = "chromium"):
        """Log browser and OS telemetry."""
        os_info = BrowserConfig.get_os_info()
        logger_func(f"=== Browser Telemetry ===")
        logger_func(f"Browser Type: {browser_type}")
        logger_func(f"OS: {os_info['system']}")
        logger_func(f"Architecture: {os_info['machine']}")
        logger_func(f"Platform: {os_info['platform']}")
        logger_func(f"========================")
