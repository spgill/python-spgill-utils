# stdlib imports
import dataclasses
import enum
import functools
import json
import pathlib
import re
import typing

# vendor imports
import dataclass_wizard
import dataclass_wizard.enums
import dataclass_wizard.loaders
import sh

ffprobe = sh.Command("ffprobe")
mkvextract = sh.Command("mkvextract")

selector_fragment_pattern = re.compile(r"^([-+]?)(.*)$")
comma_delim_nos_pattern = re.compile(
    r"^(?:(?:(?<!^),)?(?:[vas]?(?:-?\d+)?(?:(?<=\d)\:|\:(?=-?\d))(?:-?\d+)?|[vas]?-?\d+))+$"
)
index_with_type_pattern = re.compile(r"^([vas]?)(.*?)$")


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


class StreamSelectorValues(typing.TypedDict, total=True):
    # Convenience values
    stream: "Stream"
    index: int
    typeIndex: int
    lang: str
    title: str
    codec: str

    # Generic flags
    isDefault: bool
    isForced: bool
    isVideo: bool
    isAudio: bool
    isSubtitle: bool
    isEnglish: bool
    isCompatibility: bool

    # Video track flags
    isHEVC: bool
    isAVC: bool
    isHDR: bool
    isDoVi: bool
    isHDR10Plus: bool

    # Audio track flags
    isAAC: bool
    isAC3: bool
    isEAC3: bool
    isDTS: bool
    isDTSHD: bool
    isTrueHD: bool

    # Subtitle track flags
    isSRT: bool
    isPGS: bool
    isSDH: bool


@dataclasses.dataclass(unsafe_hash=True)
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
    profile: typing.Optional[str] = None
    sample_fmt: typing.Optional[str] = None
    sample_rate: typing.Optional[str] = None
    channels: typing.Optional[int] = None
    channel_layout: typing.Optional[str] = None
    bits_per_raw_sample: typing.Optional[str] = None

    tags: dict[str, str] = dataclasses.field(default_factory=dict, hash=False)
    side_data_list: list[dict[str, typing.Any]] = dataclasses.field(
        default_factory=list, hash=False
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
        # If this is not a compatible stream, return an empty set
        if self.type is not StreamType.Video or self.container is None:
            return set()

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

    def __repr__(self) -> str:
        attributes = ["index", "type", "codec_name", "title", "language"]
        formatted_attributes: list[str] = []
        for name in attributes:
            formatted_attributes.append(f"{name}={getattr(self, name)!r}")
        return f"{type(self).__name__}({', '.join(formatted_attributes)})"

    def __post_init__(self):
        self.container: typing.Optional["Container"] = None

    def _bind(self, container: "Container") -> None:
        self.container = container

    def get_selector_values(self) -> StreamSelectorValues:
        """
        Return a dictionary mapping of computed stream selector values.

        TODO: Validate the codec-based selectors as they likely need to be adjusted
        based on ffprobe's output.
        """
        return {
            # Convenience values
            "stream": self,
            "index": self.index,
            "typeIndex": self.type_index,
            "lang": self.language or "",
            "title": self.title or "",
            "codec": self.codec_name or "",
            # Generic flags
            "isDefault": self.disposition.default,
            "isForced": self.disposition.forced,
            "isVideo": self.type == StreamType.Video,
            "isAudio": self.type == StreamType.Audio,
            "isSubtitle": self.type == StreamType.Subtitle,
            "isEnglish": (self.language or "").lower() in ["en", "eng"],
            "isCompatibility": "compatibility" in (self.title or "").lower(),
            # Video track flags
            "isHEVC": "hevc" in (self.codec_name or "").lower(),
            "isAVC": "avc" in (self.codec_name or "").lower(),
            "isHDR": self.is_hdr,
            "isDoVi": HDRFormat.DolbyVision in self.hdr_formats,
            "isHDR10Plus": HDRFormat.HDR10Plus in self.hdr_formats,
            # Audio track flags
            "isAAC": "aac" in (self.codec_name or "").lower(),
            "isAC3": "_ac3" in (self.codec_name or "").lower(),
            "isEAC3": "eac3" in (self.codec_name or "").lower(),
            "isDTS": "dts" in (self.codec_name or "").lower(),
            "isDTSHD": "dts" in (self.codec_name or "").lower()
            and "hd" in (self.profile or "").lower(),
            "isTrueHD": "truehd" in (self.codec_name or "").lower(),
            # Subtitle track flags
            # TODO: restore the "isText" and "isImage" fields by establishing a list of text-based sub codecs
            "isSRT": self.codec_name == "subrip",
            "isPGS": self.codec_name == "hdmv_pgs_subtitle",
            "isSDH": "sdh" in (self.title or "").lower(),
        }

    def extract(self, path: pathlib.Path, fg: bool = True):
        """
        Extract this stream to a new file.

        *ONLY WORKS WITH MKV CONTAINERS*
        """
        assert self.container is not None
        self.container.extract_streams([(self, path)], fg)


@dataclasses.dataclass(unsafe_hash=True)
class Chapter(dataclass_wizard.JSONWizard):
    """Representation of a single chapter defined within a container."""

    id: int
    start: int
    start_time: str
    end: int
    end_time: str

    tags: dict[str, str] = dataclasses.field(default_factory=dict, hash=False)

    @property
    def title(self) -> typing.Optional[str]:
        """Convenience property for reading the title tag of this chapter."""
        return self.tags.get("title", None)


@dataclasses.dataclass(unsafe_hash=True)
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

    tags: dict[str, str] = dataclasses.field(default_factory=dict, hash=False)


@dataclasses.dataclass(unsafe_hash=True)
class Container(dataclass_wizard.JSONWizard):
    """Do NOT instantiate this class manually, use the `Container.open()` class method instead."""

    format: ContainerFormat
    streams: list[Stream] = dataclasses.field(repr=False, hash=False)
    chapters: list[Chapter] = dataclasses.field(repr=False, hash=False)

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

    @staticmethod
    def select_streams_from_list(
        stream_list: list[Stream], selector: typing.Optional[str]
    ) -> list[Stream]:
        """
        Given a list of `MediaTrack`'s, return a selection of these streams defined
        by a `selector` following a particular syntax.

        ### The selector must obey one of the following rules:

        The selection starts with _no_ streams selected.

        A constant value:
        - `"none"` or empty string or `None`, returns nothing (an empty array).
        - `"all"` will return all the input streams (cloning the array).

        A comma-delimited list of indexes and/or slices:
        - These indexes are in reference to the list of streams passed to the method.
        - No spaces allowed!
        - Slices follow the same rules and basic syntax as Python slices.
          E.g. `1:3` or `:-1`
        - If the index/slice begins with one of `v` (video), `a` (audio), or
          `s` (subtitle) then the index/range will be taken from only streams
          of that type (wrt the order they appear in the list).

        A colon-delimitted list of python expressions:
        - Each expression either adds to the selection or removes from it.
          - This is defined by starting your expression with an operator; `+` or `-`.
          - `+` is implied if no operator is given.
        - Each expression must return a boolean value.
        - `"all"` is a valid expression and will add or remove (why?) all streams from the selection.
        - There are lots of pre-calculated boolean flags and other variables available
          during evaluation of your expression. Inspect source code of this method
          to learn all of the available variables.
        - Examples;
          - `+isEnglish`, include only english language streams.
          - `+all:-isPGS` or `+!isPGS`, include only non-PGS subtitle streams.
          - `+isTrueHD:+'commentary' in title.lower()`. include Dolby TrueHD streams and any streams labelled commentary.
        """
        # "none" is a valid selector. Returns an empty list.
        # Empty or falsy strings are treated the same as "none"
        if selector == "none" or not selector:
            return []

        # ... As is "all". Returns every stream passed in.
        if selector == "all":
            return stream_list.copy()

        # The selector may also be a comma delimited list of stream indexes and ranges.
        if comma_delim_nos_pattern.match(selector):
            # Create a quick mapping of stream types to streams
            grouped_streams: dict[StreamType, list[Stream]] = {
                StreamType.Video: [],
                StreamType.Audio: [],
                StreamType.Subtitle: [],
            }
            for stream in stream_list:
                if (
                    group_list := grouped_streams.get(stream.type, None)
                ) is not None:
                    group_list.append(stream)

            indexed_streams: list[Stream] = []

            # Iterate through the arguments in the list
            for fragment in selector.split(","):
                fragment_match = index_with_type_pattern.match(fragment)
                assert fragment_match is not None
                argument_type, argument = fragment_match.groups()

                # If a type is specified, we need to change where the streams
                # are selected from
                stream_source = stream_list
                if argument_type == "v":
                    stream_source = grouped_streams[StreamType.Video]
                elif argument_type == "a":
                    stream_source = grouped_streams[StreamType.Audio]
                elif argument_type == "s":
                    stream_source = grouped_streams[StreamType.Subtitle]

                # If there is a colon character, the argument is a range
                if ":" in argument:
                    start, end = (
                        (int(s) if s else None) for s in argument.split(":")
                    )
                    for stream in stream_source[start:end]:
                        indexed_streams.append(stream)

                # Else, it's just a index number
                else:
                    indexed_streams.append(stream_source[int(argument)])

            # Return it as an iteration of the master stream list so that it
            # maintains the original order
            return [
                stream for stream in stream_list if stream in indexed_streams
            ]

        # Start with an empty list
        selected_streams: list[Stream] = []

        # Split the selector string into a list of selector fragments
        selector_fragments = selector.split(":")

        # Iterate through each fragment consecutively and evaluate them
        for fragment in selector_fragments:
            try:
                fragment_match = selector_fragment_pattern.match(fragment)

                if fragment_match is None:
                    raise RuntimeError(
                        f"Could not parse selector fragment '{fragment}'. Re-examine your selector syntax."
                    )

                polarity, expression = fragment_match.groups()
            except AttributeError:
                raise RuntimeError(
                    f"Could not parse selector fragment '{fragment}'. Re-examine your selector syntax."
                )

            filtered_streams: list[Stream] = []

            if expression == "all":
                filtered_streams = stream_list

            # Iterate through each track and apply the specified expression to filter
            else:
                for stream in stream_list:
                    # Evaluate the expression
                    try:
                        evalResult = eval(
                            expression, None, stream.get_selector_values()
                        )
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
                        filtered_streams.append(stream)

            # If polarity is positive, add the filtered tracks into the selected tracks
            # list, in its original order.
            if not polarity or polarity == "+":
                selected_streams = [
                    stream
                    for stream in stream_list
                    if (
                        stream in filtered_streams
                        or stream in selected_streams
                    )
                ]

            # Else, filter the selected tracks list by the filtered tracks
            else:
                selected_streams = [
                    stream
                    for stream in selected_streams
                    if stream not in filtered_streams
                ]

        return selected_streams

    def select_streams(self, selector: str) -> list[Stream]:
        """
        Select streams from _this_ container using a selector string.

        More information on the syntax of the selector string can be found
        in the docstring of the `Container.select_streams_from_list` method.
        """
        return self.select_streams_from_list(self.streams, selector)

    def selectTracksByType(
        self, type: StreamType, selector: str
    ) -> list[Stream]:
        """
        Select streams of a particular type from _this_ container using a selector string.

        More information on the syntax of the selector string can be found
        in the docstring of the `Container.select_streams_from_list` method.
        """
        return self.select_streams_from_list(
            self.streams_by_type[type], selector
        )

    def extract_streams(
        self, stream_pairs: list[tuple[Stream, pathlib.Path]], fg: bool = True
    ):
        """
        Extract one or more tracks from this container.

        *ONLY WORKS WITH MKV CONTAINERS*
        """
        # Assert that this is in fact an MKV container
        assert self.format.format_name.startswith("matroska")

        # Begin building a list of arguments for extraction
        extract_args: list[typing.Union[pathlib.Path, str]] = [
            self.format.filename,
            "tracks",
        ]

        # Iterate through each tuple given and generator appropriate arguments
        for stream, path in stream_pairs:
            # Assert the stream belongs to this container
            assert stream.container is self

            extract_args.append(f"{stream.index}:{path}")

        # Execute the extraction commands
        mkvextract(*extract_args, _fg=fg)

    def extract_chapters(
        self, path: pathlib.Path, simple: bool = False, fg: bool = True
    ):
        """
        Extract _all_ chapters in this container to a new file.

        *ONLY WORTH WITH MKV CONTAINERS*
        """
        # Assert that this is in fact an MKV container
        assert self.format.format_name.startswith("matroska")

        # Call mkvextract to begin the extraction
        mkvextract(path, "chapters", "--simple" if simple else "", _fg=fg)
