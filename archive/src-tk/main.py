import argparse
import os
import sys

from app import MusicPlayer
from utils import load_config, save_config, load_theme, get_theme_path


def main():
    parser = argparse.ArgumentParser(description="MP3 Player")
    parser.add_argument(
        "-d",
        "--default-directory",
        dest="default_directory",
        help="Set the default music directory and exit",
    )
    parser.add_argument(
        "-t",
        "--theme",
        dest="theme",
        help="Set the default theme from a file path (copied to ~/.config/mp3-player/theme.json)",
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
    if args.theme:
        theme_src = os.path.abspath(os.path.expanduser(args.theme))
        if not os.path.isfile(theme_src):
            print(f"Theme file not found: {theme_src}")
            return 1
        theme_dst = get_theme_path()
        os.makedirs(os.path.dirname(theme_dst), exist_ok=True)
        try:
            with open(theme_src, "r", encoding="utf-8") as handle:
                theme_text = handle.read()
            with open(theme_dst, "w", encoding="utf-8") as handle:
                handle.write(theme_text)
        except Exception as exc:
            print(f"Failed to set theme: {exc}")
            return 1
        print(f"Theme set from: {theme_src}")

    theme_data = load_theme()

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
        import pygame
        print("Pygame available")
    except ImportError:
        print("Pygame not found (required for the app)")
        return 1
    try:
        import yt_dlp
        print("yt-dlp available")
    except ImportError:
        print("yt-dlp not found (required for the app)")
        return 1

    try:
        from app import MUTAGEN_AVAILABLE, PILLOW_AVAILABLE
        if MUTAGEN_AVAILABLE:
            print("Mutagen available (for metadata)")
        if PILLOW_AVAILABLE:
            print("Pillow available (for images)")
    except Exception:
        pass

    print("\nStarting player...")
    app = MusicPlayer(initial_folder=launch_dir, theme=theme_data)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
