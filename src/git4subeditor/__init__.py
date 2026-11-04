"""Utilities for version-controlling Barotrauma submarine files."""

from git4subeditor.subfile import (
    SubFileError,
    decode_xml,
    decompress_sub,
    read_sub_bytes,
    unpack_sub,
    validate_xml,
)

__all__ = [
    "SubFileError",
    "decode_xml",
    "decompress_sub",
    "read_sub_bytes",
    "unpack_sub",
    "validate_xml",
]

__version__ = "0.1.0"
