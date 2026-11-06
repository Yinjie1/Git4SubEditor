"""Miscellaneous console and project utilities."""

import os
import shutil
import sys
from typing import TextIO

_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"

_LABEL_COLORS: dict[str, str] = {
    "error": _RED,
    "warning": _YELLOW,
}

_BANNER = """\
 ██████╗ ██╗████████╗    ██╗  ██╗
██╔════╝ ██║╚══██╔══╝    ██║  ██║
██║  ███╗██║   ██║       ███████║
██║   ██║██║   ██║       ╚════██║
╚██████╔╝██║   ██║            ██║
 ╚═════╝ ╚═╝   ╚═╝            ╚═╝

███████╗██╗   ██╗██████╗ ███████╗██████╗ ██╗████████╗ ██████╗ ██████╗
██╔════╝██║   ██║██╔══██╗██╔════╝██╔══██╗██║╚══██╔══╝██╔═══██╗██╔══██╗
███████╗██║   ██║██████╔╝█████╗  ██║  ██║██║   ██║   ██║   ██║██████╔╝
╚════██║██║   ██║██╔══██╗██╔══╝  ██║  ██║██║   ██║   ██║   ██║██╔══██╗
███████║╚██████╔╝██████╔╝███████╗██████╔╝██║   ██║   ╚██████╔╝██║  ██║
╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
"""


def format_message(message: str, *, label: str) -> str:
    """Format a message with a colored label.

    Args:
        message: Message text without the label prefix.
        label: Label text, for example ``warning`` or ``error``.

    Returns:
        The formatted message line.
    """
    color: str | None = _LABEL_COLORS.get(label)
    label_text: str = label
    if color is not None:
        label_text = _colorize(label, color, sys.stderr)
    return f"{label_text}: {message}"


def format_success(message: str) -> str:
    """Format a success message in green.

    The message is colored only when stdout is a terminal and ``NO_COLOR`` is
    not set.

    Args:
        message: Success text.

    Returns:
        The formatted success message.
    """
    return _colorize(message, _GREEN, sys.stdout)


def _colorize(text: str, color: str, stream: TextIO | None) -> str:
    """Wrap text in an ANSI color when the stream supports it."""
    if _supports_color(stream):
        return f"{color}{text}{_RESET}"
    return text


def build_banner(version: str) -> tuple[str, ...]:
    """Build the banner with author and version beside the first lines.

    Args:
        version: Version text shown on the second line.

    Returns:
        Banner lines with trailing spaces removed.
    """
    lines: list[str] = [line.rstrip() for line in _BANNER.splitlines()]
    text_column: int = max(len(lines[0]), len(lines[1])) + 4
    lines[0] = f"{lines[0]:<{text_column}}by Yinjie"
    lines[1] = f"{lines[1]:<{text_column}}{version}"
    return tuple(lines)


def print_banner(version: str) -> None:
    """Print the banner when the terminal is wide enough.

    Args:
        version: Version text shown on the second line.
    """
    if sys.stdout is None:
        return
    lines: tuple[str, ...] = build_banner(version)
    columns: int = shutil.get_terminal_size(fallback=(80, 24)).columns
    if columns < max(len(line) for line in lines):
        return
    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        pass


def _supports_color(stream: TextIO | None) -> bool:
    """Return whether a text stream supports ANSI color output."""
    if stream is None or "NO_COLOR" in os.environ:
        return False
    try:
        return stream.isatty()
    except AttributeError:
        return False
