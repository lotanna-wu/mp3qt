# mp3qt
This is a remake of an mp3 player I made using WinForms

## Linux installation
```bash
git clone git@github.com:lotanna-wu/mp3qt.git && cd mp3qt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/install.sh
```

## Native Linux theming (optional)
By default, `pip`'s PySide6 bundles its own private Qt6 build, which is
usually a different minor version than the system Qt6 — so Linux platform
theme integrations like `qt6ct`/kvantum (native dark mode, accent colors,
etc.) fail to load when no `.qss` theme is set.

To get native theming working when no theme is set, install your distro's
system PySide6 package (matches your system Qt6) instead of pip's wheel. after that enable system-site-packages in your venv and drop the pip-installed copy so the system one is used:
```bash
# edit .venv/pyvenv.cfg: include-system-site-packages = true
pip uninstall PySide6 PySide6_Addons PySide6_Essentials shiboken6
pip install -r requirements.local.txt  # everything except PySide6
```

## FFmpeg
- The app uses `ffmpeg` from your system `PATH`
- If `ffmpeg` is missing, downloads that require conversion(which is basically any download) will fail.

## Node.js
 - Node.js is used in order to properly download from youtube, which requires a JS runtime for the ytdlp-ejs package to complete challenges. I chose Node because I didn't want to install deno, but deno technically is the default. To use the app as is, node should be installed and in your PATH. if you don't wanna use node, edit or remove the js_runtimes option in _download_song_thread (`src/app.py`). Deno is recommended by ytdlp, and I believe it is used by default.

## PyInstaller builds
- `pyinstaller linux.spec`
- 'pyinstaller win.spec

## Linux desktop integration
`scripts/install.sh` builds the Linux bundle, installs the desktop entry and icon, and creates the `mp3qt` CLI launcher.
- Install: `./scripts/install.sh`
- Uninstall: `./scripts/uninstall.sh`

## CLI usage
- Open with a folder: `mp3qt ~/Music`
- Set default folder (no UI): `mp3qt -d ~/Music`

## Screenshots

![MP3 Qt Default theme](./screenshots/mp3qt-showcase-1.png)

![MP3 Qt Cloud theme](./screenshots/mp3qt-showcase-2.png)

![MP3 Qt Blue theme](./screenshots/mp3qt-showcase-3.png)

![MP3 Qt Synth theme](./screenshots/mp3qt-showcase-4.png)
