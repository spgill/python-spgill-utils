### stdlib imports
import enum
import pathlib
import json
import types
import typing

### vendor imports
import charset_normalizer
import sh


# Commands
mediainfo = sh.Command("mediainfo")
mkvextract = sh.Command("mkvextract")


# Cast methods
def _castYesNo(value: str) -> bool:
    return value.lower() == "yes"


def _convertToZeroIndex(value: str) -> int:
    return int(value) - 1


class MediaTrackType(enum.Enum):
    """Enum representing the type of content in the media track."""

    Metadata = "General"
    Chapters = "Menu"
    Video = "Video"
    Audio = "Audio"
    Subtitles = "Text"


class MediaTrack(types.SimpleNamespace):
    """A single track with a `MediaFile` object."""

    # Map of track fields to method for casting them to the appropriate types
    _fieldCastMap: dict[str, typing.Any] = {
        "audiocount": int,
        "bitdepth": int,
        "bitrate_maximum": int,
        "bitrate": int,
        "buffersize": int,
        "channels": int,
        "colour_description_present": _castYesNo,
        "default": _castYesNo,
        "delay": float,
        "displayaspectratio": float,
        "duration": float,
        "elementcount": int,
        "filesize": int,
        "forced": _castYesNo,
        "format_settings_cabac": _castYesNo,
        "format_settings_refframes": int,
        "framecount": int,
        "framerate": float,
        "height": int,
        "id": _convertToZeroIndex,
        "isstreamable": _castYesNo,
        "overallbitrate": int,
        "pixelaspectratio": float,
        "sampled_height": int,
        "sampled_width": int,
        "samplesperframe": int,
        "samplingcount": int,
        "samplingrate": int,
        "stored_height": int,
        "streamorder": int,
        "streamsize_proportion": float,
        "streamsize": int,
        "textcount": int,
        "type": MediaTrackType,
        "videocount": int,
        "width": int,
    }

    def __init__(
        self,
        container: "MediaFile",
        /,
        **kwargs: typing.Union[str, int, float],
    ) -> None:
        self.container = container

        # Sanitize all field names
        kwargs = {
            key.lower().replace("@", ""): value
            for key, value in kwargs.items()
        }

        # Iterate through each field and process them through the appropriate cast method
        for key in kwargs:
            if castMethod := self._fieldCastMap.get(key.lower(), None):
                kwargs[key] = castMethod(kwargs[key])

        super().__init__(**kwargs)

    def __getattr__(self, name: str) -> typing.Any:
        if name.lower() in self.__dict__:
            return super().__getattribute__(name.lower())
        return None

    def extract(self, path: pathlib.Path, fg: bool = True):
        """
        Use mkvextract to extract this track into a separate file.

        *CURRENTLY ONLY WORKS WITH MKV CONTAINERS*
        """
        # Double check the parent container is mkv
        if self.container.meta.format != "Matroska":
            raise RuntimeError(
                f"Parent container of type '{self.container.meta.format}' is not supported by extract method."
            )

        return mkvextract(
            [
                self.container.path,
                "tracks",
                f"{self.id}:{path}",
            ],
            _fg=fg,
        )


class MediaFile(object):
    """Object representing a single media container file."""

    def __init__(self, path: pathlib.Path) -> None:
        super().__init__()

        # Check that the path is valid
        self.path = path.absolute()
        if not self.path.is_file():
            raise RuntimeError(f"'{path}' is not a valid file path!")

        # Start by reading the file and decoding the JSON
        rawInfo = mediainfo(["--output=JSON", self.path])
        self.info = json.loads(rawInfo.stdout)

        # Get a list of tracks from the info, and convert into MediaTrack objects
        self.tracks = [
            MediaTrack(self, **track)
            for track in self.info.get("media", {}).get("track", [])
        ]

        # Separate the meta info ('General' track) into its own object, if it exists
        self.meta: typing.Optional[MediaTrack] = None
        self.chapters: typing.Optional[MediaTrack] = None
        for track in self.tracks:
            if track.type is MediaTrackType.Metadata:
                self.meta = track
                self.tracks.remove(track)
            elif track.type is MediaTrackType.Chapters:
                self.chapters = track
                self.tracks.remove(track)


def guessSubtitleCharset(
    path: pathlib.Path, ignoreLowConfidence: bool = False
) -> str:
    """Guess the charset of a subtitle file. MUST be a text subtitle file."""
    with path.open("rb") as handle:
        results = charset_normalizer.detect(handle.read())

    # If confidence is less than half, abort (should not happen)
    if results["confidence"] <= 0.5 and not ignoreLowConfidence:
        print(f"ERROR: Lack of confidence detecting charset for '{path}'")
        exit(1)

    return results["encoding"]
