from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QMediaDevices
import os

try:
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

class SongInfo():
    def __init__(self):
        self.song_name = None
        self.artist_name = None
        self.album_name = None
        self.track_path = None
        self.track_length_us = 0
    
    def clear(self):
        self.song_name = None
        self.artist_name = None
        self.album_name = None
        self.track_path = None
        self.track_length_us = 0
    
    def set(self, song_path, update_song_name=True):
        fallback_title = os.path.splitext(os.path.basename(song_path))[0]
        self.track_path = song_path
        self.track_length_us = 0
        self.artist_name = "Unknown Artist"
        self.album_name = "Unknown Album"
        self.song_name = fallback_title

        if not MUTAGEN_AVAILABLE:
            return
        
        try:
            audio = MP3(song_path, ID3=ID3)
        except Exception:
            return

        title_tag = audio.tags.get("TIT2") if audio.tags else None
        artist_tag = audio.tags.get("TPE1") if audio.tags else None
        album_tag = audio.tags.get("TALB") if audio.tags else None

        if title_tag:
            self.song_name = str(title_tag)
        elif update_song_name:
            self.song_name = os.path.basename(song_path)

        if artist_tag:
            self.artist_name = str(artist_tag)
        if album_tag:
            self.album_name = str(album_tag)

        if getattr(audio, "info", None) and getattr(audio.info, "length", None):
            self.track_length_us = int(audio.info.length * 1_000_000)


class Mixer(QObject):
    position_changed = Signal(int)
    duration_changed = Signal(int)
    playback_state_changed = Signal(object)
    media_status_changed = Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent

        self.current_song = SongInfo()

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)

        self.media_devices = QMediaDevices()
        self.media_devices.audioOutputsChanged.connect(self.on_audio_output_changed)
        
        self.player.mediaStatusChanged.connect(self.on_status)
        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.playbackStateChanged.connect(self.playback_state_changed.emit)
    
    # sets the source to song_path, when loaded, it will play automatically
    def set_source(self, song_path, update_song=True):
        self.player.setSource(QUrl.fromLocalFile(song_path))
        self.set_track_metadata(song_path, update_song)
    
    def on_audio_output_changed(self):
        #todo: find a way to autoplay if the player was active before the media change
        vol = self.audio_output.volume()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(vol)
        self.player.setAudioOutput(self.audio_output)

    def on_status(self, status):
        self.media_status_changed.emit(status)
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.app.next_song(force_play=True)
    
    def play(self):
        self.player.play()
            
    def pause(self):
        self.player.pause()

    def stop(self):
        if not self.is_stopped():
            self.player.stop()

    def clear_track_metadata(self):
        self.current_song.clear()
    
    def set_track_metadata(self, song_path, update_song_name=True):
        self.current_song.set(song_path, update_song_name)

    @property
    def current_song_name(self):
        return self.current_song.song_name

    @property
    def current_artist_name(self):
        return self.current_song.artist_name

    @property
    def current_album_name(self):
        return self.current_song.album_name

    @property
    def current_track_path(self):
        return self.current_song.track_path

    @property
    def current_track_length_us(self):
        return self.current_song.track_length_us

    def is_playing(self):
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    
    def is_paused(self):
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState

    def is_stopped(self):
        return self.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
    
    def set_volume(self, vol):
        self.audio_output.setVolume(vol)
    
    def set_position(self, pos):
        self.player.setPosition(pos)
    
    def get_volume(self):
        return self.audio_output.volume()
