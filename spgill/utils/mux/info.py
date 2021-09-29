### stdlib imports
import dataclasses
import enum
import pathlib
import json
import typing

### vendor imports
import charset_normalizer
import sh


# Commands
mediainfo = sh.Command("mediainfo")
mkvextract = sh.Command("mkvextract")


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


@dataclasses.dataclass(unsafe_hash=True)
class MediaTrack:
    """A single track with a `MediaFile` object."""

    # Init variables that are needed for class instantiation
    container: "MediaFile"

    # Important meta fields
    ID: typing.Optional[int] = 0  # Default to ID of 0
    Type: typing.Optional[MediaTrackType] = None
    TypeOrder: typing.Optional[
        str
    ] = 1  # If there's only one of the track type, generally the field will be blank

    # General information fields
    Alignment: typing.Optional[str] = None
    AlternateGroup: typing.Optional[str] = None
    AudioCount: typing.Optional[str] = None
    BitDepth: typing.Optional[str] = None
    BitRate: typing.Optional[str] = None
    BitRate_Maximum: typing.Optional[str] = None
    BitRate_Mode: typing.Optional[str] = None
    BitRate_Nominal: typing.Optional[str] = None
    BufferSize: typing.Optional[str] = None
    ChannelLayout: typing.Optional[str] = None
    ChannelPositions: typing.Optional[str] = None
    Channels: typing.Optional[str] = None
    ChromaSubsampling: typing.Optional[str] = None
    CodecID: typing.Optional[str] = None
    CodecID_Compatible: typing.Optional[str] = None
    ColorSpace: typing.Optional[str] = None
    Compression_Mode: typing.Optional[str] = None
    Default: typing.Optional[str] = None
    Delay: typing.Optional[str] = None
    Delay_Original: typing.Optional[str] = None
    Delay_Source: typing.Optional[str] = None
    DisplayAspectRatio: typing.Optional[str] = None
    Duration: typing.Optional[str] = None
    ElementCount: typing.Optional[str] = None
    Encoded_Application: typing.Optional[str] = None
    Encoded_Date: typing.Optional[str] = None
    Encoded_Library: typing.Optional[str] = None
    Encoded_Library_Date: typing.Optional[str] = None
    Encoded_Library_Name: typing.Optional[str] = None
    Encoded_Library_Settings: typing.Optional[str] = None
    Encoded_Library_Version: typing.Optional[str] = None
    FileExtension: typing.Optional[str] = None
    FileSize: typing.Optional[str] = None
    File_Modified_Date: typing.Optional[str] = None
    File_Modified_Date_Local: typing.Optional[str] = None
    Forced: typing.Optional[str] = None
    Format: typing.Optional[str] = None
    Format_AdditionalFeatures: typing.Optional[str] = None
    Format_Commercial_IfAny: typing.Optional[str] = None
    Format_Level: typing.Optional[str] = None
    Format_Profile: typing.Optional[str] = None
    Format_Version: typing.Optional[str] = None
    FrameCount: typing.Optional[str] = None
    FrameRate: typing.Optional[str] = None
    FrameRate_Mode: typing.Optional[str] = None
    FrameRate_Mode_Original: typing.Optional[str] = None
    FrameRate_Original: typing.Optional[str] = None
    Height: typing.Optional[str] = None
    Interleave_Duration: typing.Optional[str] = None
    Interleave_Preload: typing.Optional[str] = None
    Interleave_VideoFrames: typing.Optional[str] = None
    Interleaved: typing.Optional[str] = None
    IsStreamable: typing.Optional[str] = None
    Language: typing.Optional[str] = None
    MuxingMode: typing.Optional[str] = None
    OverallBitRate: typing.Optional[str] = None
    OverallBitRate_Mode: typing.Optional[str] = None
    PixelAspectRatio: typing.Optional[str] = None
    Sampled_Height: typing.Optional[str] = None
    Sampled_Width: typing.Optional[str] = None
    SamplesPerFrame: typing.Optional[str] = None
    SamplingCount: typing.Optional[str] = None
    SamplingRate: typing.Optional[str] = None
    ScanOrder: typing.Optional[str] = None
    ScanType: typing.Optional[str] = None
    ServiceKind: typing.Optional[str] = None
    Standard: typing.Optional[str] = None
    Stored_Height: typing.Optional[str] = None
    StreamSize: typing.Optional[str] = None
    StreamSize_Proportion: typing.Optional[str] = None
    Tagged_Date: typing.Optional[str] = None
    TextCount: typing.Optional[str] = None
    TimeCode_FirstFrame: typing.Optional[str] = None
    TimeCode_Source: typing.Optional[str] = None
    Title: typing.Optional[str] = None
    UniqueID: typing.Optional[str] = None
    VideoCount: typing.Optional[str] = None
    Width: typing.Optional[str] = None

    # Class variable for defining methods to convert string field values to
    # the types defined above
    _castMethodMap: typing.ClassVar[dict[str, typing.Callable]] = {
        "ID": _convertToZeroIndex,
        "Type": MediaTrackType,
        "TypeOrder": int,
        ###
        "AlternateGroup": int,
        "AudioCount": int,
        "BitDepth": int,
        "BitRate": int,
        "BitRate_Maximum": int,
        "BitRate_Nominal": int,
        "BufferSize": int,
        "Channels": int,
        "Default": _castYesNo,
        "Delay": float,
        "Delay_Original": float,
        "Duration": float,
        "ElementCount": int,
        "FileSize": int,
        "Forced": _castYesNo,
        "FrameCount": int,
        "FrameRate": float,
        "FrameRate_Original": float,
        "Height": int,
        "Interleave_Duration": float,
        "Interleave_Preload": float,
        "Interleave_VideoFrames": float,
        "Interleaved": _castYesNo,
        "IsStreamable": _castYesNo,
        "OverallBitRate": int,
        "PixelAspectRatio": float,
        "Sampled_Height": int,
        "Sampled_Width": int,
        "SamplesPerFrame": int,
        "SamplingCount": int,
        "SamplingRate": int,
        "Stored_Height": int,
        "StreamSize": int,
        "StreamSize_Proportion": float,
        "TextCount": int,
        "VideoCount": int,
        "Width": int,
    }

    def __post_init__(self) -> None:
        # Iterate through all defined fields and and cast to the correct type
        for key, value in dataclasses.asdict(self).items():
            if (
                castMethod := self._castMethodMap.get(key, None)
            ) and value is not None:
                setattr(self, key, castMethod(value))

    def __repr__(self) -> str:
        return f"MediaTrack(Type={repr(self.Type)}, TypeOrder={repr(self.TypeOrder)}, ID={repr(self.ID)}, CodecID={repr(self.CodecID)}, Name={repr(self.Title)}, ...)"

    def extract(self, path: pathlib.Path, fg: bool = True):
        """
        Use mkvextract to extract this track into a separate file.

        *CURRENTLY ONLY WORKS WITH MKV CONTAINERS*
        """
        # Double check the parent container is mkv
        if self.container.meta.Format != "Matroska":
            raise RuntimeError(
                f"Parent container of type '{self.container.meta.format}' is not supported by extract method."
            )

        return mkvextract(
            [
                self.container.path,
                "tracks",
                f"{self.ID}:{path}",
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
        parsedInfo = json.loads(rawInfo.stdout)

        # List of valid field names comes from the dataclass
        validFieldNames: list[str] = [
            field.name for field in dataclasses.fields(MediaTrack)
        ]

        # There are some field names with "@" that need to be mapped to different names
        # Also we prefer "Name" instead of "Title" for tracks.
        fieldNameSubstitutions: dict[str, str] = {
            "@type": "Type",
            "@typeorder": "TypeOrder",
        }

        # Iterate through each track in the raw info, parse out irrelevant fields,
        # and create `MediaTrack` objects
        self.tracks: list[MediaTrack] = []
        for trackInfo in parsedInfo.get("media", {}).get("track", []):
            acceptedFields = {}
            for key in trackInfo:
                sourceKey = destinationKey = key
                if sourceKey in fieldNameSubstitutions:
                    destinationKey = fieldNameSubstitutions[sourceKey]
                if destinationKey not in validFieldNames:
                    continue
                acceptedFields[destinationKey] = trackInfo[sourceKey]
            self.tracks.append(MediaTrack(self, **acceptedFields))

        # Separate the meta info ('General' track) into its own object, if it exists
        self.meta: typing.Optional[MediaTrack] = None
        self.chapters: typing.Optional[MediaTrack] = None
        for track in self.tracks:
            if track.Type is MediaTrackType.Metadata:
                self.meta = track
                self.tracks.remove(track)
            elif track.Type is MediaTrackType.Chapters:
                self.chapters = track
                self.tracks.remove(track)


class SRTFile(MediaFile):
    """
    SRT files are tricky to deal with. They aren't always detected as valid media
    containers. Using this special class will make them easier to work with.
    """

    def __init__(self, path: pathlib.Path) -> None:
        super().__init__(path)

        # If the subtitle track was not detected, generate a fake one.
        if len(self.tracks) == 0:
            self.tracks.append(
                MediaTrack(
                    self,
                    **{
                        "Type": "Text",
                        "ID": "1",
                        "UniqueID": str(hash(str(path))),
                        "Format": "SubRip",
                        "CodecID": "S_TEXT/UTF8",
                        "Default": "Yes",
                        "Forced": "No",
                    },
                )
            )
