import json
import os
import threading

CONFIG_FILE = "backend/control.json"
LOCK = threading.Lock()


def load_config():
    with LOCK:
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}


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
