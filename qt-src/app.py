import glob
import io
import os
import random
import threading
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
import yt_dlp
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

try:
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    from PIL import Image, ImageOps

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils import get_ffmpeg_path, get_resource_path, load_config, save_config
from theme_manager import ThemeError, ThemeManager


class MusicPlayer(QMainWindow):
    status_update = Signal(str, str)
    download_button_state = Signal(bool, str)
    download_clear_url = Signal()
    reload_playlist_signal = Signal()

    def __init__(self, initial_folder=None):
        super().__init__()
        self.setWindowTitle("MP3 Player (Qt)")

        icon_path = get_resource_path(os.path.join("assets", "mp3-logo.png"))
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        pygame.mixer.init()

        self.current_folder = None
        self.playlist = []
        self.ui_playlist = []
        self.current_index = 0
        self.current_song_name = None
        self.is_playing = False
        self.is_paused = False
        self.is_downloading = False
        self.current_theme_path = None
        self.theme = None
        self.theme_manager = ThemeManager(PROJECT_ROOT)

        self._setup_ui()
        self._bind_signals()
        self._start_playback_monitor()
        self._load_initial_theme()

        if initial_folder:
            self.set_folder(initial_folder, show_status=False)

    def _setup_ui(self):
        menu = self.menuBar()
        theme_menu = menu.addMenu("Theme")
        load_theme_action = QAction("Load Theme...", self)
        load_theme_action.triggered.connect(self.choose_theme_file)
        theme_menu.addAction(load_theme_action)

        reload_theme_action = QAction("Reload Current Theme", self)
        reload_theme_action.triggered.connect(self.reload_current_theme)
        theme_menu.addAction(reload_theme_action)

        theme_menu.addSeparator()

        reset_theme_action = QAction("Reset to Default", self)
        reset_theme_action.triggered.connect(self.reset_theme)
        theme_menu.addAction(reset_theme_action)

        root = QWidget(self)
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search Playlist:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter songs...")
        self.search_input.textChanged.connect(self.handle_playlist_search)
        search_row.addWidget(self.search_input)
        main_layout.addLayout(search_row)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setObjectName("folderLabel")
        self.folder_label.setMinimumHeight(28)
        self.folder_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.folder_label.setFrameShape(QFrame.Shape.Panel)
        self.folder_label.setFrameShadow(QFrame.Shadow.Sunken)
        self.folder_label.setLineWidth(1)
        folder_row.addWidget(self.folder_label, 1)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("browseButton")
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_row.addWidget(self.browse_btn)
        main_layout.addLayout(folder_row)

        now_row = QHBoxLayout()
        now_row.addWidget(QLabel("Now Playing:"))
        self.current_song_label = QLabel("None")
        self.current_song_label.setObjectName("songLabel")
        self.current_song_label.setMinimumHeight(28)
        self.current_song_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.current_song_label.setFrameShape(QFrame.Shape.Panel)
        self.current_song_label.setFrameShadow(QFrame.Shadow.Sunken)
        self.current_song_label.setLineWidth(1)
        now_row.addWidget(self.current_song_label, 1)
        main_layout.addLayout(now_row)

        content_row = QHBoxLayout()
        self.playlist_box = QListWidget()
        self.playlist_box.currentRowChanged.connect(self.on_song_select)
        self.playlist_box.itemClicked.connect(self.on_song_clicked)
        content_row.addWidget(self.playlist_box, 1)

        self.album_art_label = QLabel("No Art")
        self.album_art_label.setObjectName("albumArt")
        self.album_art_label.setFixedSize(300, 300)
        self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art_label.setStyleSheet("border: 1px solid #bdbdbd;")
        content_row.addWidget(self.album_art_label)
        main_layout.addLayout(content_row, 1)

        download_row = QHBoxLayout()
        download_row.addWidget(QLabel("URL (YT, SoundCloud, etc):"))
        self.url_input = QLineEdit()
        self.url_input.returnPressed.connect(self.download_song)
        download_row.addWidget(self.url_input, 1)
        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.clicked.connect(self.download_song)
        download_row.addWidget(self.download_btn)
        main_layout.addLayout(download_row)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumHeight(28)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.status_label.setFrameShape(QFrame.Shape.Panel)
        self.status_label.setFrameShadow(QFrame.Shadow.Raised)
        self.status_label.setLineWidth(1)
        status_row.addWidget(self.status_label)
        main_layout.addLayout(status_row)

        controls_row = QHBoxLayout()
        self.prev_btn = QPushButton("<")
        self.prev_btn.clicked.connect(self.previous_song)
        controls_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("playButton")
        self.play_btn.clicked.connect(self.toggle_play)
        controls_row.addWidget(self.play_btn)

        self.next_btn = QPushButton(">")
        self.next_btn.clicked.connect(self.next_song)
        controls_row.addWidget(self.next_btn)

        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.setObjectName("shuffleButton")
        self.shuffle_btn.clicked.connect(self.shuffle_playlist)
        controls_row.addWidget(self.shuffle_btn)

        controls_row.addStretch()
        controls_row.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(140)
        self.volume_slider.valueChanged.connect(self.set_volume)
        controls_row.addWidget(self.volume_slider)
        main_layout.addLayout(controls_row)

        self.update_status("Ready", "default")
        self.set_volume(70)

    def _bind_signals(self):
        self.status_update.connect(self.update_status)
        self.download_button_state.connect(self._set_download_button_state)
        self.download_clear_url.connect(self.url_input.clear)
        self.reload_playlist_signal.connect(self.load_playlist)

    def _start_playback_monitor(self):
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(500)
        self.playback_timer.timeout.connect(self._monitor_playback_tick)
        self.playback_timer.start()

    def _load_initial_theme(self):
        config = load_config()
        configured_theme = config.get("qt_theme_path")
        if configured_theme:
            if self.apply_theme_from_path(configured_theme, persist=False):
                return
        self.reset_theme(show_status=False)

    def choose_theme_file(self):
        start_dir = self.theme_manager.theme_dir
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load Theme File",
            start_dir,
            "Theme JSON (*.json)",
        )
        if not selected:
            return
        self.apply_theme_from_path(selected, persist=True)

    def reload_current_theme(self):
        if not self.current_theme_path:
            self.update_status("No current theme to reload", "error")
            return
        self.apply_theme_from_path(self.current_theme_path, persist=False)

    def reset_theme(self, show_status=True):
        theme, theme_path = self.theme_manager.load_default_theme()
        self.apply_theme(theme, theme_path, persist=True)
        if show_status:
            self.update_status(f"Theme reset: {theme['meta'].get('name', 'default')}", "success")

    def apply_theme_from_path(self, theme_path, persist=True):
        try:
            theme, resolved_path = self.theme_manager.load_theme(theme_path)
        except ThemeError as exc:
            self.update_status(str(exc), "error")
            QMessageBox.warning(self, "Theme Load Error", str(exc))
            return False

        self.apply_theme(theme, resolved_path, persist=persist)
        self.update_status(f"Theme loaded: {theme['meta'].get('name', 'custom')}", "success")
        return True

    def apply_theme(self, theme, theme_path, persist=True):
        self.theme = theme
        self.current_theme_path = theme_path

        m = theme["metrics"]
        spacing = max(0, int(m.get("spacing", 8)))
        padding = max(0, int(m.get("padding", 12)))
        self.centralWidget().layout().setSpacing(spacing)
        self.centralWidget().layout().setContentsMargins(padding, padding, padding, padding)

        self.setFixedSize(max(640, m["window_width"]), max(480, m["window_height"]))
        self.album_art_label.setFixedSize(
            max(120, m["album_art_width"]),
            max(120, m["album_art_height"]),
        )

        font_family = theme["typography"].get("font_family", "Courier New")
        font_size = int(theme["typography"].get("font_size", 10))
        self.setFont(QFont(font_family, font_size))

        qss = self.theme_manager.build_stylesheet(theme)
        self.setStyleSheet(qss)

        self._apply_field_shadow(self.folder_label, theme["effects"].get("field_shadow", "sunken"))
        self._apply_field_shadow(self.current_song_label, theme["effects"].get("field_shadow", "sunken"))
        self._apply_field_shadow(self.status_label, theme["effects"].get("status_shadow", "raised"))

        if persist:
            config = load_config()
            config["qt_theme_path"] = theme_path
            save_config(config)

    def _apply_field_shadow(self, widget, style):
        widget.setFrameShape(QFrame.Shape.Panel)
        widget.setLineWidth(1)
        if style == "raised":
            widget.setFrameShadow(QFrame.Shadow.Raised)
        elif style == "plain":
            widget.setFrameShadow(QFrame.Shadow.Plain)
        else:
            widget.setFrameShadow(QFrame.Shadow.Sunken)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if folder:
            self.set_folder(folder)

    def set_folder(self, folder, show_status=True):
        if not folder or not os.path.isdir(folder):
            if show_status:
                self.update_status("Invalid folder selected", "error")
            return False
        self.current_folder = folder
        self.folder_label.setText(folder)
        self.load_playlist()
        if show_status:
            self.update_status("Folder loaded successfully", "success")
        return True

    def update_status(self, message, level="default"):
        palette = (self.theme or {}).get("palette", {})
        if level == "error":
            color = palette.get("status_error", "#b00020")
        elif level == "success":
            color = palette.get("status_success", "#1b5e20")
        elif level == "info":
            color = palette.get("status_info", "#0d47a1")
        else:
            color = palette.get("text", "#333333")
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")

    def handle_playlist_search(self, value):
        query = value.strip().lower()
        if not query:
            self.ui_playlist = self.playlist.copy()
        else:
            self.ui_playlist = [song for song in self.playlist if query in song.lower()]
        self._refresh_playlist_widget()

    def _refresh_playlist_widget(self):
        self.playlist_box.clear()
        for song in self.ui_playlist:
            self.playlist_box.addItem(QListWidgetItem(song))
        if self.ui_playlist:
            self.current_index = min(self.current_index, len(self.ui_playlist) - 1)
            self.playlist_box.setCurrentRow(self.current_index)
        else:
            self.current_index = 0

    def download_song(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Enter a valid URL")
            return
        if not self.current_folder:
            QMessageBox.warning(self, "No Folder", "Select a folder first")
            return
        if self.is_downloading:
            QMessageBox.information(self, "Download in Progress", "A download is already in progress")
            return
        thread = threading.Thread(target=self._download_song_thread, args=(url,), daemon=True)
        thread.start()

    def _download_song_thread(self, url):
        self.is_downloading = True
        self.status_update.emit("Starting download...", "info")
        self.download_button_state.emit(False, "Downloading...")
        try:
            ffmpeg_path = get_ffmpeg_path()
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"},
                    {"key": "EmbedThumbnail"},
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
                "outtmpl": os.path.join(self.current_folder, "%(title)s.%(ext)s"),
                "writethumbnail": True,
                "quiet": True,
                "no_warnings": True,
            }
            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get("title", "Unknown")
                self.status_update.emit(f"Downloading: {video_title[:50]}...", "info")
                ydl.download([url])

            self.status_update.emit(f"Downloaded: {video_title[:40]}...", "success")
            self.download_clear_url.emit()
            self.reload_playlist_signal.emit()
        except Exception as exc:
            error_msg = str(exc)
            if "Video unavailable" in error_msg:
                error_msg = "Video is unavailable or private"
            elif "network" in error_msg.lower():
                error_msg = "Network error"
            elif "ffmpeg" in error_msg.lower():
                error_msg = "Download failed: FFmpeg not found in PATH"
            else:
                error_msg = f"Download failed: {error_msg[:60]}..."
            self.status_update.emit(error_msg, "error")
        finally:
            self.is_downloading = False
            self.download_button_state.emit(True, "Download")

    def _set_download_button_state(self, enabled, text):
        self.download_btn.setEnabled(enabled)
        self.download_btn.setText(text)

    def load_playlist(self):
        self.search_input.clear()
        if not self.current_folder:
            return
        mp3_files = glob.glob(os.path.join(self.current_folder, "*.mp3"))
        self.playlist = [os.path.basename(path) for path in mp3_files]
        self.ui_playlist = self.playlist.copy()
        self.current_index = 0
        self._refresh_playlist_widget()
        if self.ui_playlist:
            self.current_song_label.setText(f"Ready to play: {self.ui_playlist[0]}")
            self.clear_album_art()
        else:
            self.current_song_label.setText("None")
            self.clear_album_art()
            self.update_status("No MP3 files found in selected folder", "info")

    def toggle_play(self):
        if not self.ui_playlist:
            QMessageBox.warning(self, "No Music", "No songs in queue")
            return
        if self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
                self.play_btn.setText("Pause")
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
                self.play_btn.setText("Play")
        else:
            self.play_current_song()

    def play_current_song(self):
        if not self.ui_playlist or self.current_index >= len(self.ui_playlist):
            self.is_playing = False
            pygame.mixer.music.stop()
            self.clear_album_art()
            return

        song_path = os.path.join(self.current_folder, self.ui_playlist[self.current_index])
        try:
            pygame.mixer.music.load(song_path)
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
            self.play_btn.setText("Pause")
            self.current_song_name = self.ui_playlist[self.current_index]
            self.current_song_label.setText(self.current_song_name)
            self.playlist_box.setCurrentRow(self.current_index)
            self.update_album_art(song_path)
        except Exception as exc:
            QMessageBox.critical(self, "Playback Error", f"Couldn't play {song_path}\nError: {exc}")
            self.is_playing = False
            self.clear_album_art()

    def clear_album_art(self):
        self.album_art_label.setPixmap(QPixmap())
        self.album_art_label.setText("No Art")

    def update_album_art(self, song_path):
        if not MUTAGEN_AVAILABLE or not PILLOW_AVAILABLE:
            self.album_art_label.setPixmap(QPixmap())
            self.album_art_label.setText("Libs Missing")
            return

        try:
            audio = MP3(song_path, ID3=ID3)
            if not audio.tags:
                self.clear_album_art()
                return

            for key, value in audio.tags.items():
                if key.startswith("APIC"):
                    img = Image.open(io.BytesIO(value.data))
                    img = ImageOps.fit(img, (300, 300), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    image_data = buffer.getvalue()

                    qimage = QImage.fromData(image_data, "PNG")
                    pixmap = QPixmap.fromImage(qimage)
                    self.album_art_label.setText("")
                    self.album_art_label.setPixmap(pixmap)
                    return
            self.clear_album_art()
        except Exception:
            self.clear_album_art()

    def next_song(self):
        if not self.ui_playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.ui_playlist)
        if self.is_playing or self.is_paused:
            self.play_current_song()
        else:
            self.playlist_box.setCurrentRow(self.current_index)
            self.current_song_label.setText(f"Ready: {self.ui_playlist[self.current_index]}")

    def previous_song(self):
        if not self.ui_playlist:
            return
        self.current_index = (self.current_index - 1 + len(self.ui_playlist)) % len(self.ui_playlist)
        if self.is_playing or self.is_paused:
            self.play_current_song()
        else:
            self.playlist_box.setCurrentRow(self.current_index)
            self.current_song_label.setText(f"Ready: {self.ui_playlist[self.current_index]}")

    def shuffle_playlist(self):
        if not self.ui_playlist:
            QMessageBox.warning(self, "No Playlist", "Load songs first")
            return
        current_song = self.ui_playlist[self.current_index] if self.current_index < len(self.ui_playlist) else None
        random.shuffle(self.ui_playlist)
        self._refresh_playlist_widget()
        if current_song and current_song in self.ui_playlist:
            self.current_index = self.ui_playlist.index(current_song)
            self.playlist_box.setCurrentRow(self.current_index)
        self.update_status("Playlist shuffled", "success")

    def on_song_select(self, row):
        if row < 0 or row >= len(self.ui_playlist):
            return
        self.current_index = row
        if not self.is_playing and not self.is_paused:
            self.current_song_label.setText(f"Ready: {self.ui_playlist[row]}")

    def on_song_clicked(self, item):
        row = self.playlist_box.row(item)
        if row < 0 or row >= len(self.ui_playlist):
            return
        self.current_index = row
        self.play_current_song()

    def set_volume(self, value):
        pygame.mixer.music.set_volume(int(value) / 100.0)

    def _monitor_playback_tick(self):
        if self.is_playing and not self.is_paused and not pygame.mixer.music.get_busy():
            self.next_song()

    def closeEvent(self, event):
        pygame.mixer.quit()
        super().closeEvent(event)
