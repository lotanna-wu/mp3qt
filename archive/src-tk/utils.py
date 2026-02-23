import json
import os
import shutil
import sys

APP_NAME = "mp3-player"


def get_ffmpeg_path():
    return shutil.which("ffmpeg")


def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)


def get_config_path():
    base_dir = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    config_dir = os.path.join(base_dir, APP_NAME)
    return os.path.join(config_dir, "config.json")


def load_config():
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_config(config):
    config_path = get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)


def get_theme_path():
    base_dir = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    config_dir = os.path.join(base_dir, APP_NAME)
    return os.path.join(config_dir, "theme.json")


def load_theme():
    theme_path = get_theme_path()
    try:
        with open(theme_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        print("Failed to load theme: FileNotFoundError")
        return {}
    except json.JSONDecodeError:
        print("Failed to load theme: JSONDecodeError")
        return {}
