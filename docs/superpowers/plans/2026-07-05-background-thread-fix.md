# 后台线程与 UI 同步修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or inline execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 修复下载器后台线程中"停止"按钮不工作的问题，消除跨线程数据竞争，清理冗余的 UI 轮询机制。

**架构改动:** 在 `_fnDownloadSingleFile` 入口处检查 `_bCancelled` 提前返回，将 `_fnDownloadImages` 的 `list(tqdm(imap_unordered))` 阻塞式消费改为带取消检测的迭代 + `pool.terminate()`；完善 `fnGetProgress()` 读取锁保护；移除 `DownloadPage` 中冗余的 `_pollTimer` 轮询，全部依赖 Qt Signal 驱动 UI 刷新。

**技术栈:** Python 3.12+, PySide6, PySide6-Fluent-Widgets, multiprocessing.pool.ThreadPool

## 全局约束

- 所有 `.py` 文件首行为 `# coding: utf-8`
- 行长 120 字符，双引号，4 空格缩进
- 方法与函数使用 `camelCase` 命名
- 修改的代码必须通过 `ruff check` 和 `ruff format`
- 不要在 `_fnDownloadSingleFile` 中引入新的第三方包或复杂依赖

---

### 任务 1: 修复下载阶段取消不生效的问题

**文件:**
- 修改: `app/service/downloader.py:113-145`（`_fnDownloadImages` 方法）
- 修改: `app/service/downloader.py:148-183`（`_fnDownloadSingleFile` 方法）

**说明:**
当前 `_fnDownloadImages` 使用 `list(tqdm(oPool.imap_unordered(...)))`，这是一个完全阻塞的调用——即使设置了 `_bCancelled = True`，也要等所有 ThreadPool 任务跑完才能返回。`_fnDownloadSingleFile` 内部也完全不检查取消标志。

修复方案：
1. `_fnDownloadSingleFile` 在下载开始前检查 `_bCancelled`，取消则立即返回
2. `_fnDownloadImages` 改为 `for result in tqdm(imap_unordered(...)):` 迭代形式，每拿到一个结果就检查一次取消标志
3. 取消时调用 `oPool.terminate()` 终止工作线程，然后 break

%-- 注意：在 Python 中，`imap_unordered` 是惰性迭代器。如果我们 break 循环，ThreadPool 的输入队列中未分发的任务就不会被分配给工作线程。但已分配给工作线程的任务会继续执行直到当前文件下载完成。调用 `terminate()` 可以立即终止所有工作线程——对于已取消的下载，.part 残留文件没有影响。

- [ ] **Step 1: 在 `_fnDownloadSingleFile` 入口添加取消检查**

在 `_fnDownloadSingleFile` 方法的最开始（函数签名之后，变量声明之前），检查 `_bCancelled`：

```python
def _fnDownloadSingleFile(self, sUrl: str):
    if self._bCancelled:
        return
    sFilename = os.path.basename(sUrl)
    # ... 后续不变
```

- [ ] **Step 2: 重构 `_fnDownloadImages` 为带取消检测的迭代**

将原来的阻塞式 `list(tqdm(...))` 替换为 for 循环迭代，每次迭代检查取消标志：

```python
def _fnDownloadImages(self, lsImageUrls: list):
    """从 URL 列表并发下载所有图片。"""
    os.makedirs(self.sImageDownloadPath, exist_ok=True)

    urls_to_download = []
    for url in lsImageUrls:
        filename = os.path.basename(url)
        filepath = os.path.join(self.sImageDownloadPath, filename)
        if not os.path.exists(filepath):
            urls_to_download.append(url)

    print(
        f"Found {len(lsImageUrls)} total images. "
        f"{len(urls_to_download)} need to be downloaded."
    )

    self.dProgress["total"] = len(urls_to_download)
    self.dProgress["completed"] = 0

    if not urls_to_download:
        return

    with ThreadPool(processes=self.iUrlFetchingThreads) as oPool:
        iterator = oPool.imap_unordered(self._fnDownloadSingleFile, urls_to_download)
        for _ in tqdm(
            iterator,
            total=len(urls_to_download),
            desc="Downloading images",
        ):
            if self._bCancelled:
                oPool.terminate()
                break
```

- [ ] **Step 3: 验证取消行为的完整性**

检查 `fnDownload` 方法中取消后的流程是否正确：

```python
def fnDownload(self):
    """启动下载流程：通过 JSON API 获取图片 URL 后下载。"""
    try:
        print("Starting download process...")
        self.dProgress["description"] = "Fetching image URLs via API..."
        lsAllFileUrls = self._fnFetchAllFileUrls()

        if self._bCancelled:          # 这个检查已经存在，保持不变
            print("Download cancelled after fetching URLs.")
            return

        self.dProgress["description"] = "Downloading images..."
        self._fnDownloadImages(lsAllFileUrls)

        if not self._bCancelled:      # 这个检查已经存在，保持不变
            print("\n--- Download Summary ---")
            print(f"Downloaded {len(lsAllFileUrls)} files.")
            print("Download process finished successfully.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
```

无需改动 `fnDownload` 方法主体——已有的 `if self._bCancelled: return` 在 URL 获取和下载两个阶段之间仍然有效；新增的检查在 `_fnDownloadImages` 内部生效。

- [ ] **Step 4: 运行 ruff 检查**

```bash
rtk ruff check app/service/downloader.py --fix
rtk ruff format app/service/downloader.py
```

预期：无报错。

---

### 任务 2: 修复 `dProgress` 跨线程读取无锁保护

**文件:**
- 修改: `app/service/downloader.py:65-71`（`fnGetProgress` 方法）

**说明:**
`dProgress` 字典在 `_fnDownloadSingleFile` 中受 `oFileLock` 保护写入，但 `fnGetProgress()` 直接被主线程调用时没有加锁读取。虽然 CPython GIL 让直接 crash 的概率极低，但还是可能读到中间状态（如 completed 更新了但 total 还没来得及设置），属于数据竞争。

修复方案：在 `fnGetProgress` 中也获取 `oFileLock`，然后返回字典的浅拷贝。

- [ ] **Step 1: 修改 `fnGetProgress` 添加读锁**

```python
def fnGetProgress(self) -> dict:
    """返回当前下载进度的快照（线程安全）。"""
    with self.oFileLock:
        return dict(self.dProgress)
```

- [ ] **Step 2: 运行 ruff 检查**

```bash
rtk ruff check app/service/downloader.py --fix
rtk ruff format app/service/downloader.py
```

预期：无报错。

---

### 任务 3: 移除 `DownloadPage` 中冗余的 `_pollTimer` 轮询

**文件:**
- 修改: `app/view/page/downloadPage.py:26-29`（`_pollTimer` 相关声明）
- 修改: `app/view/page/downloadPage.py:108-115`（`_startDownload` 中的 timer 启动）
- 删除: `app/view/page/downloadPage.py:123-130`（`_pollProgress` 方法）
- 修改: `app/view/page/downloadPage.py:145`（`_onFinished` 中的 timer 停止）

**说明:**
当前存在两条并行的进度更新路径：
1. `progressUpdated` Signal（每个文件完成时从 ThreadPool → Qt 队列 → 主线程 `_onProgressUpdated`）
2. `_pollTimer`（每 500ms 轮询 `_worker.getProgress()` → 主线程 `_onProgressUpdated`）

有了任务 2 的锁保护后，Signal 路径已经足以提供实时更新。轮询路径在 URL 获取阶段有用（因为该阶段没有 Signal 触发），但可以通过 `onProgressUpdated` Signal 在 `_run` 方法中增加一个阶段变更信号来解决。

实际上更好的方案是保留 Timer 轮询但降低优先级——因为 URL 获取阶段也需要 UI 展示 description。但如果我们让 `_run` 在 URL 获取阶段也通过 `progressUpdated` Signal 推送状态，就可以完全移除 Timer。

**替代方案（推荐：保留 Timer 但降低间隔）：**
保持 Timer 但把间隔从 500ms 降至 2000ms，作为备用回退。Signal 负责实时更新，Timer 兜底。

考虑到改动风险最小化，选择**保留 Timer 改为 2000ms**。

- [ ] **Step 1: 调整 Timer 间隔并移除冗余的 poll 方法**

```python
# 在 __init__ 中
self._pollTimer = QTimer(self)
self._pollTimer.setInterval(2000)         # 500ms → 2000ms，降低冗余刷新频率
self._pollTimer.timeout.connect(self._pollProgress)
```

保留 `_pollProgress` 方法不变，只是间隔拉长，作为 Signal 路径的备用。

- [ ] **Step 2: 运行 ruff 检查**

```bash
rtk ruff check app/view/page/downloadPage.py --fix
rtk ruff format app/view/page/downloadPage.py
```

预期：无报错。

---

### 任务 4: 验证整体链路

**说明:**
运行 GUI 应用，手动验证整个下载 + 取消流程。

- [ ] **Step 1: 启动 GUI**

```bash
cd /media/hr/Data/Codes/danbooru_downloader
source .venv/bin/activate
rtk python main.py
```

- [ ] **Step 2: 手动测试检查清单**

- [ ] 输入标签，点击"开始下载"，观察进度条和日志面板正常显示
- [ ] 在下载阶段点击"停止"，确认下载很快终止（不再等待所有文件完成）
- [ ] 确认没有新的日志行出现（之前队列中的可能还有几条，但不会太多）
- [ ] 连续快速点击"停止"不会导致应用崩溃
- [ ] 成功下载后 UI 按钮状态恢复正常（停止禁用、开始启用）
- [ ] 取消后 UI 按钮状态恢复正常

- [ ] **Step 3: 提交代码**

```bash
git add -A
git commit -m "fix: make cancel immediately terminate thread pool during download

- Check _bCancelled in _fnDownloadSingleFile entry for early return
- Replace list(tqdm(imap_unordered)) with cancellable for-loop + pool.terminate()
- Add thread-safe lock acquisition in fnGetProgress() for race-condition-free reads
- Reduce poll timer interval from 500ms to 2000ms to reduce redundant UI updates"
```
