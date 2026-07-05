# coding: utf-8
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QFileDialog
from PySide6.QtCore import QTimer, QThread

from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, FluentIcon, LineEdit,
    SpinBox, TextEdit, ProgressBar,
    InfoBar,
)

from ...service.downloadWorker import DownloadWorker


class DownloadPage(QFrame):
    """Interactive download page for Danbooru."""

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))
        self.window = window

        # --- Worker thread ---
        self._thread = None
        self._worker = None
        self._pollTimer = QTimer(self)
        self._pollTimer.setInterval(500)
        self._pollTimer.timeout.connect(self._pollProgress)

        # --- Build UI ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 1. Tags card
        self._buildTagsCard(layout)

        # 2. Config card
        self._buildConfigCard(layout)

        # 3. Progress card
        self._buildProgressCard(layout)

        # 4. Log card
        self._buildLogCard(layout)

    # ---- UI Builders ----

    def _buildTagsCard(self, layout):
        card = CardWidget(self)
        cardLayout = QVBoxLayout(card)

        title = StrongBodyLabel("标签设置", card)
        desc = CaptionLabel(
            "输入要搜索的标签，多个标签用空格分隔。支持 OR / NOT 语法。", card
        )

        self.tagInput = LineEdit(card)
        self.tagInput.setPlaceholderText("例如: mery_(yangmalgage) hyouka")

        cardLayout.addWidget(title)
        cardLayout.addWidget(desc)
        cardLayout.addWidget(self.tagInput)
        layout.addWidget(card)

    def _buildConfigCard(self, layout):
        card = CardWidget(self)
        cardLayout = QVBoxLayout(card)

        title = StrongBodyLabel("下载配置", card)
        cardLayout.addWidget(title)

        # Download path
        pathRow = QHBoxLayout()
        pathRow.addWidget(BodyLabel("下载路径:", card))
        self.pathInput = LineEdit(card)
        self.pathInput.setText("./downloads")
        pathRow.addWidget(self.pathInput, 1)
        self.browseBtn = PushButton("浏览...", card, icon=FluentIcon.FOLDER)
        self.browseBtn.clicked.connect(self._browsePath)
        pathRow.addWidget(self.browseBtn)
        cardLayout.addLayout(pathRow)

        # Threads config row
        threadRow = QHBoxLayout()
        threadRow.addWidget(BodyLabel("爬取线程:", card))
        self.pageThreadsBox = SpinBox(card)
        self.pageThreadsBox.setRange(1, 20)
        self.pageThreadsBox.setValue(5)
        threadRow.addWidget(self.pageThreadsBox)

        threadRow.addSpacing(24)
        threadRow.addWidget(BodyLabel("下载线程:", card))
        self.urlThreadsBox = SpinBox(card)
        self.urlThreadsBox.setRange(1, 20)
        self.urlThreadsBox.setValue(10)
        threadRow.addWidget(self.urlThreadsBox)

        threadRow.addStretch(1)
        cardLayout.addLayout(threadRow)

        # Control buttons
        btnRow = QHBoxLayout()
        self.startBtn = PrimaryPushButton("开始下载", card, icon=FluentIcon.PLAY)
        self.startBtn.clicked.connect(self._startDownload)
        self.stopBtn = PushButton("停止", card, icon=FluentIcon.CANCEL)
        self.stopBtn.clicked.connect(self._stopDownload)
        self.stopBtn.setEnabled(False)
        btnRow.addWidget(self.startBtn)
        btnRow.addWidget(self.stopBtn)
        btnRow.addStretch(1)
        cardLayout.addLayout(btnRow)

        layout.addWidget(card)

    def _buildProgressCard(self, layout):
        card = CardWidget(self)
        cardLayout = QVBoxLayout(card)

        self.progressTitle = StrongBodyLabel("就绪", card)
        self.progressBar = ProgressBar(card, useAni=True)
        self.progressBar.setRange(0, 100)
        self.progressLabel = CaptionLabel("0 / 0", card)

        cardLayout.addWidget(self.progressTitle)
        cardLayout.addWidget(self.progressBar)
        cardLayout.addWidget(self.progressLabel)
        layout.addWidget(card)

    def _buildLogCard(self, layout):
        card = CardWidget(self)
        cardLayout = QVBoxLayout(card)

        title = StrongBodyLabel("运行日志", card)
        self.logOutput = TextEdit(card)
        self.logOutput.setReadOnly(True)
        self.logOutput.setMinimumHeight(150)

        clearBtn = PushButton("清空", card, icon=FluentIcon.DELETE)
        clearBtn.clicked.connect(self.logOutput.clear)

        cardLayout.addWidget(title)
        cardLayout.addWidget(self.logOutput, 1)
        cardLayout.addWidget(clearBtn)
        layout.addWidget(card, 1)

    # ---- Actions ----

    def _browsePath(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if path:
            self.pathInput.setText(path)

    def _startDownload(self):
        tagsText = self.tagInput.text().strip()
        if not tagsText:
            InfoBar.warning(
                parent=self,
                title="",
                content="请输入至少一个标签",
            )
            return

        tags = tagsText.split()
        downloadRoot = self.pathInput.text().strip() or "./downloads"
        pageThreads = self.pageThreadsBox.value()
        urlThreads = self.urlThreadsBox.value()

        # Disable UI during download
        self.startBtn.setEnabled(False)
        self.stopBtn.setEnabled(True)
        self.tagInput.setEnabled(False)
        self.pathInput.setEnabled(False)
        self.browseBtn.setEnabled(False)
        self.pageThreadsBox.setEnabled(False)
        self.urlThreadsBox.setEnabled(False)
        self.progressBar.setValue(0)
        self.logOutput.clear()

        self._log(f"开始下载: tags={tags}, path={downloadRoot}")
        self._log(f"线程配置: 爬取={pageThreads}, 下载={urlThreads}")

        # Setup worker thread
        self._thread = QThread(self)
        self._worker = DownloadWorker()
        self._worker.moveToThread(self._thread)

        self._worker.progressUpdated.connect(self._onProgressUpdated)
        self._worker.logMessage.connect(self._log)
        self._worker.finished.connect(self._onFinished)

        self._thread.started.connect(
            lambda: self._worker.start(tags, downloadRoot, pageThreads, urlThreads)
        )
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()
        self._pollTimer.start()

    def _stopDownload(self):
        self._log("正在停止下载...")
        if self._worker:
            self._worker.cancel()

    def _pollProgress(self):
        if not self._worker:
            return
        try:
            prog = self._worker.getProgress()
            self._onProgressUpdated(
                prog["total"], prog["completed"], prog["description"]
            )
        except Exception:
            pass

    def _onProgressUpdated(self, total, completed, description):
        self.progressTitle.setText(description)
        if total > 0:
            pct = int(completed / total * 100)
            self.progressBar.setValue(pct)
            self.progressLabel.setText(f"{completed} / {total}")
        else:
            self.progressBar.setValue(0)
            self.progressLabel.setText(f"{completed} / {total}")

    def _onFinished(self, success):
        self._pollTimer.stop()
        self._cleanupThread()

        self.startBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)
        self.tagInput.setEnabled(True)
        self.pathInput.setEnabled(True)
        self.browseBtn.setEnabled(True)
        self.pageThreadsBox.setEnabled(True)
        self.urlThreadsBox.setEnabled(True)

        if success:
            self._log("下载完成！")
            InfoBar.success(
                parent=self,
                title="",
                content="下载完成",
            )
        else:
            self._log("下载已取消或出错")
            InfoBar.warning(
                parent=self,
                title="",
                content="下载已取消或出错",
            )

    def _cleanupThread(self):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None

    def _log(self, msg: str):
        self.logOutput.append(msg)
        # Auto-scroll to bottom
        scrollbar = self.logOutput.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
