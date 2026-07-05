<div align="center">
  <h1>
    <a href="https://danbooru.donmai.us"><img src="assets/icon.png" alt="Danbooru Logo" width="32" height="32"></a>
    Danbooru Downloader
  </h1>
  <p>
    <strong>基于 PySide6 的 Danbooru 图片批量下载工具</strong>
  </p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/GUI-PySide6-green?logo=qt" alt="PySide6">
    <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
  </p>
</div>

---

## 📖 项目简介

**Danbooru Downloader** 是一个从 [Danbooru](https://danbooru.donmai.us) 图片社区按标签批量下载原始图片的工具。支持多线程并发爬取、断点续传、增量缓存，提供命令行和桌面 GUI 两种使用方式。

> GUI 框架基于 [PySide6-Application-Template](https://github.com/SurpassHR/PySide6-Application-Template)。

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🏷️ **标签过滤** | 支持 `OR` 和 `NOT` 运算符，参见 [Danbooru 黑名单语法](https://danbooru.donmai.us/wiki_pages/help:blacklists) |
| 🔄 **断点续传** | 中断后重新运行自动从上次位置继续，不重复爬取已缓存的页面 |
| ⚡ **多线程并发** | 页面爬取和图片下载分别支持自定义线程数，加速大批量下载 |
| 📦 **增量缓存** | JSONL 格式增量写入缓存，批处理防内存溢出，意外退出不丢数据 |
| 🎨 **Fluent 桌面端** | 基于 PySide6-Fluent-Widgets 的现代 GUI，支持暗/亮主题切换 |
| 📊 **进度显示** | 终端模式使用 `tqdm` 进度条；GUI 模式通过进度卡片展示 |
| 🛡️ **智能重试** | HTTP 429/5xx 自动重试，指数退避策略，尊重 `Retry-After` 头 |
| 💻 **跨平台** | 支持 Windows 11（Mica 特效）、macOS、Linux |

---

## 🚀 快速开始

### 环境要求

- **Python** >= 3.12
- **pip**（Python 包管理器）

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/SurpassHR/danbooru_downloader.git
cd danbooru_downloader

# 初始化开发环境（创建 venv + 安装依赖）
bash init_dev_env.sh
```

### 命令行模式

编辑 `app/service/downloader.py` 底部的 `TAG_LIST` 和 `DOWNLOAD_PATH`，然后：

```bash
python app/service/downloader.py
```

下载的图片存放在 `downloads/images/`，缓存文件在 `downloads/cache/`。

> **提示**：开始新任务前，建议手动删除 `downloads/cache/` 和 `downloads/images/` 目录以清空旧缓存。

### GUI 桌面模式

```bash
python main.py
```

启动后将显示 Fluent Design 风格桌面窗口，通过侧边导航栏进入各功能页面。

---

## 📁 项目结构

```
danbooru_downloader/
├── main.py                     # 程序入口（GUI 模式）
├── init_dev_env.sh             # 一键开发环境初始化
├── pyinstall.py                # PyInstaller 打包脚本
├── pyproject.toml              # Ruff 代码格式化配置
├── README.md                   # 本文件
├── assets/                     # 静态资源
│   ├── icon.png                # 应用图标
│   ├── icons/                  # 导航栏图标
│   └── images/                 # 页面横幅
├── config/
│   ├── config.json             # GUI 配置文件（主题等）
│   └── requirements.txt        # Python 依赖列表
├── app/                        # 应用主代码
│   ├── app.py                  # 应用入口（startApp 函数）
│   ├── common/                 # 公共模块
│   │   ├── application.py      # 单实例应用（QSharedMemory）
│   │   ├── configLoader.py     # JSON 配置读写
│   │   ├── eventManager.py     # 事件管理（信号/槽/线程池）
│   │   ├── levelDefs.py        # 日志/消息级别枚举
│   │   ├── simpleLogger.py     # 日志工具（文件 + rich 终端）
│   │   ├── singleton.py        # 单例装饰器
│   │   ├── styleDefs.py        # ANSI 颜色/样式枚举
│   │   ├── timeTools.py        # 时间工具
│   │   └── uiFunctionBase.py   # UI 功能基类
│   ├── service/                # 业务逻辑层
│   │   └── downloader.py       # Danbooru 下载器核心类
│   ├── view/                   # 视图层
│   │   ├── appFluentWindow.py  # 主窗口（Fluent Design）
│   │   └── page/               # 导航页面
│   └── widget/                 # 自定义组件
│       ├── progressCard.py     # 进度条卡片
│       └── textAreaCard.py     # 文本输入卡片
├── downloads/                  # 运行时生成
│   ├── cache/                  # 增量缓存文件
│   └── images/                 # 下载的图片
└── log/                        # 运行时日志
```

---

## ⚙️ 配置说明

### GUI 配置 (`config/config.json`)

```json
{
    "theme": "dark",
    "log_min_level": 1,
    "log_filepath_reserve": 35
}
```

| 键 | 类型 | 说明 |
|----|------|------|
| `theme` | string | 主题：`"dark"` / `"light"` |
| `log_min_level` | int | 日志最低级别 |
| `log_filepath_reserve` | int | 日志文件路径保留宽度 |

### 下载器配置

命令行模式下，修改 `app/service/downloader.py` 底部：

```python
TAG_LIST = ["mery_(yangmalgage)", "hyouka"]  # 目标标签
DOWNLOAD_PATH = "./downloads"                   # 下载目录

oDownloader = DanbooruDownloader(
    lsTags=TAG_LIST,
    sDownloadRoot=DOWNLOAD_PATH,
    iPageThreads=5,    # 页面爬取线程数
    iUrlThreads=10,    # 图片下载线程数
    iBatchSize=50,     # 缓存批处理大小
)
```

---

## 🔧 代码格式化

项目使用 [Ruff](https://docs.astral.sh/ruff/) 进行代码格式化和 lint：

```bash
# 检查格式问题
ruff check .

# 自动修复
ruff check --fix .

# 格式化代码
ruff format .
```

配置在 `pyproject.toml` 中（行长 120, 双引号，缩进宽度 4，目标 Python 3.12）。

---

## 📦 打包为可执行文件

```bash
python pyinstall.py
```

打包输出到 `dist/main/`，自动复制 `config/` 和 `assets/` 到目标目录。

| PyInstaller 选项 | 说明 |
|-----------------|------|
| `--onedir` | 输出为目录（非单文件） |
| `--optimize=2` | 完全优化 |
| `--noconfirm` | 覆盖已存在输出 |
| `--clean` | 清理缓存 |

---

## 🧩 核心架构

### 下载器（CLI）数据流

```
标签搜索 → 分页爬取 → 帖子 URL 缓存（JSONL）
    ↓
帖子 URL → 爬取直链 → 图片 URL 映射缓存（JSONL）
    ↓
图片 URL → 并发下载 → 下载完成（.part 临时文件 → 最终文件）
```

### GUI 架构

```
main.py → app.py → AppFluentWindow（FluentWindow 子类）
                     ├── 页面路由
                     ├── 组件系统（TextAreaCard / ProgressCard）
                     ├── 事件管理（Signal/Slot + QThreadPool）
                     └── 配置管理（JSON 读/写）
```

---

## 📝 开发笔记

- **分支策略**：当前主分支为 `gui`，`master` 分支为遗留代码
- **日志**：日志自动写入 `log/YY-MM-DD.log`，终端同步彩色输出
- **单实例**：通过 `QSharedMemory` + `QLocalServer` 防止重复启动
- **清理退出**：`SIGINT`/`SIGTERM` 信号 + `atexit` 保证缓存数据写入磁盘

---

## 📄 License

MIT License
