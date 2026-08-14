"""Library stream parser — extracts strLst (string table) from DSN Library stream.

Reference:
    OpenOrCadParser: src/Streams/StreamLibrary.cpp
    universal-netlist: src/parsers/cadence/dsn/library-parser.ts
    dsn-format.md §6
"""

from __future__ import annotations

import logging
from typing import Optional

from .binary_reader import BinaryReader

logger = logging.getLogger(__name__)

# Constants
HEADER_BYTE_SIZE = 48
PAGE_SETTINGS_SIZE = 156
LOGFONTA_SIZE = 60
PART_FIELD_COUNT = 8


def parse_strlst(library_bytes: bytes) -> list[str]:
    """Parse the strLst (string table) from a Library stream.

    Args:
        library_bytes: Raw bytes of the Library CFB stream.

    Returns:
        List of strings in Latin-1 encoding.

    Raises:
        ValueError: If the stream format is unrecognized.
    """
    reader = BinaryReader(library_bytes)

    # --- Header (48 bytes) ---
    reader.skip(HEADER_BYTE_SIZE)

    # --- LOGFONTA structures ---
    text_font_len = reader.read_uint16()
    font_count = max(0, text_font_len - 1)  # text_font_len - 1 fonts
    reader.skip(font_count * LOGFONTA_SIZE)

    # --- some_len + some_data ---
    some_len = reader.read_uint16()
    reader.skip(some_len * 2)  # uint16 array

    # --- 8 bytes unknown ---
    reader.skip(8)

    # --- 8 part field strings (len_zero_term format) ---
    for _ in range(PART_FIELD_COUNT):
        slen = reader.read_uint16()
        if slen > 0:
            reader.skip(slen)
        reader.skip(1)  # null terminator

    # --- PageSettings (156 bytes) ---
    reader.skip(PAGE_SETTINGS_SIZE)

    # --- strLst count ---
    str_lst_len = reader.read_uint32()

    # --- strLst entries ---
    result: list[str] = []
    for i in range(str_lst_len):
        slen = reader.read_uint16()
        if slen == 0:
            reader.skip(1)  # null terminator only
            result.append("")
            continue
        raw = reader.read_bytes(slen)
        reader.skip(1)  # null terminator
        text = raw.decode("latin-1", errors="replace")

        # If Latin-1 result contains a high proportion of non-printable
        # characters, the string is likely GBK-encoded Chinese text
        # (common in HG5015 DSN files where DESCRIPTION/SOURCE_LIBRARY
        # property values were written in GBK).
        non_printable = sum(
            1 for c in text
            if not c.isprintable() and c not in ' \t\n\r'
        )
        if non_printable > len(text) * 0.2:
            try:
                text = raw.decode("gbk", errors="replace")
            except (UnicodeDecodeError, LookupError):
                pass

        result.append(text)

    logger.info("Parsed strLst: %d entries", len(result))
    return result
