# coding: utf-8
from enum import IntEnum, StrEnum


# fmt: off
# log levels
class LogLevels(IntEnum):
    DEBUG       = 0
    INFO        = 1
    WARNING     = 2
    ERROR       = 3
    CRITICAL    = 4

# messageBox levels
class MsgBoxLevels(StrEnum):
    INFO        = "提示"
    WARNING     = "警告"
    ERROR       = "错误"
    CRITICAL    = "致命"
# fmt: on
