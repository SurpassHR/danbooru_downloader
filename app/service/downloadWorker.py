# coding: utf-8
import sys
from PySide6.QtCore import QObject, Signal

from .downloader import DanbooruDownloader


class _StreamRedirect:
    """将 stdout/stderr 重定向到 Qt Signal，同时保留原始输出。

    按行切分文本块，过滤 tqdm 进度行（含 \r 回车符的更新行），
    每行通过 Signal 发射到 GUI 日志面板。
    """

    def __init__(self, signal_emit, original_stream):
        self._emit = signal_emit
        self._original = original_stream
        self._buffer = ""

    def write(self, text):
        self._original.write(text)
        if "\r" in text:
            self._buffer = ""
            return
        self._buffer += text
        if "\n" in self._buffer:
            lines = self._buffer.split("\n")
            self._buffer = lines[-1]
            for line in lines[:-1]:
                stripped = line.strip()
                if stripped:
                    self._emit(stripped)

    def flush(self):
        self._original.flush()


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
            fnProgress=self._emitProgress,
        )
        self._run()

    def _emitProgress(self, total: int, completed: int, description: str):
        """Thread-safe progress update via Qt Signal."""
        self.progressUpdated.emit(total, completed, description)

    def cancel(self):
        """Request cancellation."""
        if self._downloader:
            self._downloader.fnCancel()

    def getProgress(self) -> dict:
        """Get current download progress: {total, completed, description}."""
        if self._downloader:
            return self._downloader.fnGetProgress()
        return {"total": 0, "completed": 0, "description": "Idle"}

    def _run(self):
        """Execute download (runs in background thread)."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _StreamRedirect(self.logMessage.emit, old_stdout)
        sys.stderr = _StreamRedirect(self.logMessage.emit, old_stderr)

        try:
            self._downloader.fnDownload()
            progress = self._downloader.fnGetProgress()
            self.progressUpdated.emit(
                progress["total"], progress["completed"], progress["description"]
            )
            success = not self._downloader.fnIsCancelled()
            self.finished.emit(success)
        except Exception as e:
            self.logMessage.emit(f"Download error: {e}")
            self.finished.emit(False)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
