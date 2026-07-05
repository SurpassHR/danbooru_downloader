# coding: utf-8
from typing import Callable, Optional

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import CardWidget
from qfluentwidgets import LineEdit, StrongBodyLabel, CaptionLabel
from qfluentwidgets.common.overload import singledispatchmethod


class TextAreaCard(CardWidget):
    """Card with text area"""

    @singledispatchmethod
    def __init__(self, parent=None):
        super().__init__(parent)
        # need manually call init

    @__init__.register
    def _(self, title: str, desc: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.init(title=title, desc=desc)

    def init(self, title: str, desc: str):
        """Support manual init"""

        # create container
        self.container = QHBoxLayout()
        self.titleDescContainer = QVBoxLayout()

        # create title
        self.titleArea = StrongBodyLabel(text=title, parent=self)
        # create description
        self.descArea = CaptionLabel(text=desc)
        # create text area
        self.textArea = LineEdit()

        self.titleDescContainer.addWidget(self.titleArea)
        self.titleDescContainer.addWidget(self.descArea)
        self.container.addLayout(self.titleDescContainer)
        self.container.addStretch(1)
        self.container.addWidget(self.textArea)

        self.setLayout(self.container)

    def regOnTextAreaChg(self, func: Callable[[str], None]):
        """Process on text area change"""

        self.textArea.textChanged.connect(lambda text: func(text))

    def regInitTextArea(self, func: Callable[[], str]):
        """Init text area content"""

        self.textArea.setText(func())


class TextAreaCardExtra(TextAreaCard):
    @singledispatchmethod
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    @__init__.register
    def _(self, title: str, desc: str, extraInit: Callable[[TextAreaCard], None], parent: Optional[QWidget] = None):
        super().__init__(title=title, desc=desc, parent=parent)
        extraInit(self)
