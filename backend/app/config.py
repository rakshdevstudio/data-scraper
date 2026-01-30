import json
import os
import threading

# Determine project root
# If running as module (python -m backend.app.main), cwd might be root
# If running from inside backend, we need to adjust.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# Potential paths for control.json
CANDIDATE_PATHS = [
    os.path.join(PROJECT_ROOT, "backend", "control.json"),
    os.path.join("backend", "control.json"),
    "control.json",
]

CONFIG_FILE = "control.json"  # Default fallback
for path in CANDIDATE_PATHS:
    if os.path.exists(path):
        CONFIG_FILE = path
        break
    # If not exists, use the first preferred one for creation
    CONFIG_FILE = CANDIDATE_PATHS[0]

LOCK = threading.Lock()


def get_default_config():
    """Get default configuration with production-grade timeout and throttling settings."""
    return {
        "headless": False,  # Headful mode for anti-detection
        "slow_mo": 50,  # Human-like interaction speed (ms)
        "max_keyword_timeout": 180,  # 3 minutes max per keyword
        "max_business_timeout": 20,  # 20 seconds max per business
        "browser_restart_interval": 10,  # Restart browser every N keywords
        "watchdog_timeout": 60,  # Auto-recover if no progress for 60s
        "heartbeat_interval": 5,  # Log heartbeat every 5s
        "delay_between_businesses_min": 2,  # Min delay between business pages
        "delay_between_businesses_max": 6,  # Max delay between business pages
        "delay_between_keywords_min": 5,  # Min delay between keywords
        "delay_between_keywords_max": 15,  # Max delay between keywords
        "delay_min": 1,  # Legacy support
        "delay_max": 3,  # Legacy support
    }


def load_config():
    """Load config from file and merge with defaults."""
    with LOCK:
        defaults = get_default_config()
        if not os.path.exists(CONFIG_FILE):
            return defaults
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
                # Merge: user config overrides defaults
                merged = {**defaults, **user_config}
                return merged
        except Exception:
            return defaults


def update_config(key, value):
    with LOCK:
        config = load_config()
        config[key] = value
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return config


def get_value(key, default=None):
    config = load_config()
    return config.get(key, default)
