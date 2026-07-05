# coding: utf-8
from PySide6.QtCore import QObject, Signal

from .downloader import DanbooruDownloader


class DownloadWorker(QObject):
    """Runs DanbooruDownloader in a background thread with progress updates."""

    progressUpdated = Signal(int, int, str)   # total, completed, description
    logMessage = Signal(str)                  # log line
    finished = Signal(bool)                   # success

    def __init__(self, parent=None):
        super().__init__(parent)
        self._downloader = None

    def start(self, tags: list, downloadRoot: str, pageThreads: int, urlThreads: int):
        """Start the download in a background thread."""
        self._downloader = DanbooruDownloader(
            lsTags=tags,
            sDownloadRoot=downloadRoot,
            iPageThreads=pageThreads,
            iUrlThreads=urlThreads,
        )
        self._run()

    def cancel(self):
        """Request cancellation."""
        if self._downloader:
            self._downloader.fnCancel()

    def _run(self):
        """Execute download (runs in background thread)."""
        try:
            self._downloader.fnDownload()
            progress = self._downloader.fnGetProgress()
            self.progressUpdated.emit(
                progress["total"], progress["completed"], progress["description"]
            )
            success = not self._downloader._bCancelled
            self.finished.emit(success)
        except Exception as e:
            self.logMessage.emit(f"Download error: {e}")
            self.finished.emit(False)
