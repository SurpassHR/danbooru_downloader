# coding: utf-8
import os
import json
from typing import Any, Dict, Optional
from pathlib import Path


def loadConfig() -> Dict[str, Any]:
    config_path = os.path.join("config", "config.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load config: {str(e)}")


def setConfig(key: str, value: Any) -> bool:
    try:
        config_path = os.path.join("config", "config.json")
        Path(os.path.dirname(config_path)).mkdir(parents=True, exist_ok=True)

        config = loadConfig()
        keys = key.split(".")
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


def getConfig(key: str, default: Optional[Any] = None) -> Any:
    try:
        config = loadConfig()
        keys = key.split(".")
        current = config
        for k in keys:
            if k not in current:
                return default
            current = current[k]
        return current
    except Exception:
        return default
