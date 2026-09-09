import os
import sys


class ThemeError(Exception):
    pass


class ThemeManager:
    def __init__(self, project_root):
        self.project_root = os.path.abspath(project_root)
        runtime_root = os.path.abspath(getattr(sys, "_MEIPASS", self.project_root))
        bundled_theme_dir = os.path.join(runtime_root, "themes")
        project_theme_dir = os.path.join(self.project_root, "themes")

        if os.path.isdir(project_theme_dir):
            self.theme_dir = project_theme_dir
        else:
            self.theme_dir = bundled_theme_dir

    def load_qss(self, theme_path):
        if not theme_path:
            raise ThemeError("Theme path is empty.")
        path = os.path.abspath(os.path.expanduser(theme_path))
        if not os.path.isfile(path):
            raise ThemeError(f"Theme file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read(), path
        except OSError as exc:
            raise ThemeError(f"Failed to read theme: {exc}") from exc
