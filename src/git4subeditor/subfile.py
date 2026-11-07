"""Read and extract Barotrauma submarine files.

A .sub file is gzip-compressed XML (magic bytes 1F 8B). Some files produced by
older tools may be plain XML. Both forms are supported.
"""

import gzip
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from git4subeditor.l10n import t
from git4subeditor.utils import format_message

GZIP_MAGIC: bytes = b"\x1f\x8b"


class SubFileError(Exception):
    """Raised when a submarine file cannot be read, extracted, or validated."""


def read_sub_bytes(path: Path) -> bytes:
    """Read the raw bytes of a .sub file.

    Args:
        path: Path to the .sub file.

    Returns:
        The raw file contents.

    Raises:
        SubFileError: If the file cannot be read.
    """
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SubFileError(t("err.read_file", path=path, error=exc)) from exc


def decompress_sub(data: bytes) -> bytes:
    """Decompress .sub data.

    Gzip content is detected by its magic bytes and decompressed. Any other
    content, such as plain XML, is returned unchanged.

    Args:
        data: Raw bytes read from a .sub file.

    Returns:
        The decompressed XML bytes.

    Raises:
        SubFileError: If gzip decompression fails.
    """
    if data.startswith(GZIP_MAGIC):
        try:
            return gzip.decompress(data)
        except (OSError, EOFError) as exc:
            raise SubFileError(t("err.gzip_decompress", error=exc)) from exc
    return data


def decode_xml(data: bytes, encoding: str | None = None) -> str:
    """Decode XML bytes into text.

    UTF-8 (with or without BOM) is used by default. UTF-16 is only attempted
    when a UTF-16 BOM is present, so corrupted UTF-8 data is not silently
    decoded into plausible-looking garbage.

    Args:
        data: XML bytes.
        encoding: Optional encoding name that overrides auto-detection.

    Returns:
        The decoded XML text.

    Raises:
        SubFileError: If the requested encoding cannot decode the data.
    """
    if encoding is not None:
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise SubFileError(t("err.decode", encoding=encoding, error=exc)) from exc

    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise SubFileError(t("err.decode_utf16", error=exc)) from exc

    print(
        format_message(t("warning.decode_replace"), label="warning"),
        file=sys.stderr,
    )
    return data.decode("utf-8", errors="replace")


def validate_xml(text: str) -> None:
    """Validate that the text is well-formed XML.

    Args:
        text: XML text to validate.

    Raises:
        SubFileError: If the text is not well-formed XML.
    """
    try:
        ET.fromstring(text)
    except ET.ParseError as exc:
        raise SubFileError(t("err.invalid_decompressed_xml", error=exc)) from exc


def unpack_sub(
    src: Path,
    out_dir: Path | None = None,
    *,
    encoding: str | None = None,
    force: bool = False,
    to_stdout: bool = False,
    validate: bool = True,
) -> Path | None:
    """Extract a single .sub file.

    Args:
        src: Path to the input .sub file.
        out_dir: Output directory. Defaults to the input file's directory.
        encoding: Optional encoding name that overrides auto-detection.
        force: Whether to overwrite an existing output file.
        to_stdout: Whether to print the XML instead of writing a file.
        validate: Whether to check that the result is well-formed XML.

    Returns:
        The output path, or None when writing to stdout.

    Raises:
        SubFileError: If reading, decompressing, validating, or writing fails,
            or if the output file already exists and force is False.
    """
    raw: bytes = read_sub_bytes(src)
    is_gzip: bool = raw.startswith(GZIP_MAGIC)
    xml_bytes: bytes = decompress_sub(raw)
    text: str = decode_xml(xml_bytes, encoding)

    if validate:
        validate_xml(text)

    if to_stdout:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return None

    target_dir: Path = out_dir if out_dir is not None else src.parent
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SubFileError(t("err.create_dir", path=target_dir, error=exc)) from exc

    dst: Path = target_dir / f"{src.stem}.xml"
    try:
        with dst.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as exc:
        if not force:
            raise SubFileError(t("err.output_exists", path=dst)) from exc
        try:
            dst.write_text(text, encoding="utf-8", newline="\n")
        except OSError as write_exc:
            raise SubFileError(t("err.write", path=dst, error=write_exc)) from write_exc
    except OSError as exc:
        raise SubFileError(t("err.write", path=dst, error=exc)) from exc

    kind: str = t("kind.gzip") if is_gzip else t("kind.plain_xml")
    print(
        t(
            "status.unpack",
            src=src.name,
            dst=dst,
            kind=kind,
            bytes=f"{len(xml_bytes):,}",
        )
    )
    return dst
