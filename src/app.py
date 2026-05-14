import glob
import hashlib
import io
import os
import random
import threading

import yt_dlp
from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal, QUrl
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

from PySide6.QtDBus import QDBusConnection
from PySide6.QtDBus import QDBusMessage, QDBusObjectPath, QDBusVariant
from mpris import MprisRootAdaptor, MprisPlayerAdaptor
from media import Mixer

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

from utils import get_ffmpeg_path, get_resource_path, load_config, save_config
from theme_manager import ThemeError, ThemeManager


class MusicPlayer(QMainWindow):
    status_update = Signal(str, str)
    download_button_state = Signal(bool, str)
    download_clear_url = Signal()
    reload_playlist_signal = Signal()

    def __init__(self, initial_folder=None):
        super().__init__()
        self.setWindowTitle("MP3 Qt")

        icon_path = get_resource_path(os.path.join("assets", "mp3-logo.png"))
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.mixer = Mixer(self)

        self.current_folder = None
        self.playlist = []
        self.ui_playlist = []
        self.current_index = 0
        self._is_user_seeking = False
        
        self.is_downloading = False
        self.current_theme_path = None
        self.theme = None
        self.theme_manager = ThemeManager(PROJECT_ROOT)
        self._mpris_root_adaptor = None
        self._mpris_player_adaptor = None

        self._setup_ui()
        self._bind_signals()
        self._load_initial_theme()
        self._mpris_obj = self.register_mpris()

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
        playlist_column = QVBoxLayout()
        playlist_column.setSpacing(6)
        self.playlist_box = QListWidget()
        self.playlist_box.setMinimumHeight(220)
        self.playlist_box.currentRowChanged.connect(self.on_song_select)
        self.playlist_box.itemClicked.connect(self.on_song_clicked)
        playlist_column.addWidget(self.playlist_box, 1)

        seek_row = QHBoxLayout()
        self.seek_elapsed_label = QLabel("0:00")
        self.seek_elapsed_label.setMinimumWidth(40)
        seek_row.addWidget(self.seek_elapsed_label)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        seek_row.addWidget(self.seek_slider, 1)
        self.seek_duration_label = QLabel("0:00")
        self.seek_duration_label.setMinimumWidth(40)
        self.seek_duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        seek_row.addWidget(self.seek_duration_label)
        self.seek_slider.sliderMoved.connect(self.mixer.set_position)
        playlist_column.addLayout(seek_row)
        content_row.addLayout(playlist_column, 1)

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

    def _bind_signals(self):
        self.status_update.connect(self.update_status)
        self.download_button_state.connect(self._set_download_button_state)
        self.download_clear_url.connect(self.url_input.clear)
        self.reload_playlist_signal.connect(self.load_playlist)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.mixer.position_changed.connect(self._on_player_position_changed)
        self.mixer.duration_changed.connect(self._on_player_duration_changed)

    def _load_initial_theme(self):
        config = load_config()
        configured_theme = config.get("qt_theme_path")
        if configured_theme:
            if self.apply_theme_from_path(configured_theme, persist=False):
                return
        self.reset_theme(show_status=False)

    def choose_theme_file(self):
        start_dir = self.theme_manager.theme_dir
        dialog = QFileDialog(None, "Load Theme File", start_dir, "Theme JSON (*.json)")
        dialog.setStyleSheet("")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        selected_files = dialog.selectedFiles()
        selected = selected_files[0] if selected_files else ""
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

        # fix for theming issue when newly loaded theme has a different size - LO
        # unlock all size constraints first
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)

        new_w = max(640, m["window_width"])
        new_h = max(480, m["window_height"])

        # hide, resize, show, to force Qt to redraw the window
        self.hide()
        self.resize(new_w, new_h)
        self.setFixedSize(new_w, new_h)

        self.album_art_label.setMinimumSize(0, 0)
        self.album_art_label.setMaximumSize(16777215, 16777215)
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

        # forgot i need to rerender the album art 
        if self.mixer.current_track_path and os.path.isfile(self.mixer.current_track_path):
            self.update_album_art(self.mixer.current_track_path)

        # force full layout recalculation before showing
        self.centralWidget().updateGeometry()
        self.centralWidget().layout().activate()
        QTimer.singleShot(0, self.show)

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
        start_dir = self.current_folder if self.current_folder else os.path.expanduser("~")
        dialog = QFileDialog(None, "Select Music Folder", start_dir)
        dialog.setStyleSheet("")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        selected_files = dialog.selectedFiles()
        folder = selected_files[0] if selected_files else ""
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

    def _get_current_song_filename(self):
        track_path = self.mixer.current_track_path
        if not track_path:
            return None
        return os.path.basename(track_path)

    def _sync_playlist_selection(self):
        current_song = self._get_current_song_filename()
        if not self.ui_playlist:
            self.current_index = 0
            with QSignalBlocker(self.playlist_box):
                self.playlist_box.clearSelection()
                self.playlist_box.setCurrentRow(-1)
            return

        if current_song and current_song in self.ui_playlist:
            self.current_index = self.ui_playlist.index(current_song)
            with QSignalBlocker(self.playlist_box):
                self.playlist_box.setCurrentRow(self.current_index)
            return

        self.current_index = min(self.current_index, len(self.ui_playlist) - 1)
        with QSignalBlocker(self.playlist_box):
            self.playlist_box.clearSelection()
            self.playlist_box.setCurrentRow(-1)

    def _refresh_playlist_widget(self):
        with QSignalBlocker(self.playlist_box):
            self.playlist_box.clear()
            for song in self.ui_playlist:
                self.playlist_box.addItem(QListWidgetItem(song))
        self._sync_playlist_selection()

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
                downloaded_path = ydl.prepare_filename(info)

            self._crop_embedded_thumbnail(downloaded_path)

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
                error_msg = f"Download failed: {error_msg[:70]}..."
            self.status_update.emit(error_msg, "error")
        finally:
            self.is_downloading = False
            self.download_button_state.emit(True, "Download")

    def _set_download_button_state(self, enabled, text):
        self.download_btn.setEnabled(enabled)
        self.download_btn.setText(text)

    def _format_time_ms(self, milliseconds):
        total_seconds = max(0, int(milliseconds) // 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _reset_seek_ui(self):
        self._is_user_seeking = False
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setRange(0, 0)
            self.seek_slider.setValue(0)
        self.seek_elapsed_label.setText("0:00")
        self.seek_duration_label.setText("0:00")

    def _on_seek_pressed(self):
        self._is_user_seeking = True

    def _on_seek_moved(self, position):
        self.seek_elapsed_label.setText(self._format_time_ms(position))

    def _on_seek_released(self):
        self.mixer.set_position(self.seek_slider.value())
        self._is_user_seeking = False

    def _on_player_position_changed(self, position):
        if self._is_user_seeking:
            return
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setValue(position)
        self.seek_elapsed_label.setText(self._format_time_ms(position))

    def _on_player_duration_changed(self, duration):
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setRange(0, max(0, duration))
        self.seek_duration_label.setText(self._format_time_ms(duration))

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
            current_song = self._get_current_song_filename()
            if current_song and current_song in self.ui_playlist:
                self.current_song_label.setText(self.mixer.current_song_name)
            else:
                self.current_song_label.setText(f"Ready to play: {self.ui_playlist[0]}")
            self._reset_seek_ui()
            self.clear_album_art()
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
        else:
            self.mixer.clear_track_metadata()
            self.current_song_label.setText("None")
            self._reset_seek_ui()
            self.clear_album_art()
            self.update_status("No MP3 files found in selected folder", "info")
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
    
    def _play(self):
        self.mixer.play()
        self.play_btn.setText("Pause")
        self._emit_mpris_properties_changed({
            "PlaybackStatus": self.get_playback_status(),
            "CanGoNext": self.can_go_next(),
            "CanGoPrevious": self.can_go_previous(),
            "CanPlay": self.can_play(),
            "CanPause": self.can_pause(),
        })
            
    def _pause(self):
        self.mixer.pause()
        self.play_btn.setText("Play")
        self._emit_mpris_properties_changed({
            "PlaybackStatus": self.get_playback_status(),
            "CanGoNext": self.can_go_next(),
            "CanGoPrevious": self.can_go_previous(),
            "CanPlay": self.can_play(),
            "CanPause": self.can_pause(),
        })

    def toggle_play(self):
        if not self.ui_playlist:
            QMessageBox.warning(self, "No Music", "No songs in queue")
            return

        if self.mixer.is_paused():
            self._play()
        elif self.mixer.is_playing():
            self._pause()
        else:
            self.play_current_song()

    def play(self):
        if not self.ui_playlist:
            return
        if self.mixer.is_paused():
            self._play()
        elif not self.mixer.is_playing():
            self.play_current_song()

    def pause(self):
        if self.mixer.is_playing() and not self.mixer.is_paused():
            self._pause()

    def next_from_mpris(self):
        if not self.can_go_next():
            return
        was_paused = self.mixer.is_paused()
        was_stopped = self.mixer.is_stopped()
        self.current_index = (self.current_index + 1) % len(self.ui_playlist)
        self.playlist_box.setCurrentRow(self.current_index)
        if was_stopped:
            song_path = os.path.join(self.current_folder, self.ui_playlist[self.current_index])
            self.mixer.set_track_metadata(song_path, update_song_name=False)
            self.current_song_label.setText(f"Ready: {self.ui_playlist[self.current_index]}")
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
            return

        self.play_current_song()
        if was_paused:
            self._pause()

    def previous_from_mpris(self):
        if not self.can_go_previous():
            return
        was_paused = self.mixer.is_paused()
        was_stopped = self.mixer.is_stopped()
        self.current_index = (self.current_index - 1 + len(self.ui_playlist)) % len(self.ui_playlist)
        self.playlist_box.setCurrentRow(self.current_index)
        if was_stopped:
            song_path = os.path.join(self.current_folder, self.ui_playlist[self.current_index])
            self.mixer.set_track_metadata(song_path, update_song_name=False)
            self.current_song_label.setText(f"Ready: {self.ui_playlist[self.current_index]}")
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
            return

        self.play_current_song()
        if was_paused:
            self._pause()

    def play_current_song(self):
        if not self.ui_playlist or self.current_index >= len(self.ui_playlist):
            self.mixer.stop()
            self.mixer.clear_track_metadata()
            self._sync_playlist_selection()
            self._reset_seek_ui()
            self.clear_album_art()
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
            return

        song_path = os.path.join(self.current_folder, self.ui_playlist[self.current_index])
        try:
            self.mixer.set_source(song_path)
            self.play_btn.setText("Pause")
            self.current_song_label.setText(self.mixer.current_song_name)
            self._sync_playlist_selection()
            self.update_album_art(song_path)
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
        except Exception as exc:
            QMessageBox.critical(self, "Playback Error", f"Couldn't play {song_path}\nError: {exc}")
            self.mixer.stop()
            self.mixer.clear_track_metadata()
            self._reset_seek_ui()
            self.clear_album_art()
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })

    def clear_album_art(self):
        self.album_art_label.setPixmap(QPixmap())
        self.album_art_label.setText("No Art")

    def _crop_embedded_thumbnail(self, downloaded_path):
        if not MUTAGEN_AVAILABLE or not PILLOW_AVAILABLE:
            return

        base_path, _ = os.path.splitext(downloaded_path)
        mp3_path = f"{base_path}.mp3"
        if not os.path.isfile(mp3_path):
            return

        try:
            audio = MP3(mp3_path, ID3=ID3)
            if not audio.tags:
                return

            updated = False
            for key, value in audio.tags.items():
                if not key.startswith("APIC"):
                    continue

                img = Image.open(io.BytesIO(value.data))
                if img.width == img.height:
                    continue

                side = min(img.width, img.height)
                cropped = ImageOps.fit(img, (side, side), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                cropped.save(buffer, format="PNG")

                value.mime = "image/png"
                value.data = buffer.getvalue()
                updated = True

            if updated:
                audio.save()
        except Exception:
            return
    
    # album art rendering is separate from metadata extraction
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
                    target = self.album_art_label.size()
                    target_size = (max(1, target.width()), max(1, target.height()))
                    img = ImageOps.fit(img, target_size, Image.Resampling.LANCZOS)
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

    def next_song(self, force_play=False):
        if not self.ui_playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.ui_playlist)
        if force_play or self.mixer.is_playing() or self.mixer.is_paused():
            self.play_current_song()
        else:
            self.mixer.set_track_metadata(os.path.join(self.current_folder, self.ui_playlist[self.current_index]), update_song_name=False)
            self._sync_playlist_selection()
            self.current_song_label.setText(f"Ready: {self.ui_playlist[self.current_index]}")
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })

    def previous_song(self):
        if not self.ui_playlist:
            return
        self.current_index = (self.current_index - 1 + len(self.ui_playlist)) % len(self.ui_playlist)
        if self.mixer.is_playing() or self.mixer.is_paused():
            self.play_current_song()
        else:
            self.mixer.set_track_metadata(os.path.join(self.current_folder, self.ui_playlist[self.current_index]), update_song_name=False)
            self._sync_playlist_selection()
            self.current_song_label.setText(f"Ready: {self.ui_playlist[self.current_index]}")
            self._emit_mpris_properties_changed({
                "PlaybackStatus": self.get_playback_status(),
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })

    def shuffle_playlist(self):
        if not self.ui_playlist:
            QMessageBox.warning(self, "No Playlist", "Load songs first")
            return
        random.shuffle(self.ui_playlist)
        self._refresh_playlist_widget()
        self.update_status("Playlist shuffled", "success")

    def on_song_select(self, row):
        if row < 0 or row >= len(self.ui_playlist):
            return
        self.current_index = row
        if self.current_folder:
            self.mixer.set_track_metadata(os.path.join(self.current_folder, self.ui_playlist[row]), update_song_name=False)
            self._emit_mpris_properties_changed({
                "Metadata": self.get_mpris_metadata(),
                "CanGoNext": self.can_go_next(),
                "CanGoPrevious": self.can_go_previous(),
                "CanPlay": self.can_play(),
                "CanPause": self.can_pause(),
            })
        if not self.mixer.is_playing() and not self.mixer.is_paused():
            self.current_song_label.setText(f"Ready: {self.ui_playlist[row]}")

    def on_song_clicked(self, item):
        row = self.playlist_box.row(item)
        if row < 0 or row >= len(self.ui_playlist):
            return
        self.current_index = row
        self.play_current_song()

    def set_volume(self, value):
        self.mixer.set_volume(int(value) / 100.0)

    def get_playback_status(self):
        if self.mixer.is_paused():
            return "Paused"
        if self.mixer.is_playing():
            return "Playing"
        return "Stopped"

    def can_play(self):
        # return True
        return bool(self.ui_playlist)

    def can_pause(self):
        return bool(self.ui_playlist)

    def can_go_next(self):
        return len(self.ui_playlist) > 1

    def can_go_previous(self):
        return len(self.ui_playlist) > 1

    def get_mpris_metadata(self):
        if not self.mixer.current_track_path:
            return {
                "mpris:trackid": QDBusObjectPath("/org/mpris/MediaPlayer2/TrackList/NoTrack"),
            }

        metadata = {
            "mpris:trackid": QDBusObjectPath(self._get_mpris_track_id()),
            "xesam:title": self.mixer.current_song_name or "",
            "xesam:artist": [self.mixer.current_artist_name or ""],
            "xesam:album": self.mixer.current_album_name or "",
            "xesam:url": QUrl.fromLocalFile(self.mixer.current_track_path).toString(),
        }
        if self.mixer.current_track_length_us > 0:
            metadata["mpris:length"] = self.mixer.current_track_length_us
        return metadata

    def _emit_mpris_properties_changed(self, changed_properties):
        if not self._mpris_obj:
            return

        changed_properties = {
            key: QDBusVariant(value)
            for key, value in changed_properties.items()
        }
        message = QDBusMessage.createSignal(
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
        )
        message.setArguments([
            "org.mpris.MediaPlayer2.Player",
            changed_properties,
            [],
        ])
        QDBusConnection.sessionBus().send(message)

    def _get_mpris_track_id(self):
        if not self.mixer.current_track_path:
            return "/org/mpris/MediaPlayer2/TrackList/NoTrack"
        digest = hashlib.sha1(self.mixer.current_track_path.encode("utf-8")).hexdigest()
        return f"/com/github/lowu/mp3qt/track/{digest}"
        
    def register_mpris(self):
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            print("Could not connect to session bus")
            return None
        self._mpris_root_adaptor = MprisRootAdaptor(self)
        self._mpris_player_adaptor = MprisPlayerAdaptor(self, self)
        bus.registerObject("/org/mpris/MediaPlayer2", self, QDBusConnection.RegisterOption.ExportAdaptors)
        bus.registerService("org.mpris.MediaPlayer2.mp3qt")
        print("MPRIS registered")
        return self

    def closeEvent(self, event):
        super().closeEvent(event)
