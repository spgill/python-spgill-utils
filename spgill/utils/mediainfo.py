### stdlib imports
import enum
import pathlib
import json
import types
import typing

### vendor imports
import sh


# Commands
mediainfo = sh.Command("mediainfo")


# Cast methods
def castYesNo(value: str) -> bool:
    return value.lower() == "yes"


class MediaTrackType(enum.Enum):
    """Enum representing the type of content in the media track."""

    Metadata = "General"
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
        "colour_description_present": castYesNo,
        "default": castYesNo,
        "delay": float,
        "displayaspectratio": float,
        "duration": float,
        "elementcount": int,
        "filesize": int,
        "forced": castYesNo,
        "format_settings_cabac": castYesNo,
        "format_settings_refframes": int,
        "framecount": int,
        "framerate": float,
        "height": int,
        "id": int,
        "isstreamable": castYesNo,
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

    def __init__(self, **kwargs: typing.Union[str, int, float]) -> None:

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


class MediaFile(object):
    """Object representing a single media container file."""

    def __init__(self, path: typing.Union[pathlib.Path, str]) -> None:
        super().__init__()

        # Normalize the path into a path object
        self.path = pathlib.Path(path).expanduser().absolute()

        # Start by reading the file and decoding the JSON
        rawInfo = mediainfo(["--output=JSON", self.path])
        self.info = json.loads(rawInfo.stdout)

        # Get a list of tracks from the info, and convert into MediaTrack objects
        trackList = [
            MediaTrack(**track)
            for track in self.info.get("media", {}).get("track", [])
        ]

        # Separate the meta info ('General' track) into its own object, if it exists
        self.meta: typing.Union[MediaTrack, None] = None
        for track in trackList:
            if track.type is MediaTrackType.Metadata:
                self.meta = track
                break

        # Now, split all non-meta tracks into the tracks list
        self.tracks = tuple(
            track
            for track in trackList
            if track.type is not MediaTrackType.Metadata
        )
