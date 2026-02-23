import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import tkinter as tk
from tkinter import filedialog, messagebox
import pygame
import glob
import random
import threading
import time
import yt_dlp
import io

from utils import get_ffmpeg_path, get_resource_path

DEFAULT_THEME = {
    "window_bg": "#f3f4f6",
    "panel_bg": "#ffffff",
    "input_bg": "#ffffff",
    "muted_bg": "#eef2f7",
    "text": "#111827",
    "muted_text": "#4b5563",
    "border": "#cbd5e1",
    "accent": "#4c67a2",
    "accent_text": "#ffffff",
    "play": "#3f6f51",
    "play_hover": "#5aba7f",
    "accent_hover": "#5d7cbf",
    "scrollbar_bg": "#cbd5e1",
    "scrollbar_trough": "#eef2f7",
    "scrollbar_active": "#94a3b8",
    "slider_bg": "#f3f4f6",
    "slider_trough": "#e5e7eb",
    "slider_active": "#94a3b8",
    "font_family": "DejaVu Sans",
    "font_size": 10,
    "title_font_size": 11,
    "listbox_font_size": 10,
    "listbox_height": 12,
    "padding": 12,
    "panel_padding": 8,
    "control_padding": 6,
    "window_size": "860x560",
    "album_art_size": [300, 300],
    "border_width": 1,
    "button_border_width": 1,
    "corner_radius": 0,
    "relief": "solid"
}

def _theme_int(value, default_value):
    return value if isinstance(value, int) else default_value


def _theme_list(value, length, default_value):
    if isinstance(value, (list, tuple)) and len(value) == length:
        try:
            return [int(v) for v in value]
        except (TypeError, ValueError):
            return default_value
    return default_value


def _theme_size_string(value, default_value):
    if isinstance(value, str) and "x" in value:
        return value
    return default_value


def _theme_relief(value, default_value):
    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in {"flat", "raised", "sunken", "groove", "ridge", "solid"}:
            return value_lower
    return default_value


def build_theme(user_theme):
    theme = {**DEFAULT_THEME, **(user_theme or {})}
    colors = {
        "window_bg": theme["window_bg"],
        "panel_bg": theme["panel_bg"],
        "input_bg": theme["input_bg"],
        "muted_bg": theme["muted_bg"],
        "text": theme["text"],
        "muted_text": theme["muted_text"],
        "border": theme["border"],
        "accent": theme["accent"],
        "accent_text": theme["accent_text"],
        "play": theme["play"],
        "play_hover": theme["play_hover"],
        "accent_hover": theme["accent_hover"]
    }
    album_art_size = tuple(_theme_list(theme.get("album_art_size"), 2, DEFAULT_THEME["album_art_size"]))
    window_size = _theme_size_string(theme.get("window_size"), DEFAULT_THEME["window_size"])
    return theme, colors, album_art_size, window_size

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("Mutagen not available. try installing mutagen")

try:
    from PIL import Image, ImageOps
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Pillow not available. try installing pillow ")


class MusicPlayer:
    def __init__(self, initial_folder=None, theme=None):
        self.theme, self.colors, self.album_art_size, self.window_size = build_theme(theme)
        self.window = tk.Tk()
        self.window.title("MP3 Player")
        self.window.configure(bg=self.colors["window_bg"])

        base_font = (
            self.theme["font_family"],
            _theme_int(self.theme.get("font_size"), DEFAULT_THEME["font_size"]),
        )
        title_font = (
            self.theme["font_family"],
            _theme_int(self.theme.get("title_font_size"), DEFAULT_THEME["title_font_size"]),
        )
        list_font = (
            self.theme["font_family"],
            _theme_int(self.theme.get("listbox_font_size"), DEFAULT_THEME["listbox_font_size"]),
        )
        self.window.option_add("*Font", base_font)

        try:
            icon_path = get_resource_path(os.path.join("assets", "mp3-logo.png"))
            self.app_icon = tk.PhotoImage(file=icon_path)
            self.window.iconphoto(True, self.app_icon)
        except Exception:
            self.app_icon = None

        self.window.geometry(self.window_size)
        self.window.resizable(False, False)

        pygame.mixer.init()

        self.current_folder = None
        self.is_filtering = False
        self.playlist = []
        self.ui_playlist = []
        self.filtered_playlist = []
        self.current_index = 0
        self.current_song_name = None
        self.is_playing = False
        self.is_paused = False
        self.is_downloading = False

        self.cover_art_image = None
        self.setup_ui(title_font, list_font)
        self.media_controls = None

        if initial_folder:
            self.set_folder(initial_folder, show_status=False)

        self.monitor_playback()

    def setup_ui(self, title_font, list_font):
        pad = _theme_int(self.theme.get("padding"), DEFAULT_THEME["padding"])
        panel_pad = _theme_int(self.theme.get("panel_padding"), DEFAULT_THEME["panel_padding"])
        control_pad = _theme_int(self.theme.get("control_padding"), DEFAULT_THEME["control_padding"])
        border_width = _theme_int(self.theme.get("border_width"), DEFAULT_THEME["border_width"])
        button_border_width = _theme_int(self.theme.get("button_border_width"), DEFAULT_THEME["button_border_width"])
        relief_style = _theme_relief(self.theme.get("relief"), DEFAULT_THEME["relief"])

        search_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        search_frame.pack(fill="x", padx=pad, pady=(control_pad, 4))
        tk.Label(
            search_frame,
            text="Search Playlist:",
            bg=self.colors["window_bg"],
            fg=self.colors["text"],
            font=title_font,
        ).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.handle_playlist_search)
        self.search_box = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=self.colors["input_bg"],
            fg=self.colors["text"],
            relief=relief_style,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            insertbackground=self.colors["text"],
        )
        self.search_box.pack(fill="x", padx=(8, 0))

        folder_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        folder_frame.pack(fill="x", padx=pad, pady=4)
        tk.Label(
            folder_frame,
            text="Folder:",
            bg=self.colors["window_bg"],
            fg=self.colors["text"],
            width=12,
            anchor="w",
            font=title_font,
        ).pack(side="left")
        self.folder_label = tk.Label(
            folder_frame,
            text="No folder selected",
            bg=self.colors["muted_bg"],
            fg=self.colors["muted_text"],
            relief=relief_style,
            bd=border_width,
            anchor="w",
            padx=8,
            pady=4,
        )
        self.folder_label.pack(side="left", fill="x", expand=True, padx=(5, 5))
        self.browse_btn = tk.Button(
            folder_frame,
            text="Browse",
            command=self.browse_folder,
            bg=self.colors["accent"],
            fg=self.colors["accent_text"],
            activebackground=self.colors["accent_hover"],
            activeforeground=self.colors["accent_text"],
            highlightbackground=self.colors["border"],
            relief="flat",
            padx=12,
            pady=4,
            bd=button_border_width,
        )
        self.browse_btn.pack(side="right")

        current_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        current_frame.pack(fill="x", padx=pad, pady=4)
        tk.Label(
            current_frame,
            text="Now Playing:",
            bg=self.colors["window_bg"],
            fg=self.colors["text"],
            width=12,
            anchor="w",
            font=title_font,
        ).pack(side="left")
        self.current_song_label = tk.Label(
            current_frame,
            text="None",
            bg=self.colors["muted_bg"],
            fg=self.colors["muted_text"],
            relief=relief_style,
            bd=border_width,
            anchor="w",
            padx=8,
            pady=4,
        )
        self.current_song_label.pack(side="left", fill="x", expand=True, padx=(5, 0))

        main_content_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        main_content_frame.pack(fill="both", expand=True, padx=pad, pady=4)

        playlist_frame = tk.Frame(
            main_content_frame,
            bg=self.colors["panel_bg"],
            relief=relief_style,
            bd=border_width,
        )
        playlist_frame.pack(side="left", fill="both", expand=True)
        list_frame = tk.Frame(playlist_frame, bg=self.colors["panel_bg"])
        list_frame.pack(fill="both", expand=True, padx=panel_pad, pady=panel_pad)
        scrollbar = tk.Scrollbar(
            list_frame,
            bg=self.theme["scrollbar_bg"],
            troughcolor=self.theme["scrollbar_trough"],
            activebackground=self.theme["scrollbar_active"],
            relief="flat",
            bd=0,
        )
        scrollbar.pack(side="right", fill="y")
        self.playlist_box = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg=self.colors["input_bg"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent"],
            selectforeground=self.colors["accent_text"],
            relief="flat",
            highlightthickness=0,
            font=list_font,
            height=_theme_int(self.theme.get("listbox_height"), DEFAULT_THEME["listbox_height"]),
        )
        self.playlist_box.pack(side="left", fill="both", expand=True)
        self.playlist_box.bind('<<ListboxSelect>>', self.on_song_select)
        scrollbar.config(command=self.playlist_box.yview)

        image_frame = tk.Frame(
            main_content_frame,
            width=self.album_art_size[0],
            height=self.album_art_size[1],
            bg=self.colors["panel_bg"],
            relief=relief_style,
            bd=border_width,
        )
        image_frame.pack(side="right", padx=(8, 0))
        image_frame.pack_propagate(False)
        self.album_art_label = tk.Label(
            image_frame,
            bg=self.colors["muted_bg"],
            fg=self.colors["muted_text"],
            text="No Art",
            relief="flat",
            font=title_font,
        )
        self.album_art_label.pack(fill="both", expand=True, pady=2)

        download_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        download_frame.pack(fill="x", padx=pad, pady=4)
        download_frame.columnconfigure(1, weight=1)
        tk.Label(
            download_frame,
            text="URL (YT, SoundCloud, etc):",
            bg=self.colors["window_bg"],
            fg=self.colors["text"],
            anchor="w",
            font=title_font,
        ).grid(row=0, column=0, sticky="w")
        self.url_entry = tk.Entry(
            download_frame,
            bg=self.colors["input_bg"],
            fg=self.colors["text"],
            relief=relief_style,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            insertbackground=self.colors["text"],
        )
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.url_entry.bind('<Return>', lambda e: self.download_song())
        self.download_btn = tk.Button(
            download_frame,
            text="Download",
            command=self.download_song,
            bg=self.colors["accent"],
            fg=self.colors["accent_text"],
            activebackground=self.colors["accent_hover"],
            activeforeground=self.colors["accent_text"],
            highlightbackground=self.colors["border"],
            relief="flat",
            padx=12,
            pady=4,
            bd=button_border_width,
        )
        self.download_btn.grid(row=0, column=2, sticky="e")

        status_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        status_frame.pack(fill="x", padx=pad, pady=(4, 0))
        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            fg=self.colors["muted_text"],
            bg=self.colors["muted_bg"],
            relief=relief_style,
            bd=border_width,
            padx=8,
            pady=4,
            anchor="w",
        )
        self.status_label.pack(fill="x")

        control_frame = tk.Frame(self.window, bg=self.colors["window_bg"])
        control_frame.pack(fill="x", padx=pad, pady=(control_pad, control_pad + 4))
        self.prev_btn = tk.Button(
            control_frame,
            text="<",
            command=self.previous_song,
            bg=self.colors["panel_bg"],
            fg=self.colors["text"],
            highlightbackground=self.colors["border"],
            relief=relief_style,
            bd=button_border_width,
            padx=10,
            pady=4,
        )
        self.prev_btn.pack(side="left", padx=5, pady=0)
        self.play_btn = tk.Button(
            control_frame,
            text="Play",
            command=self.toggle_play,
            bg=self.colors["play"],
            fg=self.colors["accent_text"],
            activebackground=self.colors["play_hover"],
            activeforeground=self.colors["accent_text"],
            highlightbackground=self.colors["border"],
            relief="flat",
            padx=12,
            pady=4,
            bd=button_border_width,
        )
        self.play_btn.pack(side="left", padx=5, pady=0)
        self.next_btn = tk.Button(
            control_frame,
            text=">",
            command=self.next_song,
            bg=self.colors["panel_bg"],
            fg=self.colors["text"],
            highlightbackground=self.colors["border"],
            relief=relief_style,
            bd=button_border_width,
            padx=10,
            pady=4,
        )
        self.next_btn.pack(side="left", padx=5, pady=0)
        self.shuffle_btn = tk.Button(
            control_frame,
            text="Shuffle",
            command=self.shuffle_playlist,
            bg=self.colors["panel_bg"],
            fg=self.colors["text"],
            highlightbackground=self.colors["border"],
            relief=relief_style,
            bd=button_border_width,
            padx=12,
            pady=4,
        )
        self.shuffle_btn.pack(side="left", padx=5, pady=0)
        volume_frame = tk.Frame(control_frame, bg=self.colors["window_bg"])
        volume_frame.pack(side="right", padx=5, pady=0)
        tk.Label(volume_frame, text="Volume:", bg=self.colors["window_bg"], fg=self.colors["text"], font=title_font).pack(side="left", padx=5, pady=0)
        self.volume_scale = tk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=self.set_volume,
            showvalue=0,
            length=120,
            bg=self.theme["slider_bg"],
            fg=self.colors["text"],
            highlightthickness=0,
            troughcolor=self.theme["slider_trough"],
            activebackground=self.theme["slider_active"],
        )
        self.volume_scale.set(70)
        self.volume_scale.pack(side="right")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            self.set_folder(folder)

    def set_folder(self, folder, show_status=True):
        if not folder or not os.path.isdir(folder):
            if show_status:
                self.update_status("Invalid folder selected", "red")
            return False
        self.current_folder = folder
        self.folder_label.config(text=folder)
        self.load_playlist()
        if show_status:
            self.update_status("Folder loaded successfully", "green")
        return True

    def update_status(self, message, color="black"):
        self.status_label.config(text=message, fg=color)
        if color != "red":
            self.window.after(
                5000, lambda: self.status_label.config(text="Ready", fg=self.colors["muted_text"])
            )

    def handle_playlist_search(self, *args):
        query = self.search_var.get().strip()
        self.playlist_box.delete(0, tk.END)

        if not query:
            self.is_filtering = False
            self.ui_playlist = self.playlist.copy()
        else:
            self.is_filtering = True
            self.ui_playlist = []
            for song in self.playlist:
                if query.lower() in song.lower():
                    self.ui_playlist.append(song)

        for song in self.ui_playlist:
            self.playlist_box.insert(tk.END, song)

    def download_song(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Enter a valid URL")
            return
        if not self.current_folder:
            messagebox.showwarning("No Folder", "Select a folder first")
            return
        if self.is_downloading:
            messagebox.showinfo("Download in Progress", "A download is already in progress")
            return
        download_thread = threading.Thread(target=self._download_song_thread, args=(url,), daemon=True)
        download_thread.start()

    def _download_song_thread(self, url):
        self.is_downloading = True
        self.window.after(0, lambda: self.update_status("Starting download...", "blue"))
        self.window.after(0, lambda: self.download_btn.config(state="disabled", text="Downloading..."))
        try:
            ffmpeg_path = get_ffmpeg_path()
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '0'},
                    {'key': 'EmbedThumbnail'}, {'key': 'FFmpegMetadata', 'add_metadata': True},
                ],
                'outtmpl': os.path.join(self.current_folder, '%(title)s.%(ext)s'),
                'writethumbnail': True, 'quiet': True, 'no_warnings': True,
            }
            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'Unknown')
                self.window.after(0, lambda: self.update_status(f"Downloading: {video_title[:50]}...", "blue"))
                ydl.download([url])

            self.window.after(0, lambda: self.update_status(f"Downloaded: {video_title[:40]}...", "green"))
            self.window.after(0, lambda: self.url_entry.delete(0, tk.END))
            self.window.after(0, self.load_playlist)
        except Exception as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg:
                error_msg = "Video is unavailable or private"
            elif "network" in error_msg.lower():
                error_msg = "Network error"
            elif "ffmpeg" in error_msg.lower():
                error_msg = "Download failed: FFmpeg not found in PATH"
            else:
                error_msg = f"Download failed: {error_msg[:50]}..."
            self.window.after(0, lambda: self.update_status(f"{error_msg}", "red"))
        finally:
            self.is_downloading = False
            self.window.after(0, lambda: self.download_btn.config(state="normal", text="Download"))

    def load_playlist(self):
        self.is_filtering = False
        self.search_box.delete(0, tk.END)
        if not self.current_folder:
            return
        mp3_files = glob.glob(os.path.join(self.current_folder, "*.mp3"))
        self.playlist = [os.path.basename(f) for f in mp3_files]
        self.ui_playlist = self.playlist.copy()
        self.playlist_box.delete(0, tk.END)
        for song in self.ui_playlist:
            self.playlist_box.insert(tk.END, song)
        if self.ui_playlist:
            self.current_index = 0
            self.playlist_box.select_set(0)
            self.current_song_label.config(text="Ready to play: " + self.ui_playlist[0])
            self.clear_album_art()
        elif self.current_folder:
            self.update_status("No MP3 files found in selected folder", "orange")

    def toggle_play(self):
        if not self.ui_playlist:
            messagebox.showwarning("No Music", "No songs in queue")
            return
        if self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
                self.play_btn.config(text="Pause")
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
                self.play_btn.config(text="Play")
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
            self.play_btn.config(text="Pause")
            self.current_song_name = self.ui_playlist[self.current_index]
            self.current_song_label.config(text=self.current_song_name)
            self.playlist_box.selection_clear(0, tk.END)
            self.playlist_box.select_set(self.current_index)
            self.playlist_box.see(self.current_index)

            self.update_album_art(song_path)

        except Exception as e:
            messagebox.showerror("Playback Error", f"Couldn't play {song_path}\nError: {str(e)}")
            self.is_playing = False
            self.clear_album_art()

    def clear_album_art(self):
        if self.album_art_label:
            self.album_art_label.config(image='', text="No Art")
            self.cover_art_image = None

    def update_album_art(self, song_path):
        if not MUTAGEN_AVAILABLE or not PILLOW_AVAILABLE:
            self.album_art_label.config(text="Libs Missing", image='')
            return

        try:
            audio = MP3(song_path, ID3=ID3)
            found_image = False
            for key, value in audio.tags.items():
                if key.startswith('APIC'):
                    cover = value.data
                    img = Image.open(io.BytesIO(cover))
                    frame_width = max(self.album_art_label.winfo_width(), self.album_art_size[0])
                    frame_height = max(self.album_art_label.winfo_height(), self.album_art_size[1])
                    img = ImageOps.fit(img, (frame_width, frame_height), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    tk_image = tk.PhotoImage(data=buffer.getvalue())
                    self.album_art_label.config(image=tk_image, text="")
                    self.cover_art_image = tk_image
                    found_image = True
                    break
            if not found_image:
                print("apic not found")
                self.clear_album_art()
        except Exception as e:
            print(f"error reading album art: {e}")
            self.clear_album_art()

    def next_song(self):
        if not self.ui_playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.ui_playlist)
        if self.is_playing or self.is_paused:
            self.play_current_song()
        else:
            self.playlist_box.selection_clear(0, tk.END)
            self.playlist_box.select_set(self.current_index)
            self.current_song_label.config(text=f"Ready: {self.ui_playlist[self.current_index]}")

    def previous_song(self):
        if not self.ui_playlist:
            return
        self.current_index = (self.current_index - 1 + len(self.ui_playlist)) % len(self.ui_playlist)
        if self.is_playing or self.is_paused:
            self.play_current_song()
        else:
            self.playlist_box.selection_clear(0, tk.END)
            self.playlist_box.select_set(self.current_index)
            self.current_song_label.config(text=f"Ready: {self.ui_playlist[self.current_index]}")

    def shuffle_playlist(self):
        if not self.playlist:
            messagebox.showwarning("No Playlist", "Load songs first")
            return
        current_song = self.ui_playlist[self.current_index] if self.current_index < len(self.ui_playlist) else None
        self.search_box.delete(0, tk.END)

        random.shuffle(self.ui_playlist)
        self.playlist_box.delete(0, tk.END)
        for song in self.ui_playlist:
            self.playlist_box.insert(tk.END, song)
        try:
            self.current_index = self.ui_playlist.index(current_song) if current_song else 0
        except ValueError:
            self.current_index = 0
        if self.playlist:
            self.playlist_box.select_set(self.current_index)
        self.update_status("Playlist shuffled", "green")

    def on_song_select(self, event):
        selection = self.playlist_box.curselection()
        if selection and selection[0] < len(self.ui_playlist) and self.current_song_name != self.ui_playlist[selection[0]]:
            self.current_index = selection[0]
            if self.is_playing or self.is_paused:
                self.play_current_song()

    def set_volume(self, value):
        pygame.mixer.music.set_volume(int(value) / 100.0)

    def monitor_playback(self):
        def check_music():
            while True:
                if self.is_playing and not self.is_paused and not pygame.mixer.music.get_busy():
                    self.window.after(0, self.next_song)
                time.sleep(0.5)
        monitor_thread = threading.Thread(target=check_music, daemon=True)
        monitor_thread.start()

    def on_closing(self):
        pygame.mixer.quit()
        self.window.destroy()

    def run(self):
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        try:
            self.window.mainloop()
        except KeyboardInterrupt:
            self.on_closing()