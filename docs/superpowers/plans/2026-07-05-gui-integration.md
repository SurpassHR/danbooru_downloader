# 下载器 GUI 集成实施计划

> **For agentic workers:** 使用 subagent-driven-development 或直接执行。

**目标：** 将 DanbooruDownloader 整合到 GUI，实现标签输入、配置、进度显示、启停控制的交互式下载页面。

**架构：**
- `DownloadWorker` 封装下载器在后台线程运行，通过 Signal 更新 UI
- `DownloadPage` 替代示例页面，作为主下载交互页面
- 通过 QTimer 轮询进度（下载器本身是同步的，线程池内部并发）

**Tech Stack:** PySide6, qfluentwidgets, QThread

## 全局约束

- 不要改动现有的文件头编码声明 `# coding: utf-8`
- 遵循项目命名规范：类名 PascalCase，方法 camelCase
- 新建文件放在已有分类目录中（service / view/page / widget）

---

### Task 1: 下载器增加取消支持

**Files:**
- Modify: `app/service/downloader.py`

- [ ] **Step 1: 在 `__init__` 末尾添加取消标志**

```python
# --- Cancellation Support ---
self._bCancelled = False
```

加到 `urllib3.disable_warnings(...)` 之后。

- [ ] **Step 2: 添加 `fnCancel` 方法**

在 `fnGetProgress` 之后添加：

```python
def fnCancel(self):
    """Requests cancellation of the download process."""
    self._bCancelled = True
    print("Cancellation requested...")
```

- [ ] **Step 3: 在 `fnDownload` 的每一步之间检查取消标志**

```python
def fnDownload(self):
    try:
        print("Starting download process...")
        self.dProgress["description"] = "Fetching post page URLs..."
        lsAllPostPageUrls = self._fnFetchPostPageUrls()

        if self._bCancelled:
            print("Download cancelled after fetching page URLs.")
            return

        self.dProgress["description"] = "Fetching direct image URLs..."
        dictAllImageUrls = self._fnFetchImageUrls(lsAllPostPageUrls)

        if self._bCancelled:
            print("Download cancelled after fetching image URLs.")
            return

        self.dProgress["description"] = "Downloading images..."
        self._fnDownloadImages(list(dictAllImageUrls.values()))

        if not self._bCancelled:
            print("\n--- Download Summary ---")
            print(f"Added {self.iNewPageUrlsCount} new page URLs.")
            print(f"Added {self.iNewImageUrlsCount} new image URL mappings.")
            print("Download process finished successfully.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
```

---

### Task 2: 创建 DownloadWorker

**Files:**
- Create: `app/service/downloadWorker.py`

**接口：**
- 信号: `progressUpdated(total, completed, description)`, `logMessage(msg)`, `finished(success)`
- 方法: `start(tags, downloadRoot, pageThreads, urlThreads)`, `cancel()`

- [ ] **Step 1: 创建 DownloadWorker 类**

```python
# coding: utf-8
import time
from PySide6.QtCore import QObject, Signal, QThread

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
```

---

### Task 3: 创建 DownloadPage

**Files:**
- Create: `app/view/page/downloadPage.py`

- [ ] **Step 1: 创建完整的下载页面**

```python
# coding: utf-8
import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QWidget,
    QFileDialog, QScrollArea,
)
from PySide6.QtCore import QTimer, QThread
from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, FluentIcon, LineEdit,
    SpinBox, ComboBox, TextEdit, ProgressBar,
    InfoBar, InfoBarPosition,
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
        desc = CaptionLabel("输入要搜索的标签，多个标签用空格分隔。支持 OR / NOT 语法。", card)

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

        clearBtn = PushButton("清空", card, icon=FluentIcon.CLEAR)
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
            InfoBar.warning("", "请输入至少一个标签", parent=self)
            return

        tags = tagsText.split()
        downloadRoot = self.pathInput.text().strip() or "./downloads"
        pageThreads = self.pageThreadsBox.value()
        urlThreads = self.urlThreadsBox.value()

        # Disable UI
        self.startBtn.setEnabled(False)
        self.stopBtn.setEnabled(True)
        self.tagInput.setEnabled(False)
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
        # Poll via worker reference (safe cross-thread since we only read)
        try:
            from ...service.downloader import DanbooruDownloader
            if self._worker._downloader:
                prog = self._worker._downloader.fnGetProgress()
                self._onProgressUpdated(prog["total"], prog["completed"], prog["description"])
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

        if success:
            self._log("下载完成！")
            InfoBar.success("", "下载完成", parent=self)
        else:
            self._log("下载已取消或出错")
            InfoBar.warning("", "下载已取消或出错", parent=self)

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
```

---

### Task 4: 注册到主窗口

**Files:**
- Modify: `app/view/appFluentWindow.py`

- [ ] **Step 1: 替换导入和注册**

修改导入：
```python
from ..view.page.downloadPage import DownloadPage
```

修改 `addPages`：
```python
def addPages(self) -> None:
    self.addSubInterface(
        DownloadPage("_downloadPage", self), FluentIcon.DOWNLOAD, "下载", NavigationItemPosition.SCROLL
    )
    self.addProjectMainPageHyperlink()
    self.addThemeChangingWidget()
```

- [ ] **Step 2: 修复项目主页链接**

```python
def addProjectMainPageHyperlink(self) -> None:
    def _openProjectPage() -> None:
        QDesktopServices.openUrl(QUrl("https://github.com/SurpassHR/danbooru_downloader"))

    self.navigationInterface.addWidget(
        routeKey="projectMainPageHyperlink",
        widget=NavigationAvatarWidget(
            "项目主页",
            QImage("assets/icons/icon-github.png"),
        ),
        onClick=_openProjectPage,
        position=NavigationItemPosition.BOTTOM,
    )
```

---

### Task 5: 修复 app.py 中的遗留硬编码

**Files:**
- Modify: `app/app.py`

- [ ] **Step 1: 修复窗口标题和单实例 ID**

```python
window = AppFluentWindow(window_title="Danbooru Downloader")

app = SingletonApplication(sys.argv, "DanbooruDownloader")
```

---

### Task 6: 清理示例代码（可选）

**Files:**
- Delete (optional): `app/view/page/examplePage.py`

保留 examplePage.py 作为参考，不删除。
