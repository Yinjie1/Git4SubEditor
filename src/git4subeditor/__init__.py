"""Utilities for version-controlling Barotrauma submarine files."""

from git4subeditor.gitformat import (
    PREVIEW_ATTRIBUTE,
    PREVIEW_LINK_ATTRIBUTE,
    ExportResult,
    embed_preview_image,
    export_sub,
    extract_preview_image,
    pack_sub,
    parse_xml,
    serialize_xml,
)
from git4subeditor.subfile import (
    SubFileError,
    decode_xml,
    decompress_sub,
    read_sub_bytes,
    unpack_sub,
    validate_xml,
)

__all__ = [
    "PREVIEW_ATTRIBUTE",
    "PREVIEW_LINK_ATTRIBUTE",
    "ExportResult",
    "SubFileError",
    "decode_xml",
    "decompress_sub",
    "embed_preview_image",
    "export_sub",
    "extract_preview_image",
    "pack_sub",
    "parse_xml",
    "read_sub_bytes",
    "serialize_xml",
    "unpack_sub",
    "validate_xml",
]

__version__ = "0.0.3"
