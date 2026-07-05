# coding: utf-8
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout

from qfluentwidgets import ProgressBar, CardWidget, IconWidget, FluentIcon, StrongBodyLabel
from qfluentwidgets.common.overload import singledispatchmethod


class ProgressCard(CardWidget):
    """Card with progress bar"""

    @singledispatchmethod
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    @__init__.register
    def _(self, title: str, fileIcon: QIcon, parent=None):
        super().__init__(parent=parent)
        self.init(title=title, fileIcon=fileIcon)

    def init(self, title: str, fileIcon: QIcon):
        # create container
        self.titleProgBarContainer = QVBoxLayout()
        self.container = QHBoxLayout()

        # wrap file icon into a widget
        self.fileIcon = IconWidget(fileIcon)
        self.fileIcon.setFixedSize(50, 50)
        # create title
        self.titleArea = StrongBodyLabel(text=title, parent=self)
        # create progess bar
        self.progressBar = ProgressBar(parent=self, useAni=True)
        self.progressBar.setRange(0, 100)
        # create start / stop icon button
        self.ctrlBtn = IconWidget(parent=self)
        self.ctrlBtn.setIcon(icon=FluentIcon.PLAY_SOLID)
        self.ctrlBtn.setFixedSize(50, 50)

        self.titleProgBarContainer.addStretch(1)
        self.titleProgBarContainer.addWidget(self.titleArea)
        self.titleProgBarContainer.addStretch(1)
        self.titleProgBarContainer.addWidget(self.progressBar)
        self.titleProgBarContainer.addStretch(1)
        self.container.addWidget(self.fileIcon)
        self.container.addLayout(self.titleProgBarContainer)
        self.container.addWidget(self.ctrlBtn)

        self.setLayout(self.container)

    def updateProgress(self, perct: int):
        self.progressBar.setValue(perct)
