# coding: utf-8
import sys
import platform

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from .common.application import SingletonApplication
from .view.appFluentWindow import AppFluentWindow


def _setAppAttrs():
    # PassThrough: 保留精确分数缩放比，防止 Windows 上模糊
    # Floor: 向下取整，Linux 下常见 1.25×~1.75× 均降为 1×，避免文字过大
    #        只有 ≥2.0 的高分屏才生效
    if sys.platform.startswith("linux"):
        policy = Qt.HighDpiScaleFactorRoundingPolicy.Floor
    elif sys.platform == "darwin":
        policy = Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    else:
        policy = Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    QApplication.setHighDpiScaleFactorRoundingPolicy(policy)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)
    # Qt 6 已默认启用 HighDpiScaling，不再需要显式设置
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)


def _isWindows11OrHigher():
    if sys.platform.startswith("win"):
        versionInfo = platform.version()
        # win11 intern version number starts from 10.0.22000
        if int(versionInfo.split(".")[0]) >= 10 and int(versionInfo.split(".")[2]) >= 22000:
            return True
    return False


def _platformSettings(window: AppFluentWindow):
    window.setMicaEffectEnabled(True if _isWindows11OrHigher() else False)
    if sys.platform == "darwin":
        from AppKit import NSApplication

        NSApplication.sharedApplication()


def startApp():
    _setAppAttrs()

    app = SingletonApplication(sys.argv, "DanbooruDownloader")

    # set your window title here
    window = AppFluentWindow(window_title="Danbooru Downloader")
    _platformSettings(window=window)
    window.show()

    app.exec()
