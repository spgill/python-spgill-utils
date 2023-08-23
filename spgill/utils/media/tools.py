"""
Module containing miscellaneous utility functions that don't belong anywhere else.
"""

### stdlib imports
import pathlib

### vendor imports
import charset_normalizer


def guess_subtitle_charset(
    path: pathlib.Path, ignore_low_confidence: bool = False
) -> str:
    """
    Guess the charset of a TEXT subtitle file.

    Useful when muxing .SRT or other text subtitles into a Matroska container,
    because Matroska will assume everything is UTF-8; this tool can help identify
    if a character set needs to be converted in the mux process.
    """
    with path.open("rb") as handle:
        results = charset_normalizer.detect(handle.read())

    confidence, encoding = results["confidence"], results["encoding"]
    assert isinstance(confidence, float) and isinstance(encoding, str)

    # If confidence is less than half, abort (should not happen)
    if confidence and not ignore_low_confidence:
        print(f"ERROR: Lack of confidence detecting charset for '{path}'")
        exit(1)

    return encoding
