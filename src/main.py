import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from app import MusicPlayer
from utils import load_config, save_config


def main():
    parser = argparse.ArgumentParser(description="MP3 Player (Qt)")
    parser.add_argument(
        "-d",
        "--default-directory",
        dest="default_directory",
        help="Set the default music directory and exit",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Music directory to open on launch",
    )
    args = parser.parse_args()

    if args.default_directory:
        default_dir = os.path.abspath(os.path.expanduser(args.default_directory))
        if not os.path.isdir(default_dir):
            print(f"Invalid directory: {default_dir}")
            return 1
        config = load_config()
        config["default_directory"] = default_dir
        save_config(config)
        print(f"Default directory set to: {default_dir}")
        return 0

    config = load_config()
    default_dir = config.get("default_directory")
    launch_dir = None

    if args.path:
        launch_dir = os.path.abspath(os.path.expanduser(args.path))
        if not os.path.isdir(launch_dir):
            print(f"Invalid directory: {launch_dir}")
            return 1
    elif default_dir and os.path.isdir(default_dir):
        launch_dir = default_dir

    print("Checking dependencies...")
    try:
        import pygame  # noqa: F401

        print("Pygame available")
    except ImportError:
        print("Pygame not found (required for the app)")
        return 1
    try:
        import yt_dlp  # noqa: F401

        print("yt-dlp available")
    except ImportError:
        print("yt-dlp not found (required for the app)")
        return 1
    try:
        import PySide6  # noqa: F401

        print("PySide6 available")
    except ImportError:
        print("PySide6 not found (required for the Qt app)")
        return 1

    qapp = QApplication(sys.argv)
    player = MusicPlayer(initial_folder=launch_dir)
    player.show()
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
