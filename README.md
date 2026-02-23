# mp3-player
this is a remake of an mp3 player i made using winforms

## FFmpeg
- The app uses `ffmpeg` from your system `PATH`
- If `ffmpeg` is missing, downloads that require conversion will fail and show an error.

## PyInstaller builds
- Linux: `pyinstaller app.spec`

## Linux desktop integration
After building the Linux bundle, install the desktop entry and icon:
- Install (user): `scripts/install.sh`
- Install (system): `scripts/install.sh --system`

## CLI usage
- Open with a folder: `mp3-player ~/Music`
- Set default folder (no UI): `mp3-player -d ~/Music`

## Themes
Create `~/.config/mp3-player/theme.json` with any of the keys below, or set it from a file with
- `window_bg`
- `panel_bg`
- `input_bg`
- `muted_bg`
- `text`
- `muted_text`
- `border`
- `accent`
- `accent_text`
- `play`
- `scrollbar_bg`
- `scrollbar_trough`
- `scrollbar_active`
- `slider_bg`
- `slider_trough`
- `slider_active`
- `font_family`
- `font_size`
- `title_font_size`
- `listbox_font_size`
- `listbox_height`
- `padding`
- `panel_padding`
- `control_padding`
- `window_size`
- `min_window_size`
- `album_art_size`
- `border_width`
- `button_border_width`
- `corner_radius` (not used by Tk)

Theme files can be created manually or passed via `-t`.
