# Qt Themes

Themes for the `mp3qt` app are plain Qt Style Sheet (`.qss`) files applied
directly via `QWidget.setStyleSheet()`

## Selecting a theme

Set `theme_path` in `config.json` (see the app config docs) to the absolute
path of a `.qss` file, or use the app's `Theme` menu (`Load Theme...`,
`Reload Current Theme`, `Clear Theme (System Style)`).

If `theme_path` is unset or fails to load, the app applies no stylesheet at
all and falls back to the default Qt style.

## Object names

These widget object names are useful selectors for custom themes:

- `#rootWidget` — the central widget
- `#songLabel` — now-playing label
- `#statusLabel` — status bar label
- `#albumArt` — album art panel
- `#downloadButton`, `#shuffleButton`, `#playButton` — accent buttons

## Window size and layout spacing

Window fixed-size/dimensions and the central layout's padding/spacing are
not stylesheet-expressible in Qt (no QSS property reaches `QLayout` margins
or top-level window geometry), so they live in `config.json` under
`window`/`layout` instead of in the theme file.

Album art size also lives in `config.json` under `album_art` and is applied
via `setFixedSize()` rather than QSS `min/max-width`/`height`. QSS box-model
properties on a widget override a widget's own `setFixedSize()`, so if
album art sizing were left to each theme's `.qss`, an unstyled/system-style
run (no stylesheet) would leave the label with no size constraint at all
and it would stretch to fill the layout on a resizable window.

## Matugen

`themes/matugen/mp3qt.qss` is a Matugen template — point your Matugen config
at it to generate a live `.qss` theme from your wallpaper colors.
