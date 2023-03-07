# stdlib imports
import dataclasses
import enum
import functools
import json
import pathlib
import typing

# vendor imports
import dataclass_wizard
import dataclass_wizard.enums
import dataclass_wizard.loaders
import sh

ffprobe = sh.Command("ffprobe")


class StreamType(enum.Enum):
    """Enum representing the base type of a stream."""

    Video = "video"
    Audio = "audio"
    Subtitle = "subtitle"
    Attachment = "attachment"


@dataclasses.dataclass
class StreamDisposition(dataclass_wizard.JSONWizard):
    """Disposition flags of a stream. Default, forced, visual impaired, etc."""

    default: bool
    dub: bool
    original: bool
    comment: bool
    lyrics: bool
    karaoke: bool
    forced: bool
    hearing_impaired: bool
    visual_impaired: bool
    clean_effects: bool
    attached_pic: bool
    timed_thumbnails: bool
    captions: bool
    descriptions: bool
    metadata: bool
    dependent: bool
    still_image: bool


class SideDataType(enum.Enum):
    """Enum of known `side_data_type` values."""

    DolbyVisionConfig = "DOVI configuration record"
    DolbyVisionRPU = "Dolby Vision RPU Data"
    DolbyVisionMeta = "Dolby Vision Metadata"

    HDRDynamicMeta = "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"

    MasterDisplayMeta = "Mastering display metadata"
    ContentLightMeta = "Content light level metadata"


class HDRFormat(enum.Enum):
    """Enum of recognized/detected HDR formats."""

    HDR10 = "hdr10"
    HDR10Plus = "hdr10plus"
    DolbyVision = "dolbyvision"
    HLG = "hlg"


@dataclasses.dataclass
class Stream(dataclass_wizard.JSONWizard):
    """Representation of a single stream within a container. Contains all relevant information therein."""

    disposition: StreamDisposition

    # Generic fields
    index: int
    type: typing.Annotated[StreamType, dataclass_wizard.json_key("codec_type")]
    start_time: str
    codec_name: typing.Optional[str] = None
    codec_long_name: typing.Optional[str] = None
    duration: typing.Optional[str] = None
    extradata_size: typing.Optional[int] = None

    # Video fields
    width: typing.Optional[int] = None
    height: typing.Optional[int] = None
    coded_width: typing.Optional[int] = None
    coded_height: typing.Optional[int] = None
    display_aspect_ratio: typing.Optional[str] = None
    pix_fmt: typing.Optional[str] = None
    level: typing.Optional[int] = None
    field_order: typing.Optional[str] = None
    avg_frame_rate: typing.Optional[str] = None
    color_range: typing.Optional[str] = None
    color_space: typing.Optional[str] = None
    color_transfer: typing.Optional[str] = None
    color_primaries: typing.Optional[str] = None
    chroma_location: typing.Optional[str] = None

    # Audio fields
    sample_fmt: typing.Optional[str] = None
    sample_rate: typing.Optional[str] = None
    channels: typing.Optional[int] = None
    channel_layout: typing.Optional[str] = None
    bits_per_raw_sample: typing.Optional[str] = None

    tags: dict[str, str] = dataclasses.field(default_factory=dict)
    side_data_list: list[dict[str, typing.Any]] = dataclasses.field(
        default_factory=list
    )

    # Properties
    @property
    def language(self) -> typing.Optional[str]:
        """Convenience property for reading the language tag of this stream."""
        return self.tags.get("language", None)

    @property
    def title(self) -> typing.Optional[str]:
        """Convenience property for reading the title tag of this stream."""
        return self.tags.get("title", None)

    @property
    def type_index(self) -> int:
        """
        Property to get this stream's index _in relation_ to other streams
        of the same type.

        Requires that this `Stream` instance is bound to a parent `Container`
        instance. This happens automatically if you use the `Container.open()`
        class method, but if you manually instantiate a `Stream` instance you
        may have issues. This proprty returns `-1` if it is invoked with
        no bound `Container`.
        """
        if self.container is None:
            return -1

        i: int = 0
        for stream in self.container.streams:
            if stream == self:
                break
            if stream.type == self.type:
                i += 1
        return i

    @functools.cached_property
    def hdr_formats(self) -> set[HDRFormat]:
        """
        Property containing a set of the HDR formats detected in the stream.

        Only works on video streams, and requires a bound `Container` instance.

        Warning: the first access of this property will have a slight delay as it
        is probed for more information. This result will be cached and will not
        cause delays on further access of the same instance.
        """
        assert self.type is StreamType.Video
        assert self.container is not None

        formats: set[HDRFormat] = set()

        # Detecting HDR10 and HLG is just a matter of reading the video stream's color transfer
        if self.color_transfer == "smpte2084":
            formats.add(HDRFormat.HDR10)
        elif self.color_transfer == "arib-std-b67":
            formats.add(HDRFormat.HLG)

        # To detect the other formats, we'll have to run a probe on the track
        # through the first couple of frames.
        results = ffprobe(
            "-hide_banner",
            "-loglevel",
            "warning",
            "-select_streams",
            f"v:{self.index}",
            "-print_format",
            "json",
            "-show_frames",
            "-read_intervals",
            "%+#10",
            "-show_entries",
            "frame=color_space,color_primaries,color_transfer,side_data_list,pix_fmt",
            "-i",
            self.container.format.filename,
        )
        assert isinstance(results, str)

        # Search through the side data list entries for any that indicate
        # a particular HDR format.
        for frame in json.loads(results).get("frames", []):
            for side_data_entry in frame.get("side_data_list", []):
                side_data_type = side_data_entry.get("side_data_type", None)
                if side_data_type == SideDataType.DolbyVisionRPU.value:
                    formats.add(HDRFormat.DolbyVision)
                if side_data_type == SideDataType.HDRDynamicMeta.value:
                    formats.add(HDRFormat.HDR10Plus)

        return formats

    @property
    def is_hdr(self) -> bool:
        """
        Simple boolean property indicating if the stream is encoded in an HDR format.

        See `Stream.hdr_formats` for more details information.
        """
        return bool(len(self.hdr_formats))

    def __post_init__(self):
        self.container: typing.Optional["Container"] = None

    def _bind(self, container: "Container") -> None:
        self.container = container


@dataclasses.dataclass
class Chapter(dataclass_wizard.JSONWizard):
    """Representation of a single chapter defined within a container."""

    id: int
    start: int
    start_time: str
    end: int
    end_time: str

    tags: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def title(self) -> typing.Optional[str]:
        """Convenience property for reading the title tag of this chapter."""
        return self.tags.get("title", None)


@dataclasses.dataclass
class ContainerFormat(dataclass_wizard.JSONWizard):
    """Format metadata of a container"""

    filename: str
    streams: typing.Annotated[int, dataclass_wizard.json_key("nb_streams")]
    # programs: typing.Annotated[int, dataclass_wizard.json_key("nb_programs")]  # Still not sure what "programs" are
    format_name: str
    format_long_name: str
    start_time: str
    duration: str
    size: int  # Cast from str
    bit_rate: int  # Cast from str
    probe_score: int

    tags: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Container(dataclass_wizard.JSONWizard):
    """Do NOT instantiate this class manually, use the `Container.open()` class method instead."""

    format: ContainerFormat
    streams: list[Stream] = dataclasses.field(repr=False)
    chapters: list[Chapter] = dataclasses.field(repr=False)

    _raw: typing.Annotated[
        typing.Optional[dict], dataclass_wizard.json_key(dump=False)
    ] = dataclasses.field(default=None, repr=False, hash=False, compare=False)
    """Raw JSON probe data for this container, parsed to a Python object with no typings."""

    @property
    def streams_by_type(self) -> dict[StreamType, list[Stream]]:
        """Property returns a dictionary grouping streams by their type."""
        groups: dict[StreamType, list[Stream]] = {
            StreamType.Video: [],
            StreamType.Audio: [],
            StreamType.Subtitle: [],
            StreamType.Attachment: [],
        }

        for stream in self.streams:
            groups[stream.type].append(stream)

        return groups

    @classmethod
    def open(cls, path: pathlib.Path) -> "Container":
        """Open a media container by its path and return a `Container` instance representing it."""
        raw = ffprobe(
            "-hide_banner",
            "-v",
            "quiet",
            # Leave these args here in case they need to be added again later
            # "-select_streams",
            # "v",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            path,
        )
        assert isinstance(raw, str)

        # Parse the JSON into a new instance
        inst = Container.from_json(raw)
        assert not isinstance(inst, list)

        # Parse the json to a python object and store it in the raw attribute
        inst._raw = json.loads(raw)

        # Bind all the tracks detected back to this container
        for stream in inst.streams:
            stream._bind(inst)

        return inst
