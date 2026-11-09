"""Miscellaneous console and project utilities."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TextIO

_COLORS: dict[str, str] = {
    "yellow": "\033[33m",
    "green": "\033[32m",
    "red": "\033[31m",
    "blue": "\033[34m",
    "light_blue": "\033[94m",
}
_RESET = "\033[0m"

_LABEL_COLORS: dict[str, str] = {
    "error": "red",
    "warning": "yellow",
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


def format_message(
    message: str,
    *,
    label: str | None = None,
    color: str | None = None,
) -> str:
    """Format text with an optional colored label.

    When ``label`` is given, the result is ``label: message`` and the label is
    colored according to ``color`` or the label defaults. Otherwise the whole
    message is colored with ``color``.

    Args:
        message: Message text.
        label: Optional label placed before the message.
        color: Optional color name such as ``red``, ``green``, or ``blue``.

    Returns:
        The formatted text.
    """
    if label is None:
        color_code: str | None = _COLORS.get(color) if color else None
        if color_code is None:
            return message
        return _colorize(message, color_code, sys.stdout)

    color_name: str | None = color or _LABEL_COLORS.get(label)
    color_code = _COLORS.get(color_name) if color_name else None
    label_text: str = label
    if color_code is not None:
        label_text = _colorize(label, color_code, sys.stderr)
    return f"{label_text}: {message}"


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
    """Print the banner, or a one-line fallback when the terminal is narrow.

    Args:
        version: Version text shown on the banner.
    """
    if sys.stdout is None:
        return
    lines: tuple[str, ...] = build_banner(version)
    columns: int = shutil.get_terminal_size(fallback=(80, 24)).columns
    try:
        if columns < max(len(line) for line in lines):
            print(f"Git4SubEditor by Yinjie {version}", end="\n")
            return
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


def open_path(path: Path) -> None:
    """Open a file with the default application.

    Args:
        path: File to open.
    """
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
