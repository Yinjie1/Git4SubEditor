"""Command-line interface for git4subeditor."""

import argparse
import sys
import xml.etree.ElementTree as ET
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
from git4subeditor.utils import (
    format_error,
    format_success,
    format_warning,
    print_banner,
)


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

    def error(self, message: str) -> None:
        """Print a colorized argument error and exit."""
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: {format_error(message)}\n")


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


def _registry_preview_override(xml_path: Path) -> bytes | None:
    """Return the registry preview configured for an exported XML file.

    The project configuration is read from the current working directory. A
    matching ``<submarine>`` entry is found by resolving its ``path`` relative
    to the configured Git repository root and comparing the ``.xml`` form with
    the input file. When the entry has a ``preview`` attribute, that image is
    read and returned. A read failure prints a localized warning and returns
    None so that packing falls back to the XML ``preview`` link.

    Args:
        xml_path: Exported XML file passed to ``pack``.

    Returns:
        Preview image bytes, or None when no registry preview should be used.
    """
    config_path: Path = Path.cwd() / "git4subeditor.xml"
    try:
        root: ET.Element = ET.parse(config_path).getroot()
    except (OSError, ET.ParseError):
        return None

    repository_text: str = (root.findtext("gitRepo") or "").strip()
    repository_root: Path = (config_path.parent / repository_text).resolve()
    target: Path = xml_path.resolve()

    for entry in root.findall("./submarines/submarine"):
        path_text: str = (entry.get("path") or "").strip()
        if not path_text:
            continue
        entry_sub: Path = repository_root / Path(path_text)
        if entry_sub.with_suffix(".xml") != target:
            continue

        preview_text: str | None = entry.get("preview")
        if preview_text is None:
            return None

        preview_path: Path = repository_root / Path(preview_text)
        try:
            return preview_path.read_bytes()
        except OSError:
            print(
                format_warning(
                    t(
                        "warning.registry_preview_failed",
                        name=entry.get("name") or entry_sub.stem,
                    )
                ),
                file=sys.stderr,
            )
            return None

    return None


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Optional argument list for testing. Defaults to sys.argv[1:].

    Returns:
        Process exit code: 0 on success, 1 if any input failed, 2 on bad usage.
    """
    set_language(resolve_language())
    args = build_parser().parse_args(argv)

    if args.command == "init":
        print_banner(__version__)
        selected_language: str | None = None
        if configured_language() is None:
            selected_language = _prompt_language()
            set_language(selected_language)
        try:
            result = initialize_project(language=selected_language)
        except InitializeError as exc:
            print(format_error(str(exc)), file=sys.stderr)
            return 1
        except OSError as exc:
            print(
                format_error(t("err.init", error=exc)),
                file=sys.stderr,
            )
            return 1
        if selected_language is not None:
            print(format_success(t("init.language_set")))
        if not result.current_git_repository:
            if result.git_repository_path:
                print(
                    format_warning(
                        t(
                            "warning.current_not_repo",
                            path=result.git_repository_path,
                        )
                    ),
                    file=sys.stderr,
                )
            else:
                print(
                    format_warning(t("warning.no_repo")),
                    file=sys.stderr,
                )
        if result.upper_git_repository_path is not None:
            print(
                format_warning(
                    t(
                        "warning.upper_repo",
                        path=result.upper_git_repository_path,
                    )
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
        print(format_error(t("err.stdout_single")), file=sys.stderr)
        return 2

    if (
        args.command == "pack"
        and args.output is not None
        and len(args.inputs) > 1
        and not args.output.is_dir()
    ):
        print(format_error(t("err.output_multi")), file=sys.stderr)
        return 2

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
                preview_override: bytes | None = _registry_preview_override(src)
                dst = pack_sub(
                    src,
                    args.output,
                    preview_override=preview_override,
                    sort_attributes=args.sort_attributes,
                )
                print(t("status.pack", src=src.name, dst=dst))
        except SubFileError as exc:
            print(format_error(str(exc)), file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
