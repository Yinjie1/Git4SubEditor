"""Interactive command loop for git4subeditor."""

import argparse
import re
import shlex
import shutil
import sys
from functools import partial
from pathlib import Path
from typing import Any, cast

from git4subeditor import __release_date__, __version__
from git4subeditor.cli import _run_command, build_parser
from git4subeditor.l10n import resolve_language, set_language, t
from git4subeditor.subfile import SubFileError
from git4subeditor.utils import format_message, open_path, print_banner
from git4subeditor.workspace import (
    WorkspaceInfo,
    load_workspace_info,
    update_status,
)

_COMMANDS: tuple[str, ...] = (
    "init",
    "export",
    "pack",
    "unpack",
    "show",
    "config",
    "github",
)
_HELP_TAG = re.compile(r"<(title|cmd)>(.*?)</\1>")


def _render_help(text: str) -> str:
    """Colorize help document markers."""

    def replace(match: re.Match[str]) -> str:
        color: str = "light_blue" if match.group(1) == "title" else "green"
        return format_message(match.group(2), color=color)

    return _HELP_TAG.sub(replace, text)


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
        ("show [--tree] [xml]", t("repl.command.show")),
        ("export <file.sub> [-o DIR]", t("repl.command.export")),
        ("pack <file.xml> [-o FILE]", t("repl.command.pack")),
        ("unpack <file.sub> [-o DIR]", t("repl.command.unpack")),
        ("config", t("repl.command.config")),
        ("github", t("repl.command.github")),
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
    info.print_paths()

    groups: dict[str, list[str]] = {}
    for submarine in info.submarines:
        groups.setdefault(Path(submarine.path).stem.casefold(), []).append(
            submarine.path
        )
    duplicates: list[list[str]] = [paths for paths in groups.values() if len(paths) > 1]
    if duplicates:
        paths_text: str = "\n".join(
            f"  {path}" for group in duplicates for path in group
        )
        print(
            format_message(
                t("warning.duplicate_registered", paths=paths_text),
                label="warning",
            )
        )


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

    print_banner(
        f"{__version__} ({__release_date__})",
        update_status(__version__),
    )
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
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.history import FileHistory
    except ImportError:
        pass
    else:

        class _CommandCompleter(Completer):
            """Complete REPL command names."""

            def get_completions(
                self,
                document: Any,
                complete_event: Any,
            ) -> Any:
                """Yield completions for the first token."""
                text: str = document.text_before_cursor
                if " " in text:
                    return
                for command in _COMMANDS:
                    if command.startswith(text):
                        yield Completion(command, start_position=-len(text))

        session = PromptSession(
            history=FileHistory(str(Path.cwd() / "history")),
            completer=_CommandCompleter(),
            complete_while_typing=False,
        )
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
        if name == "?":
            print(_render_help(t("repl.help")), end="")
            continue
        if name == "github":
            open_path("https://github.com/Yinjie1/Git4SubEditor")
            continue

        try:
            args: argparse.Namespace = build_parser().parse_args(tokens)
        except SystemExit:
            continue
        except KeyboardInterrupt:
            print()
            continue

        if args.command == "init":
            print_banner(
                f"{__version__} ({__release_date__})",
                update_status(__version__, force=True),
                compact=True,
            )

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
