"""Command-line interface for git4subeditor."""

import argparse
import sys
from pathlib import Path

from git4subeditor.subfile import SubFileError, unpack_sub


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract Barotrauma .sub files (gzip-compressed XML).",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="one or more .sub files",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="output directory, defaults to each input file's directory",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="force an XML encoding instead of auto-detecting UTF-8/UTF-16",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print XML to stdout instead of writing a file",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="skip the XML well-formedness check",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite existing output files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Optional argument list for testing. Defaults to sys.argv[1:].

    Returns:
        Process exit code: 0 on success, 1 if any input failed, 2 on bad usage.
    """
    args = build_parser().parse_args(argv)

    if args.stdout and len(args.inputs) > 1:
        print("error: --stdout accepts only one input file", file=sys.stderr)
        return 2

    errors: int = 0
    for src in args.inputs:
        try:
            unpack_sub(
                src,
                args.output_dir,
                encoding=args.encoding,
                force=args.force,
                to_stdout=args.stdout,
                validate=not args.no_validate,
            )
        except SubFileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
