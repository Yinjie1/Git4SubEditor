"""Interactive command loop for git4subeditor."""

import argparse
import shlex
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, cast

from git4subeditor import __version__
from git4subeditor.cli import (
    _read_config_root,
    _run_command,
    _SubmarineEntry,
    build_parser,
)
from git4subeditor.l10n import resolve_language, set_language, t
from git4subeditor.subfile import SubFileError
from git4subeditor.utils import format_message, print_banner


@dataclass(frozen=True, slots=True)
class _WorkspaceInfo:
    """Project information shown when the interactive mode starts.

    Attributes:
        project_name: Project name from ``git4subeditor.xml``.
        git_repo: Git repository path relative to the workspace.
        mod_root: MOD root path relative to the workspace.
        submarines: Registered submarines in configuration order.
    """

    project_name: str
    git_repo: str
    mod_root: str
    submarines: tuple[_SubmarineEntry, ...]


type _TreeEntry = tuple[list[str], _SubmarineEntry]


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
        ("export <file.sub> [-o DIR] [-f]", t("repl.command.export")),
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


def _load_workspace_info() -> _WorkspaceInfo | None:
    """Load workspace details from the current directory project config.

    Returns:
        Workspace details, or None when ``git4subeditor.xml`` does not exist.

    Raises:
        SubFileError: If the configuration cannot be read or parsed.
    """
    root: ET.Element | None = _read_config_root()
    if root is None:
        return None

    project_name: str = (root.findtext("projectName") or "").strip()
    git_repo: str = (root.findtext("gitRepo") or "").strip() or "."
    mod_root: str = (root.findtext("modRoot") or "").strip() or "."
    submarines: list[_SubmarineEntry] = []
    for entry in root.findall("./submarines/submarine"):
        path_text: str = (entry.get("path") or "").strip()
        if not path_text:
            continue
        name_text: str = (entry.get("name") or "").strip() or Path(path_text).stem
        submarines.append(_SubmarineEntry(name=name_text, path=path_text))

    return _WorkspaceInfo(
        project_name=project_name or Path.cwd().name,
        git_repo=git_repo,
        mod_root=mod_root,
        submarines=tuple(submarines),
    )


def _split_path_text(path_text: str) -> list[str]:
    """Split a configured path into components."""
    parts: tuple[str, ...] = Path(path_text).parts
    if not parts:
        return ["."]
    if path_text.startswith(("./", ".\\")):
        return [".", *parts]
    return list(parts)


def _relative_display(path: Path) -> str:
    """Return a path relative to the current directory in POSIX form."""
    relative: Path = path.resolve().relative_to(Path.cwd().resolve(), walk_up=True)
    return relative.as_posix()


def _print_submarine_paths(info: _WorkspaceInfo, tree: bool = True) -> None:
    """Print registered submarine paths, optionally as a directory tree.

    Args:
        info: Workspace information containing registered submarines.
        tree: Whether to print a directory tree. When False, print paths in
            registration order.
    """
    if not info.submarines:
        return

    root_label: str = info.git_repo or "."
    root_path: Path = Path.cwd() / root_label
    if not tree:
        for submarine in info.submarines:
            path_text: str = _relative_display(root_path / submarine.path)
            print(f"{submarine.name}: {path_text}")
        return

    root_directories: list[str] = _split_path_text(root_label)
    entries: list[_TreeEntry] = []
    for submarine in info.submarines:
        parts: list[str] = _split_path_text(submarine.path)
        if not parts:
            continue
        directories: list[str] = parts[:-1]
        if directories[: len(root_directories)] == root_directories:
            directories = directories[len(root_directories) :]
        entries.append((directories, submarine))

    if not entries:
        return

    def print_children(
        children: list[_TreeEntry],
        prefix: str,
        parent: Path,
    ) -> None:
        """Print tree entries below one directory level."""
        files: list[_SubmarineEntry] = [
            submarine for directories, submarine in children if not directories
        ]
        directory_names: list[str] = list(
            dict.fromkeys(directories[0] for directories, _ in children if directories)
        )

        total: int = len(files) + len(directory_names)
        index: int = 0
        for submarine in files:
            index += 1
            connector: str = "└── " if index == total else "├── "
            filename: str = Path(submarine.path).name
            print(f"{prefix}{connector}{submarine.name}: {filename}")

        for directory_name in directory_names:
            index += 1
            connector = "└── " if index == total else "├── "
            directory_path: Path = parent / directory_name
            directory_text: str = format_message(
                _relative_display(directory_path),
                color="light_blue",
            )
            print(f"{prefix}{connector}{directory_text}")
            child_prefix: str = prefix + ("    " if index == total else "│   ")
            nested: list[_TreeEntry] = [
                (directories[1:], submarine)
                for directories, submarine in children
                if directories and directories[0] == directory_name
            ]
            print_children(nested, child_prefix, directory_path)

    print(format_message(_relative_display(root_path), color="light_blue"))
    print_children(entries, "", root_path)


def _print_workspace_info(info: _WorkspaceInfo | None) -> None:
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
    _print_submarine_paths(info)


def _workspace_prompt(info: _WorkspaceInfo | None) -> str:
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
        workspace: _WorkspaceInfo | None = _load_workspace_info()
    except SubFileError as exc:
        print(format_message(str(exc), label="error"), file=sys.stderr)
        return 1
    _print_workspace_info(workspace)
    print()
    _print_command_list()
    print()
    print(t("repl.hint"))
    prompt: str = _workspace_prompt(workspace)

    while True:
        try:
            line: str = input(prompt)
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
                _print_submarine_paths(workspace)
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
                workspace = _load_workspace_info()
            except SubFileError:
                pass
            else:
                prompt = _workspace_prompt(workspace)
