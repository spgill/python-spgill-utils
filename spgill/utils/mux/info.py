### stdlib imports
import base64
import dataclasses
import enum
import pathlib
import re
import json
import typing

### vendor imports
import charset_normalizer
import sh


# Commands
mediainfo = sh.Command("mediainfo")
mkvextract = sh.Command("mkvextract")

# Constants
trackSelectorFragmentPattern = re.compile(r"^([-+]?)(.*)$")
commaDelimitedNumbersPattern = re.compile(
    r"^(?:(?:(?<!^),)?(?:(?:-?\d+)?(?:(?<=\d)\:|\:(?=-?\d))(?:-?\d+)?|-?\d+))+$"
)


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
    try:
        return max(int(value) - 1, 0)
    except ValueError:
        return -1


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
    _raw: typing.Optional[typing.Any] = dataclasses.field(
        hash=False
    )  # don't hash this field
    ID: typing.Optional[int] = 0  # Default to ID of 0
    Type: typing.Optional[MediaTrackType] = None
    TypeOrder: typing.Optional[
        str
    ] = 1  # If there's only one of the track type, generally the field will be blank

    # General information fields
    Alignment: typing.Optional[str] = None
    AlternateGroup: typing.Optional[int] = None
    AudioCount: typing.Optional[int] = None
    BitDepth: typing.Optional[str] = None
    BitRate_Maximum: typing.Optional[int] = None
    BitRate_Mode: typing.Optional[str] = None
    BitRate_Nominal: typing.Optional[int] = None
    BitRate: typing.Optional[int] = None
    BufferSize: typing.Optional[str] = None
    ChannelLayout: typing.Optional[str] = None
    ChannelPositions: typing.Optional[str] = None
    Channels: typing.Optional[int] = None
    ChromaSubsampling: typing.Optional[str] = None
    CodecID_Compatible: typing.Optional[str] = None
    CodecID: typing.Optional[str] = None
    ColorSpace: typing.Optional[str] = None
    Compression_Mode: typing.Optional[str] = None
    Default: typing.Optional[bool] = None
    Delay_Original: typing.Optional[float] = None
    Delay_Source: typing.Optional[str] = None
    Delay: typing.Optional[float] = None
    DisplayAspectRatio: typing.Optional[str] = None
    Duration: typing.Optional[float] = None
    ElementCount: typing.Optional[int] = None
    Encoded_Application: typing.Optional[str] = None
    Encoded_Date: typing.Optional[str] = None
    Encoded_Library_Date: typing.Optional[str] = None
    Encoded_Library_Name: typing.Optional[str] = None
    Encoded_Library_Settings: typing.Optional[str] = None
    Encoded_Library_Version: typing.Optional[str] = None
    Encoded_Library: typing.Optional[str] = None
    File_Modified_Date_Local: typing.Optional[str] = None
    File_Modified_Date: typing.Optional[str] = None
    FileExtension: typing.Optional[str] = None
    FileSize: typing.Optional[int] = None
    Forced: typing.Optional[bool] = None
    Format_AdditionalFeatures: typing.Optional[str] = None
    Format_Commercial_IfAny: typing.Optional[str] = None
    Format_Level: typing.Optional[str] = None
    Format_Profile: typing.Optional[str] = None
    Format_Version: typing.Optional[str] = None
    Format: typing.Optional[str] = None
    FrameCount: typing.Optional[int] = None
    FrameRate_Mode_Original: typing.Optional[str] = None
    FrameRate_Mode: typing.Optional[str] = None
    FrameRate_Original: typing.Optional[float] = None
    FrameRate: typing.Optional[float] = None
    HDR_Format_Compatibility: typing.Optional[str] = None
    HDR_Format_Level: typing.Optional[str] = None
    HDR_Format_Profile: typing.Optional[str] = None
    HDR_Format_Settings: typing.Optional[str] = None
    HDR_Format_Version: typing.Optional[str] = None
    HDR_Format: typing.Optional[str] = None
    Height: typing.Optional[int] = None
    Interleave_Duration: typing.Optional[float] = None
    Interleave_Preload: typing.Optional[float] = None
    Interleave_VideoFrames: typing.Optional[float] = None
    Interleaved: typing.Optional[bool] = None
    IsStreamable: typing.Optional[bool] = None
    Language: typing.Optional[str] = None
    MasteringDisplay_ColorPrimaries_Source: typing.Optional[str] = None
    MasteringDisplay_ColorPrimaries: typing.Optional[str] = None
    MasteringDisplay_Luminance_Source: typing.Optional[str] = None
    MasteringDisplay_Luminance: typing.Optional[str] = None
    MaxCLL_Source: typing.Optional[str] = None
    MaxCLL: typing.Optional[str] = None
    MaxFALL_Source: typing.Optional[str] = None
    MaxFALL: typing.Optional[str] = None
    MuxingMode: typing.Optional[str] = None
    OverallBitRate_Mode: typing.Optional[str] = None
    OverallBitRate: typing.Optional[int] = None
    PixelAspectRatio: typing.Optional[float] = None
    Sampled_Height: typing.Optional[int] = None
    Sampled_Width: typing.Optional[int] = None
    SamplesPerFrame: typing.Optional[int] = None
    SamplingCount: typing.Optional[int] = None
    SamplingRate: typing.Optional[int] = None
    ScanOrder: typing.Optional[str] = None
    ScanType: typing.Optional[str] = None
    ServiceKind: typing.Optional[str] = None
    Standard: typing.Optional[str] = None
    Stored_Height: typing.Optional[int] = None
    StreamSize_Proportion: typing.Optional[float] = None
    StreamSize: typing.Optional[int] = None
    Tagged_Date: typing.Optional[str] = None
    TextCount: typing.Optional[int] = None
    TimeCode_FirstFrame: typing.Optional[str] = None
    TimeCode_Source: typing.Optional[str] = None
    Title: typing.Optional[str] = None
    UniqueID: typing.Optional[str] = None
    VideoCount: typing.Optional[int] = None
    Width: typing.Optional[int] = None

    # Class variable for defining methods to convert string field values to
    # the types defined above
    _castMethodMap: typing.ClassVar[dict[str, typing.Callable]] = {
        "ID": _convertToZeroIndex,
        "Type": MediaTrackType,
        "TypeOrder": int,
        ###
        "AlternateGroup": int,
        "AudioCount": int,
        "BitRate_Maximum": int,
        "BitRate_Nominal": int,
        "BitRate": int,
        "Channels": int,
        "Default": _castYesNo,
        "Delay_Original": float,
        "Delay": float,
        "Duration": float,
        "ElementCount": int,
        "FileSize": int,
        "Forced": _castYesNo,
        "FrameCount": int,
        "FrameRate_Original": float,
        "FrameRate": float,
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
        "StreamSize_Proportion": float,
        "StreamSize": int,
        "TextCount": int,
        "VideoCount": int,
        "Width": int,
    }

    def __post_init__(self) -> None:
        # Iterate through all defined fields and and cast to the correct type
        for key, value in dataclasses.asdict(self).items():
            # Some long string values may be base64 encoded by mediainfo
            if isinstance(value, dict) and "@dt" in value:
                value = base64.b64decode(value["#value"]).decode()
                setattr(self, key, value)

            if (
                castMethod := self._castMethodMap.get(key, None)
            ) and value is not None:
                try:
                    setattr(self, key, castMethod(value))
                except ValueError:
                    raise ValueError(
                        f"Error casting value of field '{key}' using method '{castMethod}'. Value in container '{self.container.path}' is '{value}'"
                    )

    def __repr__(self) -> str:
        return f"MediaTrack(Type={repr(self.Type)}, TypeOrder={repr(self.TypeOrder)}, ID={repr(self.ID)}, CodecID={repr(self.CodecID)}, Name={repr(self.Title)}, Default={repr(self.Default)}, Forced={repr(self.Forced)}, ...)"

    def extract(self, path: pathlib.Path, fg: bool = True):
        """
        Use mkvextract to extract this track into a separate file.

        If you want to extract more than one track from a single container,
        you can use the `MediaFile.extractTracks` method to do it in one go.

        *ONLY WORKS WITH MKV CONTAINERS*
        """
        self.container.extractTracks([(self, path)], fg)


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
            self.tracks.append(
                MediaTrack(self, _raw=trackInfo, **acceptedFields)
            )

        # Separate the meta info ('General' track) into its own object, if it exists
        self.meta: MediaTrack = None
        self.chapters: list[MediaTrack] = []
        for track in self.tracks:
            if track.Type is MediaTrackType.Metadata:
                self.meta = track
                self.tracks.remove(track)
            elif track.Type is MediaTrackType.Chapters:
                self.chapters.append(track)
                self.tracks.remove(track)

        # Generate list of tracks grouped by type
        self.tracksByType: dict[MediaTrackType, list[MediaTrack]] = {
            trackType: [
                track for track in self.tracks if track.Type is trackType
            ]
            for trackType in [
                MediaTrackType.Video,
                MediaTrackType.Audio,
                MediaTrackType.Subtitles,
            ]
        }

    def extractTracks(
        self, tracks: list[tuple[MediaTrack, pathlib.Path]], fg: bool = True
    ):
        """
        Extract one or many tracks from this container.

        *ONLY WORKS WITH MKV CONTAINERS*
        """
        # Double check this container is mkv
        if self.meta.Format != "Matroska":
            raise RuntimeError(
                f"Parent container of type '{self.meta.Format}' is not supported by extract method."
            )

        extractArgs: list[typing.Union[pathlib.Path, str]] = [
            self.path,
            "tracks",
        ]

        for trackObj, trackPath in tracks:
            # Double check the track belongs to this container
            if trackObj.container is not self:
                raise RuntimeError(
                    "You passed a track to `extractTracks` that does not belong to this container."
                )

            extractArgs.append(f"{trackObj.ID}:{trackPath}")

        mkvextract(*extractArgs, _fg=fg)

    def extractChapters(
        self, path: pathlib.Path, simple: bool = False, fg: bool = True
    ):
        """
        Extract container chapters to a file.

        Despite the possibility of there being more than one chapter "track",
        this extract method will always produce ONE file.

        *ONLY WORKS WITH MKV CONTAINERS*
        """
        # Double check this container is mkv
        if self.meta.Format != "Matroska":
            raise RuntimeError(
                f"Parent container of type '{self.meta.Format}' is not supported by extract method."
            )

        # Run the extract command
        mkvextract(*[path, "chapters", "--simple" if simple else ""], _fg=fg)

    @staticmethod
    def selectTracksFromList(
        trackList: list[MediaTrack], selector: typing.Optional[str]
    ) -> list[MediaTrack]:
        """
        Given a list of `MediaTrack`'s, return a selection of these tracks defined
        by a `selector` following a particular syntax.

        ### The selector must obey one of the following rules:

        The selection starts with _no_ tracks selected.

        A constant value:
        - `"none"` or empty string or `None`, returns nothing (an empty array).
        - `"all"` will return all the input tracks (cloning the array).

        A comma-delimited list of indexes and/or ranges:
        - These indexes are in reference to the list of tracks passed to the method.
        - No spaces allowed!
        - Ranges follow the same rules and basic syntax as Python slice ranges.
          E.g. `1:3` or `:-1`

        A colon-delimitted list of python expressions:
        - Each expression either adds to the selection or removes from it.
          - This is defined by starting your expression with an operator; `+` or `-`.
          - `+` is implied if no operator is given.
        - Each expression must return a boolean value.
        - `"all"` is a valid expression and will add or remove (why?) all tracks from the selection.
        - There are lots of pre-calculated boolean flags and other variables available
          during evaluation of your expression. Inspect source code of this method
          to learn all of the available variables.
        - Examples;
          - `+isEnglish`, include only english language tracks.
          - `+all:-isImage` or `+!isImage`, include only non-image subtitle tracks.
          - `+isTrueHD:+'commentary' in title.lower()`. include Dolby TrueHD tracks and any tracks labelled commentary.
        """
        # "none" is a valid selector. Returns an empty list.
        # Empty or falsy strings are treated the same as "none"
        if selector == "none" or not selector:
            return []

        # ... As is "all". Returns every track passed in.
        if selector == "all":
            return trackList.copy()

        # The selector may also be a comma delimited list of track indexes and ranges.
        if commaDelimitedNumbersPattern.match(selector):
            indexedTracks: list[MediaTrack] = []

            # Iterate through the arguments in the list
            for argument in selector.split(","):
                # If there is a colon character, the argument is a range
                if ":" in argument:
                    rangeStart, rangeEnd = (
                        (int(s) if s else None) for s in argument.split(":")
                    )
                    for track in trackList[rangeStart:rangeEnd]:
                        indexedTracks.append(track)

                # Else, it's just a index number
                else:
                    indexedTracks.append(trackList[int(argument)])

            return [track for track in trackList if track in indexedTracks]

        # Start with an empty list
        selectedTracks: list[MediaTrack] = []

        # Split the selector string into a list of selector fragments
        selectorFragments = selector.split(":")

        # Iterate through each fragment consecutively and evaluate them
        for fragment in selectorFragments:
            try:
                polarity, expression = trackSelectorFragmentPattern.match(
                    fragment
                ).groups()
            except AttributeError:
                raise RuntimeError(
                    f"Could not parse selector fragment '{fragment}'. Re-examine your selector syntax."
                )

            filteredTracks: list[MediaTrack] = []

            if expression == "all":
                filteredTracks = trackList

            # Iterate through each track and apply the specified expression to filter
            else:
                for track in trackList:
                    hdrFormat = (
                        (track.HDR_Format or "")
                        + " "
                        + (track.HDR_Format_Compatibility or "")
                    ).lower()

                    trackLocals = {
                        # Fields copied from the track
                        "track": track,
                        "id": track.ID,
                        "lang": track.Language,
                        "title": track.Title or "",
                        "codec": track.CodecID,
                        # Generic flags
                        "isDefault": track.Default or False,
                        "isForced": track.Forced
                        or "forced" in (track.Title or "").lower(),
                        "isVideo": track.Type == MediaTrackType.Video,
                        "isAudio": track.Type == MediaTrackType.Audio,
                        "isSubtitle": track.Type == MediaTrackType.Subtitles,
                        "isSubtitles": track.Type == MediaTrackType.Subtitles,
                        "isEnglish": (track.Language or "").lower()
                        in ["en", "eng"],
                        # Video track flags
                        "isHEVC": "hevc" in (track.CodecID or "").lower(),
                        "isAVC": "avc" in (track.CodecID or "").lower(),
                        "isHDR": bool(hdrFormat.strip()),
                        "isDoVi": "dolby" in hdrFormat,
                        "isHDR10Plus": "hdr10+" in hdrFormat,
                        # Audio track flags
                        "isAAC": "aac" in (track.CodecID or "").lower(),
                        "isAC3": "_ac3" in (track.CodecID or "").lower(),
                        "isEAC3": "eac3" in (track.CodecID or "").lower(),
                        "isDTS": "dts" in (track.CodecID or "").lower(),
                        "isDTSHD": "dts-hd"
                        in (track.Format_Commercial_IfAny or "").lower(),
                        "isTrueHD": "truehd" in (track.CodecID or "").lower(),
                        # Subtitle track flags
                        "isText": (track.CodecID or "")
                        .lower()
                        .startswith("s_text"),
                        "isImage": (
                            not (track.CodecID or "")
                            .lower()
                            .startswith("s_text")
                        ),
                        "isSDH": "sdh" in (track.Title or "").lower(),
                    }

                    # Evaluate the expression
                    try:
                        evalResult = eval(expression, None, trackLocals)
                    except Exception:
                        raise RuntimeError(
                            f"Exception encountered while evaluating selector expression '{expression}'. Re-examine your selector syntax."
                        )

                    # If the result isn't a boolean, raise an exception
                    if not isinstance(evalResult, bool):
                        raise RuntimeError(
                            f"Return type of selector expression '{expression}' was not boolean. Re-examine your selector syntax."
                        )

                    if evalResult:
                        filteredTracks.append(track)

            # If polarity is positive, add the filtered tracks into the selected tracks
            # list, in its original order.
            if not polarity or polarity == "+":
                selectedTracks = [
                    track
                    for track in trackList
                    if (track in filteredTracks or track in selectedTracks)
                ]

            # Else, filter the selected tracks list by the filtered tracks
            else:
                selectedTracks = [
                    track
                    for track in selectedTracks
                    if track not in filteredTracks
                ]

        return selectedTracks

    def selectTracks(self, selector: str) -> list[MediaTrack]:
        return self.selectTracksFromList(self.tracks, selector)

    def selectTracksByType(
        self, trackType: MediaTrackType, selector: str
    ) -> list[MediaTrack]:
        return self.selectTracksFromList(
            self.tracksByType[trackType], selector
        )


class SRTFile(MediaFile):
    """
    SRT files are tricky to deal with. They aren't always detected as valid media
    containers. Using this special class will make their behavior more consistent.
    """

    def __init__(self, path: pathlib.Path, language: str = "en") -> None:
        super().__init__(path)

        # If the subtitle track was not detected, generate a fake one.
        if len(self.tracks) == 0:
            self.tracks.append(
                MediaTrack(
                    self,
                    ID=1,
                    UniqueID=str(hash(str(path))),
                    Type=MediaTrackType.Subtitles,
                    Format="SubRip",
                    CodecID="S_TEXT/UTF8",
                    Language=language,
                    Default=True,
                    Forced=False,
                )
            )
