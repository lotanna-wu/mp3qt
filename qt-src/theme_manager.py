import json
import os


class ThemeError(Exception):
    pass


DEFAULT_THEME = {
    "meta": {
        "name": "default",
        "version": 1,
        "author": "qt-src",
    },
    "palette": {
        "window_bg": "#d4d0c8",
        "panel_bg": "#c8c3b6",
        "input_bg": "#ffffff",
        "muted_bg": "#bcb8ad",
        "text": "#141414",
        "muted_text": "#2a2a2a",
        "border": "#5f5a50",
        "accent": "#0a2f7a",
        "accent_text": "#f5f5f5",
        "play": "#1f6a2a",
        "play_hover": "#2e8b3f",
        "accent_hover": "#244ea5",
        "selection_bg": "#0a2f7a",
        "selection_text": "#f5f5f5",
        "status_info": "#0d47a1",
        "status_success": "#1b5e20",
        "status_error": "#b00020",
    },
    "typography": {
        "font_family": "Courier New",
        "font_size": 10,
        "title_font_size": 10,
        "list_font_size": 10,
    },
    "metrics": {
        "window_width": 920,
        "window_height": 620,
        "padding": 12,
        "spacing": 8,
        "border_width": 1,
        "button_border_width": 1,
        "radius": 0,
        "album_art_width": 300,
        "album_art_height": 300,
    },
    "effects": {
        "field_shadow": "sunken",
        "status_shadow": "raised",
    },
    "images": {
        "window_bg": "",
    },
    "qss": "",
}


def _merge_dict(base, override):
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


class ThemeManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self.theme_dir = os.path.join(project_root, "qt-themes")
        self.default_theme_path = os.path.join(self.theme_dir, "default.json")

    def load_theme(self, theme_path):
        if not theme_path:
            raise ThemeError("Theme path is empty.")
        path = os.path.abspath(os.path.expanduser(theme_path))
        if not os.path.isfile(path):
            raise ThemeError(f"Theme file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ThemeError(f"Theme JSON parse error: {exc}") from exc
        except OSError as exc:
            raise ThemeError(f"Failed to read theme: {exc}") from exc

        merged = _merge_dict(DEFAULT_THEME, loaded)
        self._normalize_theme(merged, path)
        return merged, path

    def load_default_theme(self):
        if os.path.isfile(self.default_theme_path):
            return self.load_theme(self.default_theme_path)
        return _merge_dict({}, DEFAULT_THEME), self.default_theme_path

    def _normalize_theme(self, theme, source_path):
        metrics = theme["metrics"]
        for key in (
            "window_width",
            "window_height",
            "padding",
            "spacing",
            "border_width",
            "button_border_width",
            "radius",
            "album_art_width",
            "album_art_height",
        ):
            try:
                metrics[key] = int(metrics[key])
            except (TypeError, ValueError):
                metrics[key] = DEFAULT_THEME["metrics"][key]

        typography = theme["typography"]
        for key in ("font_size", "title_font_size", "list_font_size"):
            try:
                typography[key] = int(typography[key])
            except (TypeError, ValueError):
                typography[key] = DEFAULT_THEME["typography"][key]

        images = theme.get("images", {})
        bg = images.get("window_bg", "")
        if bg:
            if not os.path.isabs(bg):
                bg = os.path.abspath(os.path.join(os.path.dirname(source_path), bg))
            if not os.path.isfile(bg):
                bg = ""
        images["window_bg"] = bg
        theme["images"] = images

        field_shadow = theme.get("effects", {}).get("field_shadow", "sunken")
        status_shadow = theme.get("effects", {}).get("status_shadow", "raised")
        if field_shadow not in {"plain", "raised", "sunken"}:
            theme["effects"]["field_shadow"] = "sunken"
        if status_shadow not in {"plain", "raised", "sunken"}:
            theme["effects"]["status_shadow"] = "raised"

    def build_stylesheet(self, theme):
        p = theme["palette"]
        m = theme["metrics"]
        t = theme["typography"]
        radius = max(0, m["radius"])
        border = max(0, m["border_width"])
        button_border = max(0, m["button_border_width"])
        bg_image = theme.get("images", {}).get("window_bg", "")

        root_bg = f"background-color: {p['window_bg']};"
        if bg_image:
            safe_path = bg_image.replace("\\", "/")
            root_bg += (
                f"background-image: url('{safe_path}');"
                "background-position: center;"
                "background-repeat: no-repeat;"
            )

        qss = f"""
QWidget {{
    color: {p['text']};
    font-family: "{t['font_family']}";
    font-size: {t['font_size']}pt;
}}
#rootWidget {{
    {root_bg}
}}
QLabel {{
    background: transparent;
}}
#albumArt {{
    background-color: {p['muted_bg']};
    border: {border}px solid {p['border']};
    border-radius: {radius}px;
}}
#folderLabel, #songLabel, #statusLabel {{
    background-color: {p['muted_bg']};
    border: {border}px solid {p['border']};
    border-radius: {radius}px;
    padding: 4px 8px;
}}
QLineEdit, QListWidget {{
    background-color: {p['input_bg']};
    border: {border}px solid {p['border']};
    border-radius: {radius}px;
    padding: 4px;
    selection-background-color: {p['selection_bg']};
    selection-color: {p['selection_text']};
}}
QListWidget {{
    font-size: {t['list_font_size']}pt;
}}
QPushButton {{
    background-color: {p['panel_bg']};
    color: {p['text']};
    border: {button_border}px solid {p['border']};
    border-radius: {radius}px;
    padding: 5px 10px;
}}
QPushButton:hover {{
    background-color: {p['muted_bg']};
}}
QPushButton:pressed {{
    padding-left: 6px;
    padding-top: 6px;
}}
#browseButton, #downloadButton, #shuffleButton {{
    background-color: {p['accent']};
    color: {p['accent_text']};
}}
#browseButton:hover, #downloadButton:hover, #shuffleButton:hover {{
    background-color: {p['accent_hover']};
}}
#playButton {{
    background-color: {p['play']};
    color: {p['accent_text']};
}}
#playButton:hover {{
    background-color: {p['play_hover']};
}}
QMenuBar {{
    background-color: {p['panel_bg']};
    border: {border}px solid {p['border']};
}}
QMenu {{
    background-color: {p['panel_bg']};
    border: {border}px solid {p['border']};
}}
QSlider::groove:horizontal {{
    border: {border}px solid {p['border']};
    height: 8px;
    background: {p['muted_bg']};
}}
QSlider::handle:horizontal {{
    background: {p['accent']};
    border: {border}px solid {p['border']};
    width: 14px;
    margin: -4px 0;
}}
"""
        user_qss = theme.get("qss", "")
        if user_qss:
            qss = f"{qss}\n{user_qss}\n"
        return qss
