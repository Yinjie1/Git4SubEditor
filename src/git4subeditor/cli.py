"""Command-line interface for git4subeditor."""

import argparse
import shlex
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from git4subeditor import __version__
from git4subeditor.gitformat import export_sub, pack_sub
from git4subeditor.initialize import (
    IGNORE_PATTERNS,
    InitializeError,
    initialize_project,
)
from git4subeditor.l10n import (
    SUPPORTED_LANGUAGES,
    configured_language,
    resolve_language,
    set_language,
    t,
)
from git4subeditor.subfile import SubFileError, unpack_sub
from git4subeditor.utils import format_message, print_banner


class _ArgumentParser(argparse.ArgumentParser):
    """Argument parser with localized help headings."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", help=t("arg.help"))
        self._positionals.title = t("help.positionals")
        self._optionals.title = t("help.options")

    def format_usage(self) -> str:
        """Return usage text with a localized prefix."""
        return super().format_usage().replace("usage: ", t("help.usage"), 1)

    def format_help(self) -> str:
        """Return help text with a localized usage prefix."""
        return super().format_help().replace("usage: ", t("help.usage"), 1)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = _ArgumentParser(
        prog="git4subeditor",
        description=t("app.description"),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help=t("arg.version"),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar=t("metavar.command"),
    )

    subparsers.add_parser(
        "init",
        help=t("command.init"),
    )

    unpack = subparsers.add_parser(
        "unpack",
        help=t("command.unpack"),
    )
    _add_inputs(unpack, t("arg.inputs.sub"))
    unpack.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help=t("arg.output_dir"),
    )
    unpack.add_argument(
        "--encoding",
        default=None,
        help=t("arg.encoding"),
    )
    unpack.add_argument(
        "--stdout",
        action="store_true",
        help=t("arg.stdout"),
    )
    unpack.add_argument(
        "--no-validate",
        action="store_true",
        help=t("arg.no_validate"),
    )
    _add_force(unpack)

    export = subparsers.add_parser(
        "export",
        help=t("command.export"),
    )
    _add_inputs(export, t("arg.inputs.sub"))
    export.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help=t("arg.output_dir"),
    )
    export.add_argument(
        "--sort-attributes",
        action="store_true",
        help=t("arg.sort_attributes"),
    )
    _add_force(export)

    pack = subparsers.add_parser(
        "pack",
        help=t("command.pack"),
    )
    _add_inputs(pack, t("arg.inputs.xml"))
    pack.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=t("arg.output"),
    )
    pack.add_argument(
        "--sort-attributes",
        action="store_true",
        help=t("arg.sort_attributes_pack"),
    )

    return parser


def _add_inputs(
    parser: argparse.ArgumentParser,
    help_text: str,
) -> None:
    """Add the positional input list to a subcommand parser."""
    parser.add_argument("inputs", nargs="+", type=Path, help=help_text)


def _add_force(parser: argparse.ArgumentParser) -> None:
    """Add the shared --force option to a subcommand parser."""
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help=t("arg.force"),
    )


def _confirm_overwrite(path: Path) -> bool:
    """Ask whether an existing export target may be overwritten."""
    try:
        answer = input(t("prompt.overwrite", path=path))
    except EOFError:
        return False
    return answer.strip().casefold() == "y"


def _prompt_language() -> str:
    """Ask for the project language in Chinese, English, and Russian."""
    print("请选择语言 / Please select a language / Выберите язык:")
    print("  cn - 中文")
    print("  en - English")
    print("  ru - Русский")
    try:
        answer: str = input("选择 / Select / Выберите [cn/en/ru] (default: en): ")
    except EOFError:
        return "en"
    language: str = answer.strip().lower()
    return language if language in SUPPORTED_LANGUAGES else "en"


@dataclass(frozen=True, slots=True)
class _SubmarineEntry:
    """A submarine entry read from the project configuration.

    Attributes:
        name: Registered submarine name.
        path: Submarine path relative to the Git repository.
        preview_path: Resolved preview image path, or None when no preview is
            configured.
    """

    name: str
    path: str
    preview_path: Path | None = None


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


def _read_config_root() -> ET.Element | None:
    """Read the current directory project configuration root.

    Returns:
        The ``git4subeditor`` element, or None when the configuration does not
        exist.

    Raises:
        SubFileError: If the configuration cannot be read or parsed.
    """
    config_path: Path = Path.cwd() / "git4subeditor.xml"
    try:
        return ET.parse(config_path).getroot()
    except FileNotFoundError:
        return None
    except (OSError, ET.ParseError) as exc:
        raise SubFileError(
            t("err.invalid_config", path=config_path, error=exc)
        ) from exc


def _load_registry() -> dict[Path, _SubmarineEntry] | None:
    """Load submarine entries from the current directory project config.

    Returns:
        A mapping from resolved ``.sub`` paths to registry entries, or None
        when ``git4subeditor.xml`` does not exist.

    Raises:
        SubFileError: If the configuration cannot be read or parsed.
    """
    root: ET.Element | None = _read_config_root()
    if root is None:
        return None
    config_path: Path = Path.cwd() / "git4subeditor.xml"

    repository_text: str = (root.findtext("gitRepo") or "").strip()
    repository_root: Path = (config_path.parent / repository_text).resolve()
    registry: dict[Path, _SubmarineEntry] = {}
    for entry in root.findall("./submarines/submarine"):
        path_text: str = (entry.get("path") or "").strip()
        if not path_text:
            continue
        sub_path: Path = (repository_root / Path(path_text)).resolve()
        preview_text: str = (entry.get("preview") or "").strip()
        preview_path: Path | None = (
            (repository_root / Path(preview_text)).resolve() if preview_text else None
        )
        registry[sub_path] = _SubmarineEntry(
            name=entry.get("name") or sub_path.stem,
            path=path_text,
            preview_path=preview_path,
        )
    return registry


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


def _path_basename(path_text: str) -> str:
    """Return the final component of a configured path."""
    return Path(path_text).name


def _print_tree_children(entries: list[_TreeEntry], prefix: str) -> None:
    """Print tree entries below one directory level."""
    files: list[_SubmarineEntry] = [
        submarine for directories, submarine in entries if not directories
    ]
    directory_names: list[str] = list(
        dict.fromkeys(directories[0] for directories, _ in entries if directories)
    )

    total: int = len(files) + len(directory_names)
    index: int = 0
    for submarine in files:
        index += 1
        connector: str = "└── " if index == total else "├── "
        filename: str = _path_basename(submarine.path)
        print(f"{prefix}{connector}{submarine.name}: {filename}")

    for directory_name in directory_names:
        index += 1
        connector = "└── " if index == total else "├── "
        directory_text: str = format_message(directory_name, color="light_blue")
        print(f"{prefix}{connector}{directory_text}")
        child_prefix: str = prefix + ("    " if index == total else "│   ")
        children: list[_TreeEntry] = [
            (directories[1:], submarine)
            for directories, submarine in entries
            if directories and directories[0] == directory_name
        ]
        _print_tree_children(children, child_prefix)


def _print_submarine_tree(info: _WorkspaceInfo) -> None:
    """Print registered submarines as a directory tree."""
    if not info.submarines:
        return

    root_label: str = info.git_repo or "."
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
    print(format_message(root_label, color="light_blue"))
    _print_tree_children(entries, "")


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
    _print_submarine_tree(info)


def _workspace_prompt(info: _WorkspaceInfo | None) -> str:
    """Return the interactive prompt for the current workspace."""
    prefix: str = format_message("g4s", color="light_blue")
    if info is None:
        return f"{prefix}> "
    return f"{prefix}:{format_message(info.project_name, color='green')}> "


def _require_registered(
    path: Path,
    registry: dict[Path, _SubmarineEntry] | None,
) -> _SubmarineEntry | None:
    """Return the registry entry for a submarine or fail when missing.

    Args:
        path: Input ``.sub`` file or exported ``.xml`` file.
        registry: Registry returned by ``_load_registry``, or None when no
            project configuration exists.

    Returns:
        The matching registry entry, or None when no configuration exists.

    Raises:
        SubFileError: If a configuration exists but the submarine is not
            registered.
    """
    if registry is None:
        return None
    target: Path = path.resolve()
    sub_path: Path = (
        target.with_suffix(".sub") if target.suffix.lower() == ".xml" else target
    )
    try:
        return registry[sub_path]
    except KeyError:
        raise SubFileError(t("err.not_registered", path=path)) from None


def _registry_preview_override(
    entry: _SubmarineEntry | None,
) -> bytes | None:
    """Return the preview image configured for a registered submarine.

    Args:
        entry: Registered submarine entry, or None when no configuration
            exists.

    Returns:
        Preview image bytes, or None when no registered preview should be
        used. A read failure prints a localized warning and also returns None
        so packing falls back to the XML ``preview`` link.
    """
    if entry is None or entry.preview_path is None:
        return None
    try:
        return entry.preview_path.read_bytes()
    except OSError:
        print(
            format_message(
                t("warning.registry_preview_failed", name=entry.name),
                label="warning",
            ),
            file=sys.stderr,
        )
        return None


def _run_command(
    args: argparse.Namespace,
    *,
    show_banner: bool = True,
) -> int:
    """Execute a parsed command and return its exit code.

    Args:
        args: Parsed command arguments.
        show_banner: Whether ``init`` should print the startup banner.

    Returns:
        Process exit code: 0 on success, 1 if any input failed, 2 on bad usage.
    """
    if args.command == "init":
        if show_banner:
            print_banner(__version__)
        selected_language: str | None = None
        if configured_language() is None:
            selected_language = _prompt_language()
            set_language(selected_language)
        try:
            result = initialize_project(language=selected_language)
        except InitializeError as exc:
            print(format_message(str(exc), label="error"), file=sys.stderr)
            return 1
        except OSError as exc:
            print(
                format_message(t("err.init", error=exc), label="error"),
                file=sys.stderr,
            )
            return 1
        if selected_language is not None:
            print(format_message(t("init.language_set"), color="green"))
        if not result.current_git_repository:
            if result.git_repository_path:
                print(
                    format_message(
                        t(
                            "warning.current_not_repo",
                            path=result.git_repository_path,
                        ),
                        label="warning",
                    ),
                    file=sys.stderr,
                )
            else:
                print(
                    format_message(t("warning.no_repo"), label="warning"),
                    file=sys.stderr,
                )
        if result.upper_git_repository_path is not None:
            print(
                format_message(
                    t(
                        "warning.upper_repo",
                        path=result.upper_git_repository_path,
                    ),
                    label="warning",
                ),
                file=sys.stderr,
            )
        for change in result.submarine_path_changes:
            print(
                format_message(
                    t(
                        "warning.submarine_path_changed",
                        name=change.name,
                        old_path=change.old_path,
                        new_path=change.new_path,
                    ),
                    label="warning",
                ),
                file=sys.stderr,
            )
        patterns: str = ", ".join(result.added)
        all_patterns: str = ", ".join(IGNORE_PATTERNS)
        if result.gitignore_created:
            print(
                t(
                    "init.created_gitignore",
                    name=result.gitignore_path.name,
                    patterns=patterns,
                )
            )
        elif result.added:
            print(
                t(
                    "init.updated_gitignore",
                    name=result.gitignore_path.name,
                    patterns=patterns,
                )
            )
        else:
            print(
                t(
                    "init.gitignore_ok",
                    name=result.gitignore_path.name,
                    patterns=all_patterns,
                )
            )
        if result.config_created:
            print(t("init.config_created", name=result.config_path.name))
        elif result.config_updated:
            print(t("init.config_updated", name=result.config_path.name))
        else:
            print(t("init.config_exists", name=result.config_path.name))
        if result.submarines:
            print(t("init.registered", count=len(result.submarines)))
        if result.git_repository_path:
            print(t("status.git_repo", path=result.git_repository_path))
        return 0

    if args.command == "unpack" and args.stdout and len(args.inputs) > 1:
        print(
            format_message(t("err.stdout_single"), label="error"),
            file=sys.stderr,
        )
        return 2

    if (
        args.command == "pack"
        and args.output is not None
        and len(args.inputs) > 1
        and not args.output.is_dir()
    ):
        print(
            format_message(t("err.output_multi"), label="error"),
            file=sys.stderr,
        )
        return 2

    registry: dict[Path, _SubmarineEntry] | None = None
    if args.command in {"export", "pack"}:
        try:
            registry = _load_registry()
        except SubFileError as exc:
            print(format_message(str(exc), label="error"), file=sys.stderr)
            return 1

    errors: int = 0
    for src in args.inputs:
        try:
            if args.command == "unpack":
                unpack_sub(
                    src,
                    args.output_dir,
                    encoding=args.encoding,
                    force=args.force,
                    to_stdout=args.stdout,
                    validate=not args.no_validate,
                )
            elif args.command == "export":
                _require_registered(src, registry)
                force: bool = args.force
                target_dir: Path = (
                    args.output_dir if args.output_dir is not None else src.parent
                )
                xml_path: Path = target_dir / f"{src.stem}.xml"
                if not force and xml_path.exists():
                    if not _confirm_overwrite(xml_path):
                        print(t("status.skipped", path=xml_path))
                        continue
                    force = True
                result = export_sub(
                    src,
                    args.output_dir,
                    force=force,
                    sort_attributes=args.sort_attributes,
                )
                if result.preview_path is not None:
                    print(
                        t(
                            "status.export_preview",
                            src=src.name,
                            xml=result.xml_path,
                            preview=result.preview_path.name,
                        )
                    )
                else:
                    print(
                        t(
                            "status.export_no_preview",
                            src=src.name,
                            xml=result.xml_path,
                        )
                    )
            else:
                entry: _SubmarineEntry | None = _require_registered(src, registry)
                preview_override: bytes | None = _registry_preview_override(entry)
                dst = pack_sub(
                    src,
                    args.output,
                    preview_override=preview_override,
                    sort_attributes=args.sort_attributes,
                )
                print(t("status.pack", src=src.name, dst=dst))
        except SubFileError as exc:
            print(format_message(str(exc), label="error"), file=sys.stderr)
            errors += 1

    return 1 if errors else 0


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


def _run_interactive() -> int:
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
    print(t("repl.commands"))
    print("  init")
    print("  export <file.sub> [-o DIR] [-f]")
    print("  pack <file.xml> [-o FILE]")
    print("  unpack <file.sub> [-o DIR]")
    print("  help")
    print("  exit")
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
        if name in {"help", "?"}:
            print(build_parser().format_help(), end="")
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


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Optional argument list for testing. Defaults to sys.argv[1:].

    Returns:
        Process exit code: 0 on success, 1 if any input failed, 2 on bad usage.
    """
    set_language(resolve_language())
    arguments: list[str] = sys.argv[1:] if argv is None else argv
    if not arguments:
        return _run_interactive()
    args: argparse.Namespace = build_parser().parse_args(arguments)
    return _run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
