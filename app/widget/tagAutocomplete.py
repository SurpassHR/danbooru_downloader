# coding: utf-8
"""Danbooru 标签自动补全输入框组件。"""

import json
import re
import sys

import requests
from curl_cffi import requests as cffi_requests

from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtWidgets import QListWidget
from qfluentwidgets import LineEdit, isDarkTheme

from ..common.simpleLogger import loggerPrint
from ..common.levelDefs import LogLevels

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

DEBOUNCE_MS = 150
MIN_QUERY_LENGTH = 2
MAX_POPUP_ITEMS = 10

# 请求头仅用于 Gelbooru（regular requests）
GELBOORU_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

AUTOCOMPLETE_SOURCES = [
    {
        "name": "Danbooru",
        "url": "https://danbooru.donmai.us/autocomplete",
        "params": lambda q: {
            "search[query]": q,
            "search[type]": "tag_query",
            "version": "3",
            "limit": "20",
        },
        # curl_cffi 模拟 Safari 指纹绕过 Cloudflare（Chrome 指纹被屏蔽）
        "use_cffi": True,
        "parser": "html",       # 返回 HTML，需解析 data-autocomplete-value
    },
    {
        "name": "Gelbooru",
        "url": "https://gelbooru.com/index.php",
        "params": lambda q: {
            "page": "autocomplete2",
            "term": q,
            "limit": "20",
        },
        "use_cffi": False,
        "parser": "json",       # 返回标准 JSON
    },
]


class AutocompleteThread(QThread):
    """在独立线程中执行 autocomplete API 请求（多源轮询）。"""

    resultReady = Signal(list)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self._query = query

    def run(self):
        for source in AUTOCOMPLETE_SOURCES:
            try:
                if source.get("use_cffi"):
                    # curl_cffi + impersonate 模拟浏览器 TLS 指纹
                    resp = cffi_requests.get(
                        source["url"],
                        params=source["params"](self._query),
                        impersonate="safari15_3",
                        timeout=8,
                    )
                else:
                    resp = requests.get(
                        source["url"],
                        params=source["params"](self._query),
                        headers=GELBOORU_HEADERS,
                        timeout=8,
                    )

                if resp.status_code == 200:
                    parser = source.get("parser", "json")
                    if parser == "html":
                        suggestions = re.findall(
                            r'data-autocomplete-value="([^"]+)"',
                            resp.text,
                        )
                    else:
                        data = resp.json()
                        suggestions = [
                            item["value"] for item in data if "value" in item
                        ]
                    if suggestions:
                        loggerPrint(
                            f"[AutoComplete] {source['name']} 返回 {len(suggestions)} 条建议",
                            LogLevels.INFO,
                        )
                        self.resultReady.emit(suggestions)
                        return
                else:
                    loggerPrint(
                        f"[AutoComplete] {source['name']} 状态码 {resp.status_code}",
                        LogLevels.INFO,
                    )
            except Exception as e:
                loggerPrint(
                    f"[AutoComplete] {source['name']} 异常: {e}",
                    LogLevels.INFO,
                )
        self.resultReady.emit([])


class TagAutocomplete(LineEdit):
    """支持 Danbooru 标签自动补全的输入框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._currentQuery = ""
        self._activating = False
        self._suggestions = []

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._doRequest)

        self._popup = QListWidget(self)
        self._popup.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self._popup.setFocusProxy(self)
        self._popup.setMaximumHeight(300)
        self._popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._popup.itemClicked.connect(self._onItemClicked)
        self._popup.setObjectName("tagAutocompletePopup")
        self._popup.setUniformItemSizes(True)
        self._popup.setStyleSheet(self._buildPopupStyle())
        self._popup.hide()

        # 监听主题切换，更新弹出样式
        try:
            from qfluentwidgets import qApp
            qApp.themeChanged.connect(self._onThemeChanged)
        except Exception:
            pass

        from PySide6.QtWidgets import QApplication
        self.installEventFilter(self)
        self._popup.installEventFilter(self)
        QApplication.instance().installEventFilter(self)

        self.textChanged.connect(self._onTextChanged)

    def eventFilter(self, obj, event):
        # 全局：点击弹出窗口外部时关闭
        if event.type() == event.Type.MouseButtonPress:
            if self._popup.isVisible():
                try:
                    pos = event.globalPosition().toPoint()
                except AttributeError:
                    pos = event.globalPos()
                if not self._popup.geometry().contains(pos):
                    self._hidePopup()

        # 键盘：弹出窗口可见时处理导航
        if obj in (self, self._popup) and self._popup.isVisible():
            if event.type() == event.Type.KeyPress:
                key = event.key()
                if key == Qt.Key_Down:
                    self._popup.setCurrentRow(
                        max(0, self._popup.currentRow() + 1)
                    )
                    return True
                elif key == Qt.Key_Up:
                    self._popup.setCurrentRow(
                        max(0, self._popup.currentRow() - 1)
                    )
                    return True
                elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    item = self._popup.currentItem()
                    if item:
                        self._selectSuggestion(item.text())
                        return True
                elif key == Qt.Key_Escape:
                    self._hidePopup()
                    return True
        return super().eventFilter(obj, event)

    def _onTextChanged(self, text):
        if self._activating:
            return
        words = text.strip().split()
        if words and len(words[-1]) >= MIN_QUERY_LENGTH:
            self._currentQuery = words[-1]
            loggerPrint(f"[AutoComplete] 输入检测: query='{self._currentQuery}', 防抖 {DEBOUNCE_MS}ms", LogLevels.INFO)
            self._debounce.start()
        else:
            self._hidePopup()
            self._debounce.stop()
            loggerPrint("[AutoComplete] 输入清空或不足2字符，关闭弹出", LogLevels.INFO)

    def _doRequest(self):
        if not self._currentQuery:
            return
        loggerPrint(f"[AutoComplete] 发起 API 请求: query='{self._currentQuery}'", LogLevels.INFO)

        thread = AutocompleteThread(self._currentQuery, self)
        thread.resultReady.connect(self._onResults)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _onResults(self, suggestions):
        loggerPrint(
            f"[AutoComplete] API 返回: query='{self._currentQuery}', "
            f"建议数={len(suggestions)}, 结果={suggestions[:5]}"
            + f"{'...' if len(suggestions)>5 else ''}",
            LogLevels.INFO,
        )
        self._suggestions = suggestions
        if suggestions:
            self._showPopup(suggestions)
        else:
            self._hidePopup()
            loggerPrint("[AutoComplete] 无建议，不弹出", LogLevels.INFO)

    def _showPopup(self, items):
        self._popup.clear()
        for item in items[:MAX_POPUP_ITEMS]:
            self._popup.addItem(item)
        self._popup.setCurrentRow(0)

        pos = self.mapToGlobal(self.rect().bottomLeft())
        popup_width = max(self.width(), 200)
        item_height = self._popup.sizeHintForRow(0) if self._popup.count() > 0 else 24
        popup_height = min(self._popup.count() * item_height + 4, 300)
        self._popup.setGeometry(pos.x(), pos.y(), popup_width, popup_height)
        self._popup.show()
        self._popup.show()
        loggerPrint(f"[AutoComplete] 弹出列表 ({len(items)} 项)", LogLevels.INFO)

    def _buildPopupStyle(self, dark=None):
        """根据主题生成弹出列表样式表。"""
        if dark is None:
            dark = isDarkTheme()
        if dark:
            return '''
            QListWidget#tagAutocompletePopup {
                background: #252525;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QListWidget#tagAutocompletePopup QScrollBar:vertical {
                width: 6px;
                background: transparent;
                margin: 0;
            }
            QListWidget#tagAutocompletePopup QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 30px;
                border-radius: 3px;
            }
            QListWidget#tagAutocompletePopup QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.35);
            }
            QListWidget#tagAutocompletePopup QScrollBar::add-line:vertical,
            QListWidget#tagAutocompletePopup QScrollBar::sub-line:vertical {
                height: 0;
            }
            QListWidget#tagAutocompletePopup QScrollBar::add-page:vertical,
            QListWidget#tagAutocompletePopup QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QListWidget#tagAutocompletePopup::item {
                padding: 6px 14px;
                min-height: 28px;
                border-radius: 4px;
                font-size: 13px;
                color: #ffffff;
            }
            QListWidget#tagAutocompletePopup::item:hover {
                background: rgba(255, 255, 255, 0.06);
            }
            QListWidget#tagAutocompletePopup::item:selected {
                background: rgba(96, 160, 255, 0.3);
            }
            '''
        else:
            return '''
            QListWidget#tagAutocompletePopup {
                background: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QListWidget#tagAutocompletePopup QScrollBar:vertical {
                width: 6px;
                background: transparent;
                margin: 0;
            }
            QListWidget#tagAutocompletePopup QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.15);
                min-height: 30px;
                border-radius: 3px;
            }
            QListWidget#tagAutocompletePopup QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.25);
            }
            QListWidget#tagAutocompletePopup QScrollBar::add-line:vertical,
            QListWidget#tagAutocompletePopup QScrollBar::sub-line:vertical {
                height: 0;
            }
            QListWidget#tagAutocompletePopup QScrollBar::add-page:vertical,
            QListWidget#tagAutocompletePopup QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QListWidget#tagAutocompletePopup::item {
                padding: 6px 14px;
                min-height: 28px;
                border-radius: 4px;
                font-size: 13px;
                color: #000000;
            }
            QListWidget#tagAutocompletePopup::item:hover {
                background: rgba(0, 0, 0, 0.06);
            }
            QListWidget#tagAutocompletePopup::item:selected {
                background: rgba(96, 160, 255, 0.15);
            }
            '''

    def _onThemeChanged(self):
        self._popup.setStyleSheet(self._buildPopupStyle())

    def _hidePopup(self):
        if self._popup.isVisible():
            self._popup.hide()

    def _onItemClicked(self, item):
        self._selectSuggestion(item.text())

    def _selectSuggestion(self, completion):
        loggerPrint(f"[AutoComplete] 选中补全: '{completion}'", LogLevels.INFO)
        self._hidePopup()
        self._activating = True
        self._debounce.stop()
        self._currentQuery = ""

        fullText = self.text()
        cursorPos = self.cursorPosition()

        wordStart = fullText.rfind(" ", 0, cursorPos)
        if wordStart == -1:
            wordStart = 0
        else:
            wordStart += 1

        wordEnd = fullText.find(" ", cursorPos)
        if wordEnd == -1:
            wordEnd = len(fullText)

        if wordEnd < len(fullText) and fullText[wordEnd] == " ":
            spaceAfter = fullText[wordEnd:]
        else:
            spaceAfter = " " + fullText[wordEnd:]

        newText = fullText[:wordStart] + completion + spaceAfter
        self.setText(newText)
        self._activating = False
        self.setCursorPosition(wordStart + len(completion) + 1)
