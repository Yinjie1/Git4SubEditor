"""Command-line interface for git4subeditor."""

import argparse
import sys
from pathlib import Path

from git4subeditor import __version__
from git4subeditor.gitformat import export_sub, pack_sub
from git4subeditor.subfile import SubFileError, unpack_sub

_COMMANDS: tuple[str, ...] = ("unpack", "export", "pack")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="git4subeditor",
        description=(
            "Convert Barotrauma .sub files to and from Git-friendly XML bundles."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="command",
    )

    unpack = subparsers.add_parser(
        "unpack",
        help="extract raw XML from .sub files",
    )
    _add_inputs(unpack, "one or more .sub files")
    unpack.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="output directory, defaults to each input file's directory",
    )
    unpack.add_argument(
        "--encoding",
        default=None,
        help="force an XML encoding instead of auto-detecting UTF-8/UTF-16",
    )
    unpack.add_argument(
        "--stdout",
        action="store_true",
        help="print XML to stdout instead of writing a file",
    )
    unpack.add_argument(
        "--no-validate",
        action="store_true",
        help="skip the XML well-formedness check",
    )
    _add_force(unpack)

    export = subparsers.add_parser(
        "export",
        help="export a .sub file as canonical XML plus a preview image",
    )
    _add_inputs(export, "one or more .sub files")
    export.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="output directory, defaults to each input file's directory",
    )
    export.add_argument(
        "--sort-attributes",
        action="store_true",
        help="sort XML attributes alphabetically for more stable diffs",
    )
    _add_force(export)

    pack = subparsers.add_parser(
        "pack",
        help="pack an exported XML file back into a .sub file",
    )
    _add_inputs(pack, "one or more exported XML files")
    pack.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "output .sub file, or an existing directory; defaults to the XML "
            "file's directory"
        ),
    )
    pack.add_argument(
        "--sort-attributes",
        action="store_true",
        help="sort XML attributes alphabetically before packing",
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
        help="overwrite existing output files without prompting",
    )


def _confirm_overwrite(path: Path) -> bool:
    """Ask whether an existing export target may be overwritten."""
    try:
        answer = input(f"{path} already exists. Overwrite? [y/N] ")
    except EOFError:
        return False
    return answer.strip().casefold() == "y"


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Optional argument list for testing. Defaults to sys.argv[1:].

    Returns:
        Process exit code: 0 on success, 1 if any input failed, 2 on bad usage.
    """
    raw_args: list[str] = list(sys.argv[1:] if argv is None else argv)
    if raw_args and not raw_args[0].startswith("-") and raw_args[0] not in _COMMANDS:
        # Keep the original `git4subeditor file.sub` form working.
        raw_args.insert(0, "unpack")

    args = build_parser().parse_args(raw_args)

    if args.command == "unpack" and args.stdout and len(args.inputs) > 1:
        print("error: --stdout accepts only one input file", file=sys.stderr)
        return 2

    if (
        args.command == "pack"
        and args.output is not None
        and len(args.inputs) > 1
        and not args.output.is_dir()
    ):
        print(
            "error: --output must be an existing directory when packing multiple files",
            file=sys.stderr,
        )
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
                        print(f"skipped: {xml_path}")
                        continue
                    force = True
                result = export_sub(
                    src,
                    args.output_dir,
                    force=force,
                    sort_attributes=args.sort_attributes,
                )
                preview = (
                    f", preview: {result.preview_path.name}"
                    if result.preview_path is not None
                    else ", no preview"
                )
                print(f"{src.name} -> {result.xml_path}{preview}")
            else:
                dst = pack_sub(
                    src,
                    args.output,
                    sort_attributes=args.sort_attributes,
                )
                print(f"{src.name} -> {dst}")
        except SubFileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
