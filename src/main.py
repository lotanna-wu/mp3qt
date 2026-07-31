import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from app import MusicPlayer
from single_instance import SingleInstance
from utils import load_config, save_config


def main():
    parser = argparse.ArgumentParser(description="mp3qt")
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
        import yt_dlp
        print("yt-dlp available")
    except ImportError:
        print("yt-dlp not found (required for the app)")
        return 1
    try:
        import PySide6
        print("PySide6 available")
    except ImportError:
        print("PySide6 not found (required for the Qt app)")
        return 1

    qapp = QApplication(sys.argv)

    instance = SingleInstance()
    if not instance.try_acquire(payload=launch_dir or ""):
        print("mp3qt is already running -- focusing existing window")
        return 0

    player = MusicPlayer(initial_folder=launch_dir)

    def on_message(payload):
        player.showNormal()
        player.raise_()
        player.activateWindow()
        if payload and os.path.isdir(payload):
            player.set_folder(payload)

    instance.message_received.connect(on_message)

    player.show()
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
