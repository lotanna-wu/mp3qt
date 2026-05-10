from PySide6.QtDBus import QDBusAbstractAdaptor
from PySide6.QtCore import Slot, Property, ClassInfo


@ClassInfo(**{
    "D-Bus Interface": "org.mpris.MediaPlayer2",
    "D-Bus Introspection": """
        <interface name="org.mpris.MediaPlayer2">
            <property name="CanQuit" type="b" access="read"/>
            <property name="CanRaise" type="b" access="read"/>
            <property name="HasTrackList" type="b" access="read"/>
            <property name="Identity" type="s" access="read"/>
            <property name="DesktopEntry" type="s" access="read"/>
            <property name="SupportedUriSchemes" type="as" access="read"/>
            <property name="SupportedMimeTypes" type="as" access="read"/>
        </interface>
    """
})
class MprisRootAdaptor(QDBusAbstractAdaptor):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAutoRelaySignals(True)

    @Property(bool)
    def CanQuit(self):
        return False

    @Property(bool)
    def CanRaise(self):
        return False

    @Property(bool)
    def HasTrackList(self):
        return False

    @Property(str)
    def Identity(self):
        return "MP3 Qt"

    @Property(str)
    def DesktopEntry(self):
        return "mp3qt"

    @Property(list)
    def SupportedUriSchemes(self):
        return ["file"]

    @Property(list)
    def SupportedMimeTypes(self):
        return ["audio/mpeg"]


@ClassInfo(**{
    "D-Bus Interface": "org.mpris.MediaPlayer2.Player",
    "D-Bus Introspection": """
        <interface name="org.mpris.MediaPlayer2.Player">
            <method name="Next"/>
            <method name="Previous"/>
            <method name="Play"/>
            <method name="Pause"/>
            <method name="PlayPause"/>
            <property name="PlaybackStatus" type="s" access="read"/>
            <property name="Metadata" type="a{sv}" access="read"/>
            <property name="CanControl" type="b" access="read"/>
            <property name="CanGoNext" type="b" access="read"/>
            <property name="CanGoPrevious" type="b" access="read"/>
            <property name="CanPlay" type="b" access="read"/>
            <property name="CanPause" type="b" access="read"/>
            <property name="CanSeek" type="b" access="read"/>
        </interface>
    """
})
class MprisPlayerAdaptor(QDBusAbstractAdaptor):
    def __init__(self, parent, window):
        super().__init__(parent)
        self.setAutoRelaySignals(True)
        self._window = window

    @Property(str)
    def PlaybackStatus(self):
        if self._window.is_paused:
            return "Paused"
        elif self._window.is_playing:
            return "Playing"
        return "Stopped"

    @Property("QVariantMap")
    def Metadata(self):
        return self._window.get_mpris_metadata()

    @Property(bool)
    def CanControl(self):
        return True

    @Property(bool)
    def CanGoNext(self):
        return self._window.can_go_next()

    @Property(bool)
    def CanGoPrevious(self):
        return self._window.can_go_previous()

    @Property(bool)
    def CanPlay(self):
        return self._window.can_play()

    @Property(bool)
    def CanPause(self):
        return self._window.can_pause()

    @Property(bool)
    def CanSeek(self):
        return False

    @Slot()
    def PlayPause(self):
        self._window.toggle_play()

    @Slot()
    def Next(self):
        self._window.next_from_mpris()

    @Slot()
    def Previous(self):
        self._window.previous_from_mpris()

    @Slot()
    def Play(self):
        self._window.play()

    @Slot()
    def Pause(self):
        self._window.pause()
