# coding: utf-8
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QButtonGroup,
)
from PySide6.QtCore import Qt

from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    SwitchButton, RadioButton, LineEdit, SpinBox, FluentIcon,
    InfoBar,
)

from ...common.configLoader import getConfig, setConfig


class SettingsPage(QFrame):
    """应用设置页面。"""

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))
        self.window = window
        self._buildUI()
        self._loadConfig()

    def _buildUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._buildRenameCard(layout)
        layout.addStretch(1)

    def _buildRenameCard(self, layout):
        card = CardWidget(self)
        cardLayout = QVBoxLayout(card)

        title = StrongBodyLabel("文件命名", card)
        cardLayout.addWidget(title)

        # 启用开关
        enableRow = QHBoxLayout()
        enableRow.addWidget(BodyLabel("启用重命名:", card))
        self.renameSwitch = SwitchButton(card)
        self.renameSwitch.checkedChanged.connect(self._updatePreview)
        enableRow.addWidget(self.renameSwitch)
        enableRow.addStretch(1)
        cardLayout.addLayout(enableRow)

        cardLayout.addSpacing(8)

        # 模式选择
        modeLabel = StrongBodyLabel("模式:", card)
        cardLayout.addWidget(modeLabel)

        self.modeGroup = QButtonGroup(self)
        self.modeSeq = RadioButton("数字序号", card)
        self.modePattern = RadioButton("模板", card)
        self.modeGroup.addButton(self.modeSeq, 0)
        self.modeGroup.addButton(self.modePattern, 1)
        self.modeGroup.buttonClicked.connect(self._onModeChanged)
        modeRow = QHBoxLayout()
        modeRow.addWidget(self.modeSeq)
        modeRow.addWidget(self.modePattern)
        modeRow.addStretch(1)
        cardLayout.addLayout(modeRow)
        cardLayout.addSpacing(8)

        # 序号模式控件
        self.seqWidget = QFrame(self)
        seqLayout = QHBoxLayout(self.seqWidget)
        seqLayout.setContentsMargins(0, 0, 0, 0)
        seqLayout.addWidget(BodyLabel("前缀:", self.seqWidget))
        self.prefixInput = LineEdit(self.seqWidget)
        self.prefixInput.setPlaceholderText("例如: danbooru_")
        self.prefixInput.setText("danbooru_")
        self.prefixInput.textChanged.connect(self._updatePreview)
        seqLayout.addWidget(self.prefixInput, 1)
        seqLayout.addWidget(BodyLabel("  例: danbooru_001.jpg", self.seqWidget))
        cardLayout.addWidget(self.seqWidget)

        # 模板模式控件
        self.patternWidget = QFrame(self)
        patternLayout = QVBoxLayout(self.patternWidget)
        patternLayout.setContentsMargins(0, 0, 0, 0)

        patternRow = QHBoxLayout()
        patternRow.addWidget(BodyLabel("模板:", self.patternWidget))
        self.patternInput = LineEdit(self.patternWidget)
        self.patternInput.setPlaceholderText(
            "例如: {post_id}_{artist}_{character}_{tags_short}_{rating}"
        )
        self.patternInput.setText("{post_id}_{artist}_{character}_{tags_short}_{rating}")
        self.patternInput.textChanged.connect(self._updatePreview)
        patternRow.addWidget(self.patternInput, 1)
        patternLayout.addLayout(patternRow)

        tagsCountRow = QHBoxLayout()
        tagsCountRow.addWidget(BodyLabel("{tags_short} 标签数:", self.patternWidget))
        self.tagsCountBox = SpinBox(self.patternWidget)
        self.tagsCountBox.setRange(1, 20)
        self.tagsCountBox.setValue(3)
        self.tagsCountBox.valueChanged.connect(self._updatePreview)
        tagsCountRow.addWidget(self.tagsCountBox)
        tagsCountRow.addStretch(1)
        patternLayout.addLayout(tagsCountRow)
        cardLayout.addWidget(self.patternWidget)
        cardLayout.addSpacing(8)

        # 预览
        previewLabel = StrongBodyLabel("预览:", card)
        cardLayout.addWidget(previewLabel)
        self.previewText = CaptionLabel("暂未启用", card)
        cardLayout.addWidget(self.previewText)
        cardLayout.addSpacing(8)

        # 可用占位符参考
        hintCard = CardWidget(self)
        hintLayout = QVBoxLayout(hintCard)
        hintTitle = CaptionLabel("可用占位符", hintCard)
        hintLayout.addWidget(hintTitle)
        hintText = BodyLabel(
            "{post_id}  {artist}  {character}  {copyright}  {rating}  "
            "{md5}  {date}  {tags_short}  {search_tags}  {ext}",
            hintCard,
        )
        hintText.setWordWrap(True)
        hintLayout.addWidget(hintText)
        cardLayout.addWidget(hintCard)

        layout.addWidget(card)

        # 初始状态: 显示序号模式
        self.modeSeq.setChecked(True)
        self._onModeChanged()

    def _onModeChanged(self):
        """切换序号/模板时显示/隐藏对应控件。"""
        isSeq = self.modeGroup.checkedId() == 0
        self.seqWidget.setVisible(isSeq)
        self.patternWidget.setVisible(not isSeq)
        self._updatePreview()

    def _updatePreview(self):
        """根据当前配置生成预览文件名。"""
        if not self.renameSwitch.isChecked():
            self.previewText.setText("(已禁用)")
            return

        isSeq = self.modeGroup.checkedId() == 0
        if isSeq:
            prefix = self.prefixInput.text().strip()
            self.previewText.setText(f"{prefix}001.jpg  (自动按总数决定位数)")
        else:
            pattern = self.patternInput.text().strip()
            if not pattern:
                self.previewText.setText("(请输入模板)")
                return
            preview = pattern
            demo = {
                "{post_id}": "12345678",
                "{artist}": "yangmalgage",
                "{character}": "chitanda_eru",
                "{copyright}": "hyouka",
                "{rating}": "s",
                "{md5}": "abc123def",
                "{date}": "2025-06-30",
                "{tags_short}": "hyouka_mery_highres",
                "{search_tags}": "mery_hyouka",
                "{ext}": ".jpg",
            }
            for key, val in demo.items():
                preview = preview.replace(key, val)
            if "{ext}" not in pattern:
                preview += ".jpg"
            self.previewText.setText(preview)

    def _loadConfig(self):
        """从 config.json 加载设置。"""
        enabled = getConfig("settings.rename_enabled", False)
        self.renameSwitch.setChecked(enabled)

        mode = getConfig("settings.rename_mode", "pattern")
        if mode == "sequence":
            self.modeSeq.setChecked(True)
        else:
            self.modePattern.setChecked(True)

        prefix = getConfig("settings.rename_prefix", "danbooru_")
        self.prefixInput.setText(prefix)

        pattern = getConfig("settings.rename_pattern", "{post_id}_{artist}_{character}_{tags_short}_{rating}")
        self.patternInput.setText(pattern)

        tagsCount = getConfig("settings.rename_tags_short_count", 3)
        self.tagsCountBox.setValue(tagsCount)

        self._onModeChanged()

    def _saveConfig(self):
        """保存设置到 config.json。"""
        setConfig("settings.rename_enabled", self.renameSwitch.isChecked())
        setConfig("settings.rename_mode", "sequence" if self.modeGroup.checkedId() == 0 else "pattern")
        setConfig("settings.rename_prefix", self.prefixInput.text().strip())
        setConfig("settings.rename_pattern", self.patternInput.text().strip())
        setConfig("settings.rename_tags_short_count", self.tagsCountBox.value())

        InfoBar.success(parent=self, title="", content="设置已保存")

    def hideEvent(self, event):
        """页面隐藏时自动保存。"""
        self._saveConfig()
        super().hideEvent(event)
