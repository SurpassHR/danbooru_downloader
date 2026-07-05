# 下载文件自动重命名功能设计文档

> 日期: 2026-07-05
> 状态: 草案

---

## 1. 概述

Danbooru Downloader 下载的图片默认使用 Danbooru 服务器返回的原始文件名（如 `123456789.jpg`），该文件名无明显语义，不便管理和检索。

本功能提供两种重命名模式，允许用户自定义下载后的文件名格式。

---

## 2. 两种重命名模式

### 2.1 数字序号模式

将下载的文件按 `post_id` 升序编号，格式为 `{前缀}{序号}.{扩展名}`。

- **前缀**: 用户自定义，例如 `danbooru_`
- **序号**: 自动根据文件总数决定位数，例如 100 个文件则生成 3 位序号 `001`‑`100`
- **排序**: 按 `post_id` 升序确定编号
- **示例**: `danbooru_001.jpg`, `danbooru_002.jpg`

### 2.2 占位符模板模式

用户通过模板字符串定义文件名格式，系统从 Danbooru API 返回的 post 元数据中提取对应字段填充。

- **模板**: 包含占位符的字符串，例如 `{post_id}_{artist}_{character}`
- **分隔符**: 用户自由定义（下划线、连字符、空格等）
- **示例**: `12345678_yangmalgage_chitanda_eru_hyouka_s.jpg`

---

## 3. 可用占位符

基于 Danbooru JSON API (`/posts.json`) 返回的 post 数据:

| 占位符 | 数据来源 | 说明 | 示例 |
|--------|----------|------|------|
| `{post_id}` | `post.id` | 帖子 ID | `12345678` |
| `{artist}` | 标签中首个 `artist:` 命名空间的值 | 画师 | `yangmalgage` |
| `{character}` | 标签中首个 `character:` 命名空间的值 | 角色 | `chitanda_eru` |
| `{copyright}` | 标签中首个 `copyright:` 命名空间的值 | 作品/系列 | `hyouka` |
| `{tags_short}` | 前 N 个普通标签（不含命名空间），下划线连接 | 简短标签 | `mery_chitanda` |
| `{rating}` | `post.rating` | 分级 | `s` / `q` / `e` |
| `{md5}` | `post.md5` | 文件 MD5 | `abc123def` |
| `{date}` | `post.created_at` 的日期部分 | 上传日期 | `2025-06-30` |
| `{ext}` | 原始文件扩展名 | 模板中可省略，系统自动追加 | `.jpg` |
| `{search_tags}` | 用户输入的搜索标签，下划线连接 | 搜索标签 | `mery_hyouka` |

> **`{ext}` 自动追加规则**:
> - 系统始终**自动追加**原始文件的扩展名到模板生成的 basename 末尾
> - 用户**无需**在模板中包含 `{ext}`，即使不写也会自动追加
> - `{ext}` 占位符作为**冗余兼容**存在（如用户希望明确位置时使用）
> - **示例**: 模板 `{post_id}_{artist}` + 原始文件 `123456789.jpg` → `12345678_artistname.jpg`


**`{tags_short}` 说明**: 仅取普通标签（无命名空间前缀），避免与 `{artist}`、`{character}` 等专用字段重复。标签数量可通过配置项 `rename_tags_short_count` 调节，默认 3 个。

---

## 4. 空白/缺失字段处理

模板中任一占位符解析后为空值（如帖子没有 `artist:` 标签导致 `{artist}` 为空）时:
1. **放弃重命名**: 保留原始文件名（Danbooru 服务器返回的文件名，如 `123456789.jpg`）
2. **日志记录**: 输出 `[重命名跳过] {原文件名} → (保留原文件名，缺少字段: artist)`

> `{ext}` 不受此规则影响——每个文件都有扩展名，始终为非空值。


此策略避免生成无意义的文件名（如 `__chitanda_eru.jpg` 或 `.jpg`）。

---

## 5. UI 设计

### 5.1 导航栏变更

在导航栏新增「设置」入口:

```
导航栏:
  📥 下载           ← 已有
  ⚙️ 设置           ← 新增（SCROLL 区域）
  ─────────
  🏠 项目主页
  🌗 主题切换
```

### 5.2 设置页面（SettingsPage）

**文件路径**: `app/view/page/settingsPage.py`  
**父类**: `QFrame`（与 `DownloadPage` 一致）

```
┌─ 设置 ─────────────────────────────────────────┐
│                                                 │
│ ┌─ 文件命名 ──────────────────────────────────┐ │
│ │  ■ 启用重命名       [Switch]                │ │
│ │                                             │ │
│ │  模式:                                      │ │
│ │    ● 数字序号  ○ 模板                       │ │
│ │                                             │ │
│ │  [序号模式]                                 │ │
│ │    前缀: [danbooru_                  ]      │ │
│ │    例: danbooru_001.jpg                     │ │
│ │                                             │ │
│ │  [模板模式]                                  │ │
│ │    模板: [{post_id}_{artist}_{tags_short}]  │ │
│ │    {tags_short} 标签数: [3]                 │ │
│ │    例: 123456_yangmalgage_mery_chitanda.jpg │ │
│ │                                             │ │
│ │  ┌─── 可用占位符 ──────────────────────────┐ │ │
│ │  │ {post_id}  {artist}  {character}        │ │ │
│ │  │ {copyright}  {rating}  {md5}  {date}   │ │ │
│ │  │ {tags_short}  {search_tags}  {ext}     │ │ │
│ │  └─────────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────┘ │
│                                                 │
│ ── 后续更多设置项可在此页追加 ──                 │
└─────────────────────────────────────────────────┘
```

#### 控件说明:

| 控件 | 类型 | 作用 |
|------|------|------|
| 启用重命名 | Switch | 全局开关，关闭时下载页面不显示重命名状态 |
| 模式切换 | SegmentedButton | 序号 / 模板 二选一 |
| 前缀输入框 | LineEdit | 序号模式下的文件前缀 |
| 模板输入框 | LineEdit | 模板模式下的占位符模板 |
| 标签数 | SpinBox | `{tags_short}` 取前 N 个标签，范围 1-20 |
| 预览文本 | BodyLabel | 根据当前配置实时生成示例文件名 |
| 占位符提示 | Card + 标签列表 | 展示所有可用占位符供用户参考 |

### 5.3 下载页面状态行

在下载配置卡片底部新增一行只读状态，不占主要空间:

```
▶ 下载配置
    下载路径: [.......................]
    线程: ...
    命名: 已启用 - 模板模式: {post_id}_{artist}_...  [⚙️ 设置]
    [开始下载]  [停止]
```

- 点击 `⚙️ 设置` 按钮或命名状态文本，导航到设置页面
- 重命名未启用时显示: `命名: 未启用  [⚙️ 设置]`

---

## 6. 配置持久化

```json
{
  "theme": "dark",
  "download_page": {
    "last_tags": "...",
    "last_path": "...",
    "page_threads": 5,
    "url_threads": 5
  },
  "settings": {
    "rename_enabled": false,
    "rename_mode": "pattern",
    "rename_pattern": "{post_id}_{artist}_{character}_{tags_short}_{rating}",
    "rename_prefix": "danbooru_",
    "rename_tags_short_count": 3
  }
}
```

- 默认 `rename_enabled: false`，**向后兼容**，已有用户无感知
- 配置项集中在 `settings` 命名空间下，便于后续扩展其他设置

---

## 7. 后端数据流

### 7.1 现有流程（变更前）

```
fnDownload()
  → _fnFetchAllFileUrls() → [url, ...]
  → _fnDownloadImages([url, ...])
    → 对每个 url: _fnDownloadSingleFile(url)
      下载后按 basename(url) 保存
```

### 7.2 变更后流程

```
fnDownload()
  → _fnFetchAllPosts() → [(url, post_data), ...]
     按 post_id 升序排列
  → _fnDownloadImages(posts)
    → 对每个 post: _fnDownloadSingleFile(post)
      下载完成后:
        → 若 rename_enabled:
            → _fnComputeNewFilename(post, index, total)
            → os.rename(src, dst)
            → 日志: 原文件名 → 新文件名
      否则保持原始文件名
```

### 7.3 关键变更点

| 变更 | 说明 |
|------|------|
| `_fnFetchAllFileUrls()` → `_fnFetchAllPosts()` | 返回 post 完整元数据而非仅 URL |
| 新增 `RenameConfig` | 封装重命名配置，通过 `__init__` 注入 |
| 新增 `_fnComputeNewFilename()` | 根据模板/post 元数据生成新文件名 |
| 新增 `_fnRenameFile()` | 单个文件重命名，含冲突处理和日志 |
| 新增文件名冲突处理 | 目标文件名已存在时追加 `_1`, `_2` 后缀 |

### 7.4 Tag 解析逻辑

Danbooru 的 `post.tag_string` 格式为空格分隔:
```
artist:yangmalgage character:chitanda_eru hyouka mery school_uniform
```

解析规则:
1. 按空格切分所有标签
2. 包含 `:` 的标签为命名空间标签，取冒号后部分作为值
3. 不包含 `:` 的标签为普通标签
4. `{artist}` → 取命名空间为 `artist` 的第一个标签值
5. `{tags_short}` → 取前 N 个普通标签，下划线连接

---

## 8. 待修改/新增文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/service/downloader.py` | **修改** | 改为存储 post 元数据；新增重命名逻辑 |
| `app/service/downloadWorker.py` | **修改** | 透传重命名配置 |
| `app/view/page/downloadPage.py` | **修改** | 底部添加命名状态行 |
| `app/view/page/settingsPage.py` | **新增** | 设置页面，含重命名配置 |
| `app/view/appFluentWindow.py` | **修改** | 注册设置页面到导航栏 |

---

## 9. 未纳入范围

- 重命名历史记录/撤销功能
- 批量重命名已有下载文件
- 正则表达式重命名规则
- 文件名中非法字符的替换规则（OS 文件系统已限制字符集，本功能仅用 `os.rename` 不做额外 sanitize）
