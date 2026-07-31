from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

KEY = "mp3qt-instance"


class SingleInstance(QObject):
    message_received = Signal(str)

    def __init__(self):
        super().__init__()
        self._server = None

    def try_acquire(self, payload=""):
        """Returns True if this is the primary instance. Otherwise sends
        `payload` to the running instance and returns False."""
        socket = QLocalSocket()
        socket.connectToServer(KEY)
        if socket.waitForConnected(200):
            socket.write((payload or "focus").encode("utf-8"))
            socket.waitForBytesWritten(200)
            socket.disconnectFromServer()
            return False

        QLocalServer.removeServer(KEY)
        self._server = QLocalServer()
        self._server.newConnection.connect(self._handle_connection)
        self._server.listen(KEY)
        return True

    def _handle_connection(self):
        conn = self._server.nextPendingConnection()
        conn.readyRead.connect(lambda: self._read(conn))

    def _read(self, conn):
        data = bytes(conn.readAll()).decode("utf-8")
        self.message_received.emit(data)
        conn.disconnectFromServer()
