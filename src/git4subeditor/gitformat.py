"""Convert .sub files to and from a Git-friendly XML bundle.

The bundle contains a canonical, line-oriented XML file and, when present, the
submarine preview image extracted from the ``previewimage`` attribute. The XML
references the image through a relative ``preview`` attribute. Packing
re-embeds the preview image and writes a deterministic gzip-compressed .sub
file, backing up an existing target first.
"""

import base64
import binascii
import gzip
import io
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from git4subeditor.l10n import t
from git4subeditor.subfile import (
    GZIP_MAGIC,
    SubFileError,
    decode_xml,
    decompress_sub,
    read_sub_bytes,
)
from git4subeditor.utils import format_message

PREVIEW_ATTRIBUTE: str = "previewimage"
PREVIEW_LINK_ATTRIBUTE: str = "preview"
INDENT: str = "  "

_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"BM", ".bmp"),
)
# Barotrauma stores these comma-separated attributes as unordered sets. The
# game may write them in a different order every time a submarine is saved.
_UNORDERED_COMMA_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "Tags",
        "items",
        "excludedidentifiers",
        "DisallowedUpgrades",
        "DisallowAttachingOverTags",
        "ContainableRestrictions",
        "idcardtags",
        "outposttags",
    }
)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Paths written by :func:`export_sub`.

    Attributes:
        xml_path: The canonical XML file.
        preview_path: The extracted preview image, or None when the source has
            no preview image.
    """

    xml_path: Path
    preview_path: Path | None


def parse_xml(text: str) -> ET.Element:
    """Parse XML text while preserving comments and processing instructions.

    Args:
        text: XML text.

    Returns:
        The root element.

    Raises:
        SubFileError: If the text is not well-formed XML.
    """
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    try:
        return ET.fromstring(text, parser=parser)
    except ET.ParseError as exc:
        raise SubFileError(t("err.invalid_xml", error=exc)) from exc


def serialize_xml(
    root: ET.Element,
    *,
    sort_attributes: bool = False,
    trailing_newline: bool = True,
) -> str:
    """Serialize an XML tree in canonical, line-oriented form.

    The tree is modified in place: elements are indented with two spaces and,
    when requested, attributes are sorted alphabetically. Comma-separated
    game set attributes such as ``Tags`` and ``items`` are always sorted so
    that saving the same submarine again does not produce meaningless diffs.

    Args:
        root: Root element to serialize.
        sort_attributes: Whether to sort attributes of every element.
        trailing_newline: Whether to end the result with a newline.

    Returns:
        The serialized XML text using LF line endings.
    """
    _canonicalize_unordered_attributes(root)
    if sort_attributes:
        _sort_attributes(root)
    ET.indent(root, space=INDENT)
    text = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    if trailing_newline and not text.endswith("\n"):
        text += "\n"
    return text


def extract_preview_image(root: ET.Element) -> tuple[bytes, str] | None:
    """Remove the preview image from the root and decode it.

    Args:
        root: Root element of a submarine XML document. It is modified in
            place.

    Returns:
        A tuple of image bytes and a file suffix such as ``".png"``, or None
        when the root has no preview image.

    Raises:
        SubFileError: If the ``previewimage`` attribute is not valid base64.
    """
    encoded = root.attrib.get(PREVIEW_ATTRIBUTE)
    if encoded is None:
        return None

    compact = "".join(encoded.split())
    if not compact:
        del root.attrib[PREVIEW_ATTRIBUTE]
        return None

    try:
        image = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SubFileError(t("err.invalid_base64", error=exc)) from exc

    del root.attrib[PREVIEW_ATTRIBUTE]
    return image, _guess_image_suffix(image)


def embed_preview_image(root: ET.Element, image: bytes) -> None:
    """Add a preview image to the root as a base64 attribute.

    Existing ``previewimage`` attributes are left untouched.

    Args:
        root: Root element of a submarine XML document. It is modified in
            place.
        image: The image file contents to embed.
    """
    if PREVIEW_ATTRIBUTE in root.attrib:
        return
    root.set(PREVIEW_ATTRIBUTE, base64.b64encode(image).decode("ascii"))


def export_sub(
    src: Path,
    out_dir: Path | None = None,
    *,
    force: bool = False,
    sort_attributes: bool = False,
) -> ExportResult:
    """Export a .sub file into a Git-friendly XML bundle.

    The XML is written as ``<stem>.xml`` in the output directory. When the
    source has a preview image, it is written as ``<stem>.<ext>`` and the root
    element receives a relative ``preview`` attribute pointing to it.

    Args:
        src: Path to the input .sub file.
        out_dir: Output directory. Defaults to the input file's directory.
        force: Whether to overwrite existing output files.
        sort_attributes: Whether to sort XML attributes alphabetically.

    Returns:
        The paths of the written XML file and preview image.

    Raises:
        SubFileError: If reading, decompressing, parsing, or writing fails, or
            if an output file already exists and force is False.
    """
    raw: bytes = read_sub_bytes(src)
    text: str = decode_xml(decompress_sub(raw))
    root: ET.Element = parse_xml(text)
    _require_submarine_root(root)

    preview: tuple[bytes, str] | None = extract_preview_image(root)

    target_dir: Path = out_dir if out_dir is not None else src.parent
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SubFileError(t("err.create_dir", path=target_dir, error=exc)) from exc

    xml_path = target_dir / f"{src.stem}.xml"
    preview_path = (
        target_dir / f"{src.stem}{preview[1]}" if preview is not None else None
    )

    root.attrib.pop(PREVIEW_LINK_ATTRIBUTE, None)
    if preview_path is not None:
        root.set(PREVIEW_LINK_ATTRIBUTE, preview_path.name)

    canonical: str = serialize_xml(
        root,
        sort_attributes=sort_attributes,
        trailing_newline=True,
    )

    _ensure_writable(xml_path, force)
    if preview_path is not None:
        _ensure_writable(preview_path, force)

    _write_text(xml_path, canonical)
    if preview is not None and preview_path is not None:
        _write_bytes(preview_path, preview[0])

    return ExportResult(xml_path=xml_path, preview_path=preview_path)


def pack_sub(
    xml_path: Path,
    out: Path | None = None,
    *,
    preview_override: bytes | None = None,
    sort_attributes: bool = False,
    compresslevel: int = 9,
) -> Path:
    """Pack an exported XML file back into a .sub file.

    The relative ``preview`` attribute is resolved against the XML directory
    and embedded as base64 in ``previewimage``. If the linked image is missing,
    a warning is printed and the preview is omitted. An existing target is
    copied to ``<target>.bak`` before it is overwritten.

    When ``preview_override`` is provided, those image bytes take priority
    over the XML ``preview`` link and are embedded instead.

    The output is gzip-compressed with a fixed timestamp, so packing the same
    XML twice produces identical bytes.

    Args:
        xml_path: Path to the exported XML file.
        out: Output .sub path. Defaults to the XML file with a ``.sub`` suffix.
        preview_override: Optional preview image bytes that override the XML
            ``preview`` link.
        sort_attributes: Whether to sort XML attributes before packing.
        compresslevel: gzip compression level from 0 to 9.

    Returns:
        The path of the written .sub file.

    Raises:
        SubFileError: If reading, parsing, resolving the preview link, backing
            up the target, or writing fails, or if the override image is
            empty.
        ValueError: If compresslevel is outside the range 0 to 9.
    """
    if not 0 <= compresslevel <= 9:
        raise ValueError(f"compresslevel must be between 0 and 9, got {compresslevel}")

    try:
        raw: bytes = xml_path.read_bytes()
    except OSError as exc:
        raise SubFileError(t("err.read_file", path=xml_path, error=exc)) from exc

    if raw.startswith(GZIP_MAGIC):
        raise SubFileError(t("err.pack_sub_input", path=xml_path))

    root: ET.Element = parse_xml(decode_xml(raw))
    _require_submarine_root(root)

    link = root.attrib.pop(PREVIEW_LINK_ATTRIBUTE, None)
    if PREVIEW_ATTRIBUTE not in root.attrib:
        if preview_override is not None:
            if not preview_override:
                raise SubFileError(t("err.empty_preview", path=xml_path))
            embed_preview_image(root, preview_override)
        elif link is not None:
            preview_path = _resolve_preview_link(xml_path, link)
            try:
                preview = preview_path.read_bytes()
            except FileNotFoundError:
                print(
                    format_message(
                        t("warning.preview_missing", path=preview_path),
                        label="warning",
                    ),
                    file=sys.stderr,
                )
                preview = None
            except OSError as exc:
                raise SubFileError(
                    t("err.read_preview", path=preview_path, error=exc)
                ) from exc
            if preview is not None:
                if not preview:
                    raise SubFileError(t("err.empty_preview", path=preview_path))
                embed_preview_image(root, preview)

    text: str = serialize_xml(
        root,
        sort_attributes=sort_attributes,
        trailing_newline=False,
    )
    compressed: bytes = _compress_xml(text.encode("utf-8"), compresslevel)

    dst = _resolve_pack_output(xml_path, out)
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SubFileError(t("err.create_dir", path=dst.parent, error=exc)) from exc
    _backup_existing(dst)
    _write_bytes(dst, compressed)
    return dst


def _require_submarine_root(root: ET.Element) -> None:
    """Check that the root element is a Submarine element."""
    if root.tag != "Submarine":
        raise SubFileError(t("err.submarine_root", tag=root.tag))


def _canonicalize_unordered_attributes(element: ET.Element) -> None:
    """Sort comma-separated set attributes of an element and its descendants."""
    for name in _UNORDERED_COMMA_ATTRIBUTES:
        value = element.attrib.get(name)
        if value is None or "," not in value:
            continue
        parts = [part.strip() for part in value.split(",")]
        element.attrib[name] = ",".join(sorted(parts, key=str.casefold))
    for child in element:
        _canonicalize_unordered_attributes(child)


def _sort_attributes(element: ET.Element) -> None:
    """Sort the attributes of an element and all its descendants."""
    element.attrib = dict(sorted(element.attrib.items()))
    for child in element:
        _sort_attributes(child)


def _guess_image_suffix(image: bytes) -> str:
    """Return a file suffix based on image magic bytes."""
    for signature, suffix in _IMAGE_SIGNATURES:
        if image.startswith(signature):
            return suffix
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def _resolve_pack_output(xml_path: Path, out: Path | None) -> Path:
    """Resolve the output path for pack_sub."""
    if out is None:
        return xml_path.with_suffix(".sub")
    if out.is_dir():
        return out / f"{xml_path.stem}.sub"
    return out


def _resolve_preview_link(xml_path: Path, link: str) -> Path:
    """Resolve a relative preview link against the XML file's directory."""
    if not link.strip():
        raise SubFileError(t("err.empty_preview_link"))
    path = Path(link)
    return path if path.is_absolute() else xml_path.parent / path


def _backup_existing(path: Path) -> Path | None:
    """Copy an existing target to ``<name>.bak`` before overwriting it."""
    if not path.exists():
        return None
    if not path.is_file():
        raise SubFileError(t("err.not_regular_file", path=path))

    backup = path.with_name(f"{path.name}.bak")
    try:
        shutil.copy2(path, backup)
    except OSError as exc:
        raise SubFileError(
            t("err.backup", path=path, backup=backup, error=exc)
        ) from exc
    return backup


def _ensure_writable(path: Path, force: bool) -> None:
    """Raise when a target cannot be written."""
    if not path.exists():
        return
    if not force:
        raise SubFileError(t("err.output_exists", path=path))
    if not path.is_file():
        raise SubFileError(t("err.not_regular_file", path=path))


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with LF line endings."""
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SubFileError(t("err.write", path=path, error=exc)) from exc


def _write_bytes(path: Path, data: bytes) -> None:
    """Write raw bytes, wrapping OSError as SubFileError."""
    try:
        path.write_bytes(data)
    except OSError as exc:
        raise SubFileError(t("err.write", path=path, error=exc)) from exc


def _compress_xml(data: bytes, compresslevel: int) -> bytes:
    """Gzip-compress XML bytes with a stable timestamp."""
    buffer = io.BytesIO()
    try:
        with gzip.GzipFile(
            fileobj=buffer,
            mode="wb",
            compresslevel=compresslevel,
            mtime=0,
        ) as stream:
            stream.write(data)
    except OSError as exc:
        raise SubFileError(t("err.gzip_compress", error=exc)) from exc
    return buffer.getvalue()
