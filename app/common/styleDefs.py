from enum import StrEnum, IntEnum


# fmt: off
class ANSIColors(StrEnum):
    COLOR_RESET             = "[default]"
    COLOR_BRIGHT_RED        = "[bright_red]"
    COLOR_BRIGHT_GREEN      = "[bright_green]"
    COLOR_BRIGHT_YELLOW     = "[bright_yellow]"
    COLOR_BRIGHT_BLUE       = "[bright_blue]"
    COLOR_BRIGHT_MAGENTA    = "[bright_magenta]"

class ANSIStyles(StrEnum):
    STYLE_RESET             = "[default]"
    STYLE_BOLD              = "[bold]"
    STYLE_ITALIC            = "[italic]"
    STYLE_UNDERLINE         = "[underline]"
    STYLE_STRIKE            = "[strike]"

class ColorCode(IntEnum):
    # 参考: https://essentialsdocs.fandom.com/wiki/Messages#Text_colours
    BLUE = 1
    RED = 2
    GREEN = 3
    CYAN = 4
    MAGENTA = 5
    YELLOW = 6
    GRAY = 7
    WHITE = 8
    PURPLE = 9
    ORANGE = 10
    DARK_DEFAULT = 11
    LIGHT_DEFAULT = 12
# fmt: on
