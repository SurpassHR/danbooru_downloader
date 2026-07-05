# AGENTS.md

> 本文档为 AI 编程助手（如 Claude、GitHub Copilot、Cursor 等）提供项目级别的操作指引。

---

## 🏗️ 项目概述

**Danbooru Downloader** 是一个 Python 桌面应用，主要功能是从 Danbooru 批量下载图片。当前处于 GUI 集成阶段——下载器核心逻辑已完成（CLI 可用），GUI 框架已搭建但尚未与下载器对接。

- **语言**：Python >= 3.12
- **GUI**：PySide6 + PySide6-Fluent-Widgets
- **代码格式化**：Ruff（配置：`pyproject.toml`）
- **主分支**：`gui`

---

## 📁 关键文件速查

| 文件 | 作用 |
|------|------|
| `main.py` | GUI 模式入口（调用 `app.app.startApp()`） |
| `app/app.py` | 应用初始化、高 DPI 设置、平台适配 |
| `app/service/downloader.py` | 下载器核心类 `DanbooruDownloader`（CLI 独立可运行） |
| `app/view/appFluentWindow.py` | 主窗口（Fluent Design） |
| `app/view/page/examplePage.py` | 示例页面（展示组件用法） |
| `app/widget/progressCard.py` | 进度条卡片组件 |
| `app/widget/textAreaCard.py` | 文本输入卡片组件 |
| `app/common/configLoader.py` | JSON 配置读/写（支持点分隔嵌套 key） |
| `app/common/eventManager.py` | 事件中心（Signal/Slot + QThreadPool） |
| `app/common/simpleLogger.py` | 日志系统（文件滚动 + rich 终端输出） |
| `app/common/application.py` | 单实例检查（QSharedMemory + QLocalServer） |
| `config/config.json` | GUI 运行时配置 |
| `config/requirements.txt` | Python 依赖声明 |
| `pyproject.toml` | Ruff 格式化配置 |

---

## 🔧 开发约定

### Python 代码风格

- **格式化工具**：Ruff
- **行长限制**：120 字符
- **引号风格**：双引号
- **缩进**：4 空格
- **目标 Python 版本**：3.12
- **命名约定**：
  - 类名：`PascalCase`
  - 函数/方法：`camelCase`（注意：初始模板存在 `lowerCamelCase` 混合）
  - 常量：`UPPER_SNAKE_CASE`
  - 模块级私有函数：`_underScorePrefixedCase`
  - 文件/模块：`camelCase.py`

### GUI 开发规则

1. **页面**：放在 `app/view/page/`，继承 `qfluentwidgets` 组件，通过 `AppFluentWindow.addPages()` 注册
2. **组件**：放在 `app/widget/`，封装可复用的 PySide6 组件
3. **业务逻辑**：放在 `app/service/`，与 GUI 解耦
4. **事件通信**：通过 `app/common/eventManager.py` 的 Signal/Slot 机制
5. **配置读写**：通过 `app/common/configLoader.py` 的 `getConfig()` / `setConfig()`
6. **日志**：使用 `app/common/simpleLogger.py` 的 `loggerPrint()`

### 文件头部编码声明

所有 `.py` 文件首行为 `# coding: utf-8`（历史遗留模板约定）。

---

## 🎯 当前项目状态与待办事项

### 已完成

- [x] CLI 下载器核心（`DanbooruDownloader`）：多线程爬取、断点续传、增量缓存
- [x] GUI 框架搭建（FluentWindow、组件系统、事件管理、配置管理）
- [x] 单实例检查
- [x] 暗/亮主题切换
- [x] 日志系统
- [x] 下载器取消支持（`fnCancel` / `fnIsCancelled`）
- [x] 下载页面（`DownloadPage`）：标签输入、配置选项、进度显示、运行日志
- [x] 后台下载（`DownloadWorker` + `QThread` + 轮询进度）
- [x] 修复窗口标题：`Change Me!` → `Danbooru Downloader`
- [x] 修复单实例 ID：`DownloadXiaoeknowVideo` → `DanbooruDownloader`
- [x] 修复项目主页链接：百度 → GitHub

### 待完成

- [ ] 将下载器配置从硬编码迁移到 `config.json`
- [ ] 下载完成后的结果展示页面

---

## 🧪 调试与运行

```bash
# 激活虚拟环境
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows

# 运行 GUI
python main.py

# 运行 CLI 下载器（独立模式）
python app/service/downloader.py

# Ruff 检查与修复
ruff check . --fix
ruff format .
```

---

## ⚠️ 注意事项

1. **`downloads/cache/` 和 `downloads/images/` 是运行时目录**，不要手动向仓库提交内容。`.gitignore` 已排除。
2. **下载器直接运行时**（`if __name__ == "__main__"`）使用硬编码的 `TAG_LIST` 和 `DOWNLOAD_PATH`，GUI 集成时需要改为配置驱动。
3. **SSL 验证已禁用**（`verify=False`），如果运行环境对安全性有要求需要注意。
4. **模板残留**：`examplePage`、`Change Me!` 标题、`DownloadXiaoeknowVideo` 单实例 ID 等需要后续清理。
5. **打包脚本**（`pyinstall.py`）仅在 `config/requirements.txt` 存在时读取隐藏导入，如果新增了不在 `requirements.txt` 中的依赖，需同步更新。

---

## 📚 外部文档引用

- [Danbooru 标签语法](https://danbooru.donmai.us/wiki_pages/help:blacklists)
- [PySide6 文档](https://doc.qt.io/qtforpython-6/)
- [PySide6-Fluent-Widgets](https://qfluentwidgets.com/)
- [Ruff 配置文档](https://docs.astral.sh/ruff/configuration/)
