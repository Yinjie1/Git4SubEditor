"""Command-line interface for git4subeditor."""

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from git4subeditor import __version__
from git4subeditor.gitformat import export_sub, pack_sub
from git4subeditor.l10n import (
    SUPPORTED_LANGUAGES,
    configured_language,
    resolve_language,
    set_language,
    t,
)
from git4subeditor.subfile import SubFileError, unpack_sub
from git4subeditor.utils import format_message, print_banner
from git4subeditor.workspace import (
    IGNORE_PATTERNS,
    InitializeError,
    SubmarineEntry,
    initialize_project,
    load_workspace_info,
    print_submarine_paths,
    read_config_root,
)


class _ArgumentParser(argparse.ArgumentParser):
    """Argument parser with localized help headings."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)  # type: ignore
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

    sub = subparsers.add_parser(
        "sub",
        help=t("command.sub"),
    )
    sub.add_argument(
        "--tree",
        action="store_true",
        help=t("arg.tree"),
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


def _confirm_submarines(
    registered: tuple[SubmarineEntry, ...],
    pending: tuple[SubmarineEntry, ...],
) -> bool:
    """Show pending submarine registry changes and ask to apply them."""
    if registered:
        print(t("init.registered_header"))
        for entry in registered:
            print(f"  {entry.name}: {entry.path}")
    print(t("init.pending_header"))
    for entry in pending:
        print(f"  {entry.name}: {entry.path}")
    try:
        answer: str = input(t("prompt.submarines"))
    except EOFError:
        print()
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


def _load_registry() -> dict[Path, _SubmarineEntry] | None:
    """Load submarine entries from the current directory project config.

    Returns:
        A mapping from resolved ``.sub`` paths to registry entries, or None
        when ``git4subeditor.xml`` does not exist.

    Raises:
        SubFileError: If the configuration cannot be read or parsed.
    """
    root: ET.Element | None = read_config_root()
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
    if args.command == "sub":
        try:
            info = load_workspace_info()
        except SubFileError as exc:
            print(format_message(str(exc), label="error"), file=sys.stderr)
            return 1
        if info is None:
            print(t("repl.workspace_missing"))
            return 1
        print_submarine_paths(info, tree=args.tree)
        return 0

    if args.command == "init":
        if show_banner:
            print_banner(__version__)
        selected_language: str | None = None
        if configured_language() is None:
            selected_language = _prompt_language()
            set_language(selected_language)
        try:
            result = initialize_project(
                language=selected_language,
                confirm_submarines=_confirm_submarines,
            )
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
        if result.submarines_updated and result.submarines:
            print(t("init.registered", count=len(result.submarines)))
        elif not result.submarines_updated:
            print(t("init.submarines_skipped"))
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
        from git4subeditor.repl import run

        return run()
    args: argparse.Namespace = build_parser().parse_args(arguments)
    return _run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
