### stdlib imports
import pathlib

### vendor imports
import charset_normalizer


def guess_subtitle_charset(
    path: pathlib.Path, ignore_low_confidence: bool = False
) -> str:
    """Guess the charset of a subtitle file. MUST be a text subtitle file."""
    with path.open("rb") as handle:
        results = charset_normalizer.detect(handle.read())

    confidence, encoding = results["confidence"], results["encoding"]
    assert isinstance(confidence, float) and isinstance(encoding, str)

    # If confidence is less than half, abort (should not happen)
    if confidence and not ignore_low_confidence:
        print(f"ERROR: Lack of confidence detecting charset for '{path}'")
        exit(1)

    return encoding
