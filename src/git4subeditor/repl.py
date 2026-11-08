"""Interactive command loop for git4subeditor."""

import argparse
import shlex
import shutil
import sys
from functools import partial
from pathlib import Path
from typing import Any, cast

from git4subeditor import __version__
from git4subeditor.cli import _run_command, build_parser
from git4subeditor.l10n import resolve_language, set_language, t
from git4subeditor.subfile import SubFileError
from git4subeditor.utils import format_message, print_banner
from git4subeditor.workspace import (
    WorkspaceInfo,
    load_workspace_info,
    print_submarine_paths,
)


class _SummaryFormatter(argparse.HelpFormatter):
    """Use the usage color for positional command names."""

    def _format_action_invocation(self, action: argparse.Action) -> str:
        theme = cast(Any, self)._theme
        head, *options = action.dest.split(" [")
        parts: list[str] = [f"{theme.summary_action}{head}{theme.reset}"]
        for option in options:
            parts.append(
                f"[{theme.summary_action}{option.removesuffix(']')}{theme.reset}]"
            )
        return " ".join(parts)


def _print_command_list() -> None:
    """Print the interactive command list in argparse style."""
    commands: tuple[tuple[str, str], ...] = (
        ("init", t("repl.command.init")),
        ("export <file.sub> [-o DIR]", t("repl.command.export")),
        ("pack <file.xml> [-o FILE]", t("repl.command.pack")),
        ("unpack <file.sub> [-o DIR]", t("repl.command.unpack")),
        ("tree", t("repl.command.tree")),
        ("exit", t("repl.command.exit")),
    )
    columns: int = shutil.get_terminal_size(fallback=(80, 24)).columns
    max_command: int = max(len(syntax) for syntax, _ in commands)
    max_description: int = max(len(description) for _, description in commands)
    show_descriptions: bool = columns >= max(
        max_command + max_description + 6,
        max_command + 26,
    )
    parser = argparse.ArgumentParser(
        prog="",
        add_help=False,
        formatter_class=partial(_SummaryFormatter, max_help_position=40),
    )
    formatter = parser._get_formatter()
    formatter.start_section(t("repl.commands"))
    for syntax, description in commands:
        formatter.add_argument(
            argparse.Action(
                [],
                syntax,
                help=description if show_descriptions else None,
            )
        )
    formatter.end_section()
    print(formatter.format_help(), end="")


def _print_workspace_info(info: WorkspaceInfo | None) -> None:
    """Print the interactive workspace summary.

    Args:
        info: Loaded workspace information, or None when the workspace is not
            initialized.
    """
    if info is None:
        print(t("repl.workspace_missing"))
        return

    print(
        t(
            "repl.workspace",
            project=info.project_name,
            git_repo=info.git_repo,
            mod_root=info.mod_root,
        )
    )
    print(t("repl.cwd", path=Path.cwd().resolve()))
    print_submarine_paths(info)


def _workspace_prompt(info: WorkspaceInfo | None) -> str:
    """Return the interactive prompt for the current workspace."""
    prefix: str = format_message("g4s", color="light_blue")
    if info is None:
        return f"{prefix}> "
    return f"{prefix}:{format_message(info.project_name, color='green')}> "


def _split_interactive_line(line: str) -> list[str]:
    """Split one interactive command line without mangling Windows paths.

    Args:
        line: Raw text entered at the interactive prompt.

    Returns:
        Command tokens with matching outer quotes removed.

    Raises:
        ValueError: If the line contains an unmatched quote.
    """
    tokens: list[str] = shlex.split(line, posix=False)
    return [
        token[1:-1]
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'"
        else token
        for token in tokens
    ]


def run() -> int:
    """Run the interactive command loop.

    Returns:
        Process exit code.
    """
    if sys.stdin is None or not sys.stdin.isatty():
        print(
            format_message(t("repl.not_tty"), label="error"),
            file=sys.stderr,
        )
        return 2

    print_banner(__version__)
    print()
    try:
        workspace: WorkspaceInfo | None = load_workspace_info()
    except SubFileError as exc:
        print(format_message(str(exc), label="error"), file=sys.stderr)
        return 1
    _print_workspace_info(workspace)
    print()
    _print_command_list()
    print()
    print(t("repl.hint"))
    prompt: str = _workspace_prompt(workspace)
    session: Any = None
    ansi: Any = None
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.history import FileHistory
    except ImportError:
        pass
    else:
        session = PromptSession(history=FileHistory(str(Path.cwd() / "history")))
        ansi = ANSI

    while True:
        try:
            if session is None:
                line: str = input(prompt)
            else:
                line = session.prompt(ansi(prompt))
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue

        try:
            tokens: list[str] = _split_interactive_line(line)
        except ValueError as exc:
            print(
                format_message(t("repl.parse_error", error=exc), label="error"),
                file=sys.stderr,
            )
            continue
        if not tokens:
            continue

        name: str = tokens[0].casefold()
        if name in {"exit", "quit", "q"}:
            return 0
        if name == "tree":
            if workspace is None:
                print(t("repl.workspace_missing"))
            else:
                print_submarine_paths(workspace)
            continue

        try:
            args: argparse.Namespace = build_parser().parse_args(tokens)
        except SystemExit:
            continue
        except KeyboardInterrupt:
            print()
            continue

        try:
            code: int = _run_command(args, show_banner=False)
        except KeyboardInterrupt:
            print()
            continue
        if args.command == "init" and code == 0:
            set_language(resolve_language())
            try:
                workspace = load_workspace_info()
            except SubFileError:
                pass
            else:
                prompt = _workspace_prompt(workspace)
