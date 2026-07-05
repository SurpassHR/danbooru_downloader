# coding: utf-8
import sys
import os
import re
import inspect
from typing import Dict
from pathlib import Path
from rich import print

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from ..common.styleDefs import ANSIColors, ANSIStyles
from ..common.levelDefs import LogLevels
from ..common.timeTools import getCurrTimeInFmt, getCurrTime
from ..common.configLoader import getConfig, setConfig

# fmt: off
LOG_LEVEL_AND_COLOR_MATCH: Dict[LogLevels, ANSIColors] = {
    LogLevels.DEBUG:    ANSIColors.COLOR_BRIGHT_BLUE,
    LogLevels.INFO:     ANSIColors.COLOR_BRIGHT_GREEN,
    LogLevels.WARNING:  ANSIColors.COLOR_BRIGHT_YELLOW,
    LogLevels.ERROR:    ANSIColors.COLOR_BRIGHT_RED,
    LogLevels.CRITICAL: ANSIColors.COLOR_BRIGHT_MAGENTA,
}
# fmt: on

LOG_MIN_LEVEL = getConfig("log_min_level", LogLevels.INFO.value)
ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent)  # 根据你的实际目录结构调整


def loggerPrint(msg, level: LogLevels = LogLevels.INFO, frame=None) -> None:
    # 总是写入文件（直接写入，不经过stdout重定向）
    _writeToFile(msg, level, frame)

    # 控制台输出仅当级别足够时
    if level.value >= LOG_MIN_LEVEL:
        _printFormatted(msg, level, frame)


def _writeToFile(msg, level, frame):
    msg = re.sub(r"\033\[[0-9]{1,}m", "", msg)
    logFile = os.path.join("log", f"{getCurrTimeInFmt(fmt='%y-%m-%d')}.log")
    absPath = os.path.abspath(logFile)
    parentFolder = os.path.dirname(absPath)
    if not os.path.exists(parentFolder):
        os.makedirs(parentFolder)

    # 获取格式化日志内容（不含ANSI颜色代码）
    logContent = _formatForFile(msg, level, frame)

    with open(absPath, "a", encoding="utf-8-sig") as f:
        f.write(logContent + "\n")


def _formatFilePath(fileName: str, lineNo: int) -> str:
    filePath = os.path.relpath(fileName, ROOT_DIR)
    lineNoStr: str = str(lineNo)
    fileContext: str = f"{filePath}:{lineNoStr}"
    fileContextReserve: int = getConfig("log_filepath_reserve", 35)
    if len(fileContext) > fileContextReserve:
        fileContextReserve = len(fileContext)
        setConfig("log_filepath_reserve", fileContextReserve)
    fileContext: str = f"{fileContext:{fileContextReserve}}"

    return fileContext


def _formatForFile(msg, level, frame):
    if not frame:
        frame = inspect.stack()[2]

    # 时间部分
    currTime = f"{getCurrTime():19}"

    # 文件路径部分
    fileContext = _formatFilePath(frame.filename, frame.lineno)

    # 日志级别
    levelStr = f"{level.name:8}"

    # 组合完整日志行
    return f"{currTime} {fileContext} {levelStr} {msg}"


def _printFormatted(msg, level, frame):
    color: str = LOG_LEVEL_AND_COLOR_MATCH.get(level, ANSIColors.COLOR_RESET)

    # 时间部分固定19字符宽度
    currTimeStr: str = _colorize(f"{getCurrTime():19}", ANSIColors.COLOR_BRIGHT_BLUE) + " "

    # 文件路径部分完整显示，固定50字符宽度
    if not frame:
        frame = inspect.stack()[2]

    # 日志级别固定8字符宽度
    levelStr: str = italicFont(boldFont(_colorize(f"{level.name:>8}" + " " * 4, color)))

    fileContext: str = _formatFilePath(frame.filename, frame.lineno)

    print(f"{currTimeStr} {fileContext} {levelStr} {msg}")


def loggerPrintList(dataList: list) -> None:
    if not isinstance(dataList, list):
        loggerPrint("Not a list.", frame=inspect.stack()[1], level=LogLevels.WARNING)
        return
    if dataList is not None and dataList != []:
        for item in dataList:
            if isinstance(item, dict):
                loggerPrintDict(item)
            else:
                # 向上回溯一层栈帧再打印
                loggerPrint(f"{item}", frame=inspect.stack()[1], level=LogLevels.DEBUG)


def loggerPrintDict(dataDict: dict) -> None:
    if not isinstance(dataDict, dict):
        loggerPrint("Not a dict.", frame=inspect.stack()[1], level=LogLevels.WARNING)
        return
    if dataDict is not None and dataDict != {}:
        for key, value in dataDict.items():
            loggerPrint(f"{key}: {value}", frame=inspect.stack()[1], level=LogLevels.DEBUG)


def _colorize(msg: str, color: ANSIColors) -> str:
    colorResetList: list = list(color.value)
    colorResetList.insert(1, "/")
    return f"{color.value}{msg}{''.join(colorResetList)}"


def _stylize(msg: str, style: ANSIStyles) -> str:
    styleResetList = list(style.value)
    styleResetList.insert(1, "/")
    return f"{style.value}{msg}{''.join(styleResetList)}"


def boldFont(msg: str) -> str:
    return _stylize(msg, ANSIStyles.STYLE_BOLD)


def italicFont(msg: str) -> str:
    return _stylize(msg, ANSIStyles.STYLE_ITALIC)


if __name__ == "__main__":
    loggerPrint("haha", level=LogLevels.INFO)
