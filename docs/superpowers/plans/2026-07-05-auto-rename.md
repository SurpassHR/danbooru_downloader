# 下载文件自动重命名 — 实现计划

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 在 Danbooru Downloader 中实现下载文件的自动重命名，支持数字序号和占位符模板两种模式。

**架构:** 后端在 `DanbooruDownloader` 中新增重命名逻辑（`_fnComputeNewFilename` + 标签解析），前端新增独立设置页面（`SettingsPage`）及下载页状态行。配置通过 `config.json` 持久化，默认关闭以保证向后兼容。

**涉及文件:**
- modify `app/service/downloader.py` — 核心重命名逻辑
- modify `app/service/downloadWorker.py` — 透传配置
- create `app/view/page/settingsPage.py` — 设置页面
- modify `app/view/page/downloadPage.py` — 状态行
- modify `app/view/appFluentWindow.py` — 注册导航

---

### Task 1: 下载器后端 — 核心重命名逻辑

**Files:**
- Modify: `app/service/downloader.py`

**变更范围:**
1. `__init__` 新增 `dRenameConfig: dict = None` 参数
2. `_fnFetchAllFileUrls()` → `_fnFetchAllPosts()` 返回 `[(url, post_data), ...]` 并按 post_id 升序排序
3. `_fnDownloadImages()` 改为接收 post 列表，传递索引
4. `_fnDownloadSingleFile()` 接收 `(index, total, url, post)` 元组，下载成功后调用重命名
5. 新增 `_fnComputeNewFilename()` — 根据模板/post 元数据生成新文件名
6. 新增 `_fnExtractTag()` / `_fnGetShortTags()` — 标签解析工具

- [ ] **Step 1: 修改 `__init__` — 新增 dRenameConfig 参数**

```python
def __init__(
    self,
    lsTags: list,
    sDownloadRoot: str = "./downloads",
    iPageThreads: int = 3,
    iUrlThreads: int = 3,
    fnProgress=None,
    dRenameConfig: dict = None,
):
    # ... existing code ...
    self.dRenameConfig = dRenameConfig or {}
```

- [ ] **Step 2: 新增标签解析工具方法**

加到 `DanbooruDownloader` 类中（建议在 `_fnCreateSession` 之后）：

```python
@staticmethod
def _fnExtractTag(tag_string: str, namespace: str) -> str:
    """从 Danbooru tag_string 中提取指定命名空间的第一个标签值。

    Danbooru tag_string 格式: "artist:yangmalgage character:chitanda_eru hyouka"
    """
    if not tag_string or not namespace:
        return ""
    ns_prefix = f"{namespace}:"
    for tag in tag_string.split():
        if tag.startswith(ns_prefix):
            return tag[len(ns_prefix):]
    return ""

@staticmethod
def _fnGetShortTags(tag_string: str, count: int) -> str:
    """取前 N 个普通标签（无命名空间），下划线连接。"""
    if not tag_string or count <= 0:
        return ""
    general = [tag for tag in tag_string.split() if ":" not in tag]
    return "_".join(general[:count])
```

- [ ] **Step 3: 新增 `_fnComputeNewFilename()`**

```python
def _fnComputeNewFilename(self, post: dict, index: int, total: int, original_ext: str) -> str | None:
    """根据重命名配置生成新文件名。返回 None 表示应保留原始文件名。"""
    rc = self.dRenameConfig
    if not rc.get("enabled"):
        return None

    mode = rc.get("mode", "pattern")

    if mode == "sequence":
        digits = len(str(total))
        prefix = rc.get("prefix", "")
        return f"{prefix}{index:0{digits}d}{original_ext}"

    # ---- Pattern mode ----
    pattern = rc.get("pattern", "{post_id}")

    # 预处理 {ext}: 如果在模板中显式使用了，替换后不再自动追加
    has_ext_in_pattern = "{ext}" in pattern
    if has_ext_in_pattern:
        pattern = pattern.replace("{ext}", original_ext)

    replacements = {
        "{post_id}": str(post.get("id", "")),
        "{artist}": self._fnExtractTag(post.get("tag_string", ""), "artist"),
        "{character}": self._fnExtractTag(post.get("tag_string", ""), "character"),
        "{copyright}": self._fnExtractTag(post.get("tag_string", ""), "copyright"),
        "{rating}": post.get("rating", ""),
        "{md5}": post.get("md5", ""),
        "{date}": (post.get("created_at", "")[:10] if post.get("created_at") else ""),
        "{tags_short}": self._fnGetShortTags(post.get("tag_string", ""), rc.get("tags_short_count", 3)),
        "{search_tags}": "_".join(self.lsTags),
    }

    basename = pattern
    for placeholder, value in replacements.items():
        if value:
            basename = basename.replace(placeholder, value)

    # 检查未替换的占位符 → 字段缺失 → 放弃重命名
    import re
    remaining = re.findall(r"\{\w+\}", basename)
    if remaining:
        return None

    # 自动追加扩展名
    if not has_ext_in_pattern:
        basename += original_ext

    return basename
```

- [ ] **Step 4: 修改 `_fnFetchAllFileUrls()` → `_fnFetchAllPosts()`**

替换原方法名和内容：

```python
def _fnFetchAllPosts(self) -> list:
    """通过 JSON API 获取所有帖子，返回 [(file_url, post_data), ...] 按 post_id 升序。"""
    all_posts = []
    page = 1
    limit = 200

    while True:
        api_url = (
            f"{self.sBaseUrl}/posts.json"
            f"?tags={'+'.join(self.lsTags)}"
            f"&page={page}&limit={limit}"
        )
        try:
            resp = self.oSession.get(api_url, verify=False, timeout=20)
            resp.raise_for_status()
            posts = resp.json()
        except Exception as e:
            print(f"API request failed (page {page}): {e}")
            break

        if not posts or not isinstance(posts, list):
            break

        for post in posts:
            file_url = post.get("file_url")
            if file_url:
                all_posts.append((file_url, post))

        print(f"  Fetched page {page}: {len(posts)} posts, {len(all_posts)} total URLs")

        if self._bCancelled:
            break
        if len(posts) < limit:
            break

        page += 1
        time.sleep(1.0)

    all_posts.sort(key=lambda x: x[1].get("id", 0))
    print(f"Fetched {len(all_posts)} image URLs in total.")
    return all_posts
```

- [ ] **Step 5: 修改 `fnDownload()` — 调用 `_fnFetchAllPosts()`**

```python
def fnDownload(self):
    try:
        print("Starting download process...")
        self.dProgress["description"] = "Fetching image URLs via API..."
        lsAllPosts = self._fnFetchAllPosts()

        if self._bCancelled:
            print("Download cancelled after fetching URLs.")
            return

        self.dProgress["description"] = "Downloading images..."
        self._fnDownloadImages(lsAllPosts)

        if not self._bCancelled:
            print("\n--- Download Summary ---")
            print(f"Downloaded {len(lsAllPosts)} files.")
            print("Download process finished successfully.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
```

- [ ] **Step 6: 修改 `_fnDownloadImages()` — 传递索引 + post 数据**

```python
def _fnDownloadImages(self, lsPosts: list):
    """从 post 列表下载图片，支持重命名。lsPosts = [(file_url, post_data), ...]"""
    os.makedirs(self.sImageDownloadPath, exist_ok=True)

    total_fetched = len(lsPosts)
    posts_to_download = []

    for index, (file_url, post) in enumerate(lsPosts):
        filename = os.path.basename(file_url)
        filepath = os.path.join(self.sImageDownloadPath, filename)
        if not os.path.exists(filepath):
            posts_to_download.append((index, total_fetched, file_url, post))

    print(
        f"Found {total_fetched} total images. "
        f"{len(posts_to_download)} need to be downloaded."
    )

    self.dProgress["total"] = len(posts_to_download)
    self.dProgress["completed"] = 0

    if not posts_to_download:
        return

    with ThreadPool(processes=self.iUrlFetchingThreads) as oPool:
        it = oPool.imap_unordered(self._fnDownloadSingleFile, posts_to_download)
        for _ in tqdm(it, total=len(posts_to_download), desc="Downloading images"):
            if self._bCancelled:
                oPool.terminate()
                break
```

- [ ] **Step 7: 修改 `_fnDownloadSingleFile()` — 下载后重命名**

替换原方法。核心变更：解包 `(index, total_count, sUrl, post)`，下载成功后调用重命名：

```python
def _fnDownloadSingleFile(self, args):
    """下载单个文件。args = (index, total_count, file_url, post)"""
    index, total_count, sUrl, post = args
    if self._bCancelled:
        return

    sFilename = os.path.basename(sUrl)
    sFilepath = os.path.join(self.sImageDownloadPath, sFilename)
    sTempFilepath = sFilepath + ".part"
    max_retries = 3
    success = False

    for attempt in range(max_retries):
        try:
            dHeaders = {}
            sMode = "wb"
            iStartByte = 0

            if os.path.exists(sTempFilepath):
                iStartByte = os.path.getsize(sTempFilepath)
                dHeaders["Range"] = f"bytes={iStartByte}-"
                sMode = "ab"

            oResponse = self.oSession.get(
                sUrl, stream=True, verify=False, timeout=30, headers=dHeaders
            )

            if oResponse.status_code == 429:
                wait = 2 ** (attempt + 2)
                print(f"  429 rate limited, waiting {wait}s: {sFilename}")
                time.sleep(wait)
                continue

            oResponse.raise_for_status()

            if oResponse.status_code == 200 and iStartByte > 0:
                iStartByte = 0
                sMode = "wb"

            with open(sTempFilepath, sMode) as f:
                for chunk in oResponse.iter_content(8192):
                    if chunk:
                        f.write(chunk)

            os.rename(sTempFilepath, sFilepath)
            success = True
            break

        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 2)
                print(f"  Error, retrying in {wait}s: {sFilename} - {e}")
                time.sleep(wait)
            else:
                print(f"Failed after {max_retries} retries: {sUrl} - {e}")

    if success:
        # 重命名（序号模式下 index+1 转为 1-based）
        original_ext = os.path.splitext(sFilename)[1]
        new_name = self._fnComputeNewFilename(post, index + 1, total_count, original_ext)
        if new_name:
            new_path = os.path.join(self.sImageDownloadPath, new_name)
            if new_path != sFilepath:
                if os.path.exists(new_path):
                    base, ext = os.path.splitext(new_name)
                    counter = 1
                    while os.path.exists(
                        os.path.join(self.sImageDownloadPath, f"{base}_{counter}{ext}")
                    ):
                        counter += 1
                    new_path = os.path.join(self.sImageDownloadPath, f"{base}_{counter}{ext}")
                try:
                    os.rename(sFilepath, new_path)
                    print(f"  Renamed: {sFilename} → {os.path.basename(new_path)}")
                except OSError as e:
                    print(f"  Rename failed: {sFilename} - {e}")

        with self.oFileLock:
            self.dProgress["completed"] += 1
            if self._fnProgress:
                self._fnProgress(
                    self.dProgress["total"],
                    self.dProgress["completed"],
                    self.dProgress["description"],
                )

    time.sleep(0.3)
```

- [ ] **Step 8: 更新 `__main__` CLI 入口**

保持原样即可或在 `DanbooruDownloader()` 调用添加 `dRenameConfig=None`（已有默认值无需改动）。

- [ ] **Step 9: 验证 Ruff 格式**

```bash
cd /media/hr/Data/Codes/danbooru_downloader && source .venv/bin/activate && ruff check app/service/downloader.py --fix && ruff format app/service/downloader.py
```

---

### Task 2: DownloadWorker 透传

**Files:**
- Modify: `app/service/downloadWorker.py`

- [ ] **Step 1: 修改 `start()` 方法签名 — 新增 renameConfig 参数**

```python
def start(self, tags: list, downloadRoot: str, pageThreads: int, urlThreads: int, renameConfig: dict = None):
    self._downloader = DanbooruDownloader(
        lsTags=tags,
        sDownloadRoot=downloadRoot,
        iPageThreads=pageThreads,
        iUrlThreads=urlThreads,
        fnProgress=self._emitProgress,
        dRenameConfig=renameConfig,
    )
    self._run()
```

- [ ] **Step 2: 验证 Ruff 格式**

```bash
ruff check app/service/downloadWorker.py --fix && ruff format app/service/downloadWorker.py
```

---

### Task 3: 设置页面

**Files:**
- Create: `app/view/page/settingsPage.py`

- [ ] **Step 1: 创建 SettingsPage**

`app/view/page/settingsPage.py`:

```python
# coding: utf-8
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QButtonGroup, QRadioButton, QLabel,
)
from PySide6.QtCore import Qt

from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    SwitchButton, LineEdit, SpinBox, FluentIcon,
    InfoBar,
)

from ...common.configLoader import getConfig, setConfig


class SettingsPage(QFrame):
    """应用设置页面。"""

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))
        self.window = window
        self._buildUI()
        self._loadConfig()

    def _buildUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._buildRenameCard(layout)
        layout.addStretch(1)

    def _buildRenameCard(self, layout):
        card = CardWidget(self)
        cardLayout = QVBoxLayout(card)

        title = StrongBodyLabel("文件命名", card)
        cardLayout.addWidget(title)

        # 启用开关
        enableRow = QHBoxLayout()
        enableRow.addWidget(BodyLabel("启用重命名:", card))
        self.renameSwitch = SwitchButton(card)
        self.renameSwitch.checkedChanged.connect(self._onConfigChanged)
        enableRow.addWidget(self.renameSwitch)
        enableRow.addStretch(1)
        cardLayout.addLayout(enableRow)

        cardLayout.addSpacing(8)

        # 模式选择
        modeLabel = StrongBodyLabel("模式:", card)
        cardLayout.addWidget(modeLabel)

        self.modeGroup = QButtonGroup(self)
        self.modeSeq = QRadioButton("数字序号", card)
        self.modePattern = QRadioButton("模板", card)
        self.modeGroup.addButton(self.modeSeq, 0)
        self.modeGroup.addButton(self.modePattern, 1)
        self.modeGroup.buttonClicked.connect(self._onModeChanged)
        modeRow = QHBoxLayout()
        modeRow.addWidget(self.modeSeq)
        modeRow.addWidget(self.modePattern)
        modeRow.addStretch(1)
        cardLayout.addLayout(modeRow)

        cardLayout.addSpacing(8)

        # 序号模式控件
        self.seqWidget = QFrame(self)
        seqLayout = QHBoxLayout(self.seqWidget)
        seqLayout.setContentsMargins(0, 0, 0, 0)
        seqLayout.addWidget(BodyLabel("前缀:", self.seqWidget))
        self.prefixInput = LineEdit(self.seqWidget)
        self.prefixInput.setPlaceholderText("例如: danbooru_")
        self.prefixInput.setText("danbooru_")
        self.prefixInput.textChanged.connect(self._updatePreview)
        seqLayout.addWidget(self.prefixInput, 1)
        seqLayout.addWidget(BodyLabel("  例: danbooru_001.jpg", self.seqWidget))
        cardLayout.addWidget(self.seqWidget)

        # 模板模式控件
        self.patternWidget = QFrame(self)
        patternLayout = QVBoxLayout(self.patternWidget)
        patternLayout.setContentsMargins(0, 0, 0, 0)

        patternRow = QHBoxLayout()
        patternRow.addWidget(BodyLabel("模板:", self.patternWidget))
        self.patternInput = LineEdit(self.patternWidget)
        self.patternInput.setPlaceholderText(
            "例如: {post_id}_{artist}_{character}_{tags_short}_{rating}"
        )
        self.patternInput.setText("{post_id}_{artist}_{character}_{tags_short}_{rating}")
        self.patternInput.textChanged.connect(self._updatePreview)
        patternRow.addWidget(self.patternInput, 1)
        patternLayout.addLayout(patternRow)

        tagsCountRow = QHBoxLayout()
        tagsCountRow.addWidget(BodyLabel("{tags_short} 标签数:", self.patternWidget))
        self.tagsCountBox = SpinBox(self.patternWidget)
        self.tagsCountBox.setRange(1, 20)
        self.tagsCountBox.setValue(3)
        self.tagsCountBox.valueChanged.connect(self._updatePreview)
        tagsCountRow.addWidget(self.tagsCountBox)
        tagsCountRow.addStretch(1)
        patternLayout.addLayout(tagsCountRow)

        cardLayout.addWidget(self.patternWidget)

        cardLayout.addSpacing(8)

        # 预览
        previewLabel = StrongBodyLabel("预览:", card)
        cardLayout.addWidget(previewLabel)
        self.previewText = CaptionLabel("(暂未启用)", card)
        cardLayout.addWidget(self.previewText)

        cardLayout.addSpacing(8)

        # 可用占位符参考
        hintCard = CardWidget(self)
        hintLayout = QVBoxLayout(hintCard)
        hintTitle = CaptionLabel("可用占位符", hintCard)
        hintLayout.addWidget(hintTitle)
        hintText = BodyLabel(
            "{post_id}  {artist}  {character}  {copyright}  {rating}  "
            "{md5}  {date}  {tags_short}  {search_tags}  {ext}",
            hintCard,
        )
        hintText.setWordWrap(True)
        hintLayout.addWidget(hintText)

        cardLayout.addWidget(hintCard)

        layout.addWidget(card)

        # 初始状态: 显示序号模式
        self.modeSeq.setChecked(True)
        self._onModeChanged()

    def _onModeChanged(self):
        """切换序号/模板时显示/隐藏对应控件。"""
        isSeq = self.modeGroup.checkedId() == 0
        self.seqWidget.setVisible(isSeq)
        self.patternWidget.setVisible(not isSeq)
        self._updatePreview()

    def _onConfigChanged(self):
        self._updatePreview()

    def _updatePreview(self):
        """根据当前配置生成预览文件名。"""
        if not self.renameSwitch.isChecked():
            self.previewText.setText("(已禁用)")
            return

        isSeq = self.modeGroup.checkedId() == 0

        if isSeq:
            prefix = self.prefixInput.text().strip()
            self.previewText.setText(f"{prefix}001.jpg  (自动按总数决定位数)")
        else:
            pattern = self.patternInput.text().strip()
            if not pattern:
                self.previewText.setText("(请输入模板)")
                return
            # 模拟预览
            preview = pattern
            demo = {
                "{post_id}": "12345678",
                "{artist}": "yangmalgage",
                "{character}": "chitanda_eru",
                "{copyright}": "hyouka",
                "{rating}": "s",
                "{md5}": "abc123def",
                "{date}": "2025-06-30",
                "{tags_short}": "hyouka_mery_highres",
                "{search_tags}": "mery_hyouka",
                "{ext}": ".jpg",
            }
            for key, val in demo.items():
                preview = preview.replace(key, val)
            if "{ext}" not in pattern:
                preview += ".jpg"
            self.previewText.setText(preview)

    def _loadConfig(self):
        """从 config.json 加载设置。"""
        enabled = getConfig("settings.rename_enabled", False)
        self.renameSwitch.setChecked(enabled)

        mode = getConfig("settings.rename_mode", "pattern")
        if mode == "sequence":
            self.modeSeq.setChecked(True)
        else:
            self.modePattern.setChecked(True)

        prefix = getConfig("settings.rename_prefix", "danbooru_")
        self.prefixInput.setText(prefix)

        pattern = getConfig(
            "settings.rename_pattern",
            "{post_id}_{artist}_{character}_{tags_short}_{rating}",
        )
        self.patternInput.setText(pattern)

        tagsCount = getConfig("settings.rename_tags_short_count", 3)
        self.tagsCountBox.setValue(tagsCount)

        self._onModeChanged()

    def _saveConfig(self):
        """保存设置到 config.json。"""
        setConfig("settings.rename_enabled", self.renameSwitch.isChecked())
        setConfig("settings.rename_mode", "sequence" if self.modeGroup.checkedId() == 0 else "pattern")
        setConfig("settings.rename_prefix", self.prefixInput.text().strip())
        setConfig("settings.rename_pattern", self.patternInput.text().strip())
        setConfig("settings.rename_tags_short_count", self.tagsCountBox.value())

        InfoBar.success(parent=self, title="", content="设置已保存")

    def hideEvent(self, event):
        """页面隐藏时自动保存。"""
        self._saveConfig()
        super().hideEvent(event)
```

- [ ] **Step 2: 验证 Ruff 格式**

```bash
ruff check app/view/page/settingsPage.py --fix && ruff format app/view/page/settingsPage.py
```

---

### Task 4: 注册导航 + 下载页状态行

**Files:**
- Modify: `app/view/appFluentWindow.py`
- Modify: `app/view/page/downloadPage.py`

- [ ] **Step 1: 修改 `appFluentWindow.py` — 注册设置页面**

在 import 段添加:

```python
from ..view.page.settingsPage import SettingsPage
```

在 `addPages()` 中添加:

```python
def addPages(self) -> None:
    self.addSubInterface(
        DownloadPage("_downloadPage", self),
        FluentIcon.DOWNLOAD, "下载", NavigationItemPosition.SCROLL,
    )
    self.addSubInterface(
        SettingsPage("_settingsPage", self),
        FluentIcon.SETTING, "设置", NavigationItemPosition.SCROLL,
    )
    self.addProjectMainPageHyperlink()
    self.addThemeChangingWidget()
```

可选：添加一个 `switchToSettings()` 方法供下载页跳转:

```python
def switchToSettings(self):
    """导航到设置页面。"""
    nav_item = self.navigationInterface.widget("_settingsPage")
    if nav_item:
        nav_item.click()
```

- [ ] **Step 2: 修改 `downloadPage.py` — 添加命名状态行**

在 `_buildConfigCard()` 的按钮行之前（或之后）添加状态行：

```python
def _buildConfigCard(self, layout):
    # ... existing code ...

    # ---- 在 btnRow 之前或之后加入命名状态行 ----
    renameRow = QHBoxLayout()
    renameRow.addWidget(BodyLabel("命名:", card))
    self.renameStatus = BodyLabel("", card)
    renameRow.addWidget(self.renameStatus)

    self.settingsBtn = PushButton("设置", card, icon=FluentIcon.SETTING)
    self.settingsBtn.clicked.connect(self._openSettings)
    renameRow.addWidget(self.settingsBtn)
    renameRow.addStretch(1)
    cardLayout.addLayout(renameRow)
```

在类中新增 `_openSettings` 和 `_updateRenameStatus` 方法:

```python
def _openSettings(self):
    """打开设置页面。"""
    self.window.switchToSettings()

def _updateRenameStatus(self):
    """从 config 读取重命名状态并更新显示。"""
    from ...common.configLoader import getConfig
    enabled = getConfig("settings.rename_enabled", False)
    if not enabled:
        self.renameStatus.setText("未启用")
        return
    mode = getConfig("settings.rename_mode", "pattern")
    if mode == "sequence":
        prefix = getConfig("settings.rename_prefix", "danbooru_")
        self.renameStatus.setText(f"序号 - 前缀: {prefix}")
    else:
        pattern = getConfig("settings.rename_pattern", "{post_id}_{artist}_...")
        self.renameStatus.setText(f"模板 - {pattern}")
```

在 `_restoreSavedState()` 中调用 `_updateRenameStatus()`:

```python
def _restoreSavedState(self):
    # ... existing code ...
    self._updateRenameStatus()
```

在 `hideEvent` 中也更新（当从设置页返回时刷新）:

```python
def showEvent(self, event):
    """页面显示时刷新命名状态（可能从设置页返回）。"""
    self._updateRenameStatus()
    super().showEvent(event)
```

- [ ] **Step 3: 验证 Ruff 格式**

```bash
ruff check app/view/appFluentWindow.py app/view/page/downloadPage.py --fix && ruff format app/view/appFluentWindow.py app/view/page/downloadPage.py
```

---

### Task 5: 集成验证

- [ ] **Step 1: 确保 `_openSettings` 正常工作**

在 `appFluentWindow.py` 中, `switchToSettings` 通过触发导航按钮实现页面跳转:

```python
def switchToSettings(self):
    """导航到设置页面。"""
    nav_item = self.navigationInterface.widget("_settingsPage")
    if nav_item:
        nav_item.click()
```

- [ ] **Step 2: 运行 GUI 验证**

```bash
cd /media/hr/Data/Codes/danbooru_downloader && source .venv/bin/activate && python main.py
```

验证清单:
1. 导航栏是否有"设置"入口，点击可切换
2. 设置页开关、模式切换、输入框交互是否正常
3. 预览是否随配置实时更新
4. 下载页面"命名"状态行是否显示当前配置
5. 切换设置页 → 下载页，状态行是否刷新
6. 关闭设置页时配置是否自动保存
7. 重新打开设置页，上一次的配置是否恢复
8. 执行一次下载，检查文件是否按配置重命名
9. 禁用重命名后下载，文件是否保留原始文件名
10. 模板中某字段缺失时是否保留原始文件名
