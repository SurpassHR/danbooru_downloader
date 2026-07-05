# coding: utf-8
import sys
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl
from PySide6.QtGui import QScreen

from qfluentwidgets.common.icon import FluentIcon, QIcon, QImage
from qfluentwidgets import FluentWindow, NavigationItemPosition, NavigationAvatarWidget
from qfluentwidgets.common.config import Theme, isDarkTheme
from qfluentwidgets.common.style_sheet import setTheme, setThemeColor
from qfluentwidgets.components.navigation.navigation_widget import NavigationPushButton

from ..common.levelDefs import LogLevels, MsgBoxLevels
from ..common.simpleLogger import loggerPrint
from ..common.configLoader import getConfig, setConfig
from ..common.uiFunctionBase import uiFuncBase
from ..view.page.downloadPage import DownloadPage
from ..view.page.settingsPage import SettingsPage


class AppFluentWindow(FluentWindow):
    APP_WIDTH = 1280
    APP_HEIGHT = 720

    THEME_COLOR = "#8A95A9"

    def __init__(self, window_title: str) -> None:
        super().__init__()

        # default config
        self.default = {
            "theme": "dark",
        }

        # set theme color
        setThemeColor(self.THEME_COLOR)

        # set theme
        setTheme(Theme.DARK if getConfig("theme") == "dark" else Theme.LIGHT)

        # set icon
        self.setWindowIcon(QIcon("assets/icons/icon-app.png"))

        # set window attributes
        self.resize(self.APP_WIDTH, self.APP_HEIGHT)
        self.setMinimumSize(self.APP_WIDTH, self.APP_HEIGHT)
        self.setWindowTitle(window_title)
        # self.titleBar.iconLabel.hide()  # Removed: iconLabel is not a known property of TitleBar

        # set startup position
        screen: QScreen = QApplication.primaryScreen()
        if screen:
            # get main screen available geometry
            available_geometry = screen.availableGeometry()

            # calculate main window position
            x = available_geometry.width() // 2 - self.width() // 2
            y = available_geometry.height() // 2 - self.height() // 2

            # move window to calculated position
            self.move(x, y)
        else:
            # if no screen to use, it means errors with env
            sys.exit(-1)

        # set sidebar width
        self.navigationInterface.setExpandWidth(192)

        # set expanding sidebar as default
        self.navigationInterface.setMinimumExpandWidth(self.APP_WIDTH)
        self.navigationInterface.expand(useAni=False)

        # hide go back button
        self.navigationInterface.panel.setReturnButtonVisible(False)

        # add pages
        self.addPages()

        # bind main window to eventManger
        uiFuncBase.uiSetMainWindow(self)

    def addPages(self) -> None:
        # add your page here
        self.addSubInterface(
            DownloadPage("_downloadPage", self), FluentIcon.DOWNLOAD, "下载", NavigationItemPosition.SCROLL
        )
        self.addSubInterface(
            SettingsPage("_settingsPage", self), FluentIcon.SETTING, "设置", NavigationItemPosition.SCROLL
        )
        self.addProjectMainPageHyperlink()
        self.addThemeChangingWidget()
        self._settingsPage = None

    def switchToSettings(self):
        """导航到设置页面。"""
        if not self._settingsPage:
            self._settingsPage = self.findChild(SettingsPage)
        if self._settingsPage:
            nav_item = self.navigationInterface.widget("_settingsPage")
            if nav_item:
                nav_item.click()


    def addProjectMainPageHyperlink(self) -> None:
        def _openProjectPage() -> None:
            # add your project link here
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

    def addThemeChangingWidget(self) -> None:
        self.navigationInterface.addWidget(
            routeKey="themeNavigationButton",
            widget=NavigationPushButton(FluentIcon.CONSTRACT, "主题切换", False),
            onClick=self.toggleTheme,
            position=NavigationItemPosition.BOTTOM,
        )

    def closeEvent(self, e) -> None:
        def _acptClose():
            loggerPrint("主窗口已关闭", level=LogLevels.INFO)
            e.accept()

        def _rjktClose():
            loggerPrint("主窗口保持开启", level=LogLevels.INFO)
            e.ignore()

        uiFuncBase.uiShowMsgBox(
            level=MsgBoxLevels.INFO,
            msg="是否退出程序？",
            acptCbk=_acptClose,
            rjctCbk=_rjktClose,
        )

    # change theme
    def toggleTheme(self) -> None:
        key: str = "theme"

        if not isDarkTheme():
            setTheme(Theme.DARK)
            setConfig(key, "dark")
            loggerPrint("主题切换: light -> dark")
        else:
            setTheme(Theme.LIGHT)
            setConfig(key, "light")
            loggerPrint("主题切换: dark -> light")
