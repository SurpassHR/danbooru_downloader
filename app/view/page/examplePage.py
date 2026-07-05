# coding: utf-8
from PySide6.QtWidgets import QFrame, QVBoxLayout

from qfluentwidgets import PrimaryPushButton, FluentIcon as Icon

from ...widget.textAreaCard import TextAreaCard, TextAreaCardExtra
from ...widget.progressCard import ProgressCard
from ...common.uiFunctionBase import uiFuncBase
from ...common.levelDefs import MsgBoxLevels


class ExamplePage(QFrame):
    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # global variable
        self.window = window

        # create container
        self.container = QVBoxLayout()

        # create a widget card
        def cardInit(card: TextAreaCard):
            # create a button
            btn = PrimaryPushButton(text="示例按钮", parent=card, icon=Icon.ACCEPT)
            # when click btn get text area's content
            btn.clicked.connect(
                lambda: uiFuncBase.uiShowMsgBox(level=MsgBoxLevels.INFO, msg=f"文本框的内容是: {card.textArea.text()}")
            )
            # btn should be add to the end of card
            card.container.addWidget(btn)

        self.widgetCard1 = TextAreaCardExtra(
            title="带输入区域的卡片组件。",
            desc="可以在输入区域输入文字。",
            extraInit=cardInit,
            parent=self,
        )
        self.widgetCard1.setMaximumHeight(100)
        self.widgetCard2 = TextAreaCardExtra(
            title="带输入区域的卡片组件。",
            desc="可以在输入区域输入文字。",
            extraInit=cardInit,
            parent=self,
        )
        self.widgetCard2.setMaximumHeight(100)
        self.widgetCard3 = TextAreaCardExtra(
            title="带输入区域的卡片组件。",
            desc="可以在输入区域输入文字。",
            extraInit=cardInit,
            parent=self,
        )
        self.widgetCard3.setMaximumHeight(100)

        self.progressCard = ProgressCard(
            title="带进度条的卡片组件。",
            fileIcon=Icon.QUICK_NOTE,
            parent=self,
        )
        self.progressCard.updateProgress(50)
        self.progressCard.setMaximumHeight(100)

        self.container.addWidget(self.widgetCard1, 1)
        self.container.addWidget(self.widgetCard2, 1)
        self.container.addWidget(self.widgetCard3, 1)
        self.container.addWidget(self.progressCard, 1)

        self.setLayout(self.container)
