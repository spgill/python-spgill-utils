"""
Module for performing mux operations on media files.

Module is based on the mkvtoolnix toolchain, so the output must always be
a Matroska file.
"""

### stdlib imports
import enum
import pathlib
import typing

### vendor imports
import sh

### local imports
from . import exceptions, info, tools

_mkvmerge = sh.Command("mkvmerge")


OptionValue = typing.Union[str, bool, pathlib.Path]
"""Accepted value types for track/container/global mux options."""


class _BaseOptionFormatter:
    def __init__(self, option: str) -> None:
        self.option = option

    def format(
        self, value: OptionValue, track: typing.Optional[info.Track]
    ) -> list[str]:
        return [self.option]


class _UnaryOptionFormatter(_BaseOptionFormatter):
    # No change from the base formatter
    pass


class _BooleanOptionFormatter(_BaseOptionFormatter):
    def format(
        self, value: OptionValue, track: typing.Optional[info.Track]
    ) -> list[str]:
        assert isinstance(value, bool)
        assert track is not None
        return [self.option, f"{track.index}:{int(value)}"]


class _StringOptionFormatter(_BaseOptionFormatter):
    def format(
        self, value: OptionValue, track: typing.Optional[info.Track]
    ) -> list[str]:
        assert isinstance(value, (str, pathlib.Path))
        assert track is not None
        return [self.option, f"{track.index}:{value}"]


class OutputOption(enum.Enum):
    """Options for the output container."""

    Title = enum.auto()
    """Sets the general title for the output file, e.g. the movie name."""


class ContainerOption(enum.Enum):
    """Options for containers used as the mux input."""

    NoChapters = enum.auto()
    """Don't copy chapters from this file."""

    NoAttachments = enum.auto()
    """Don't copy attachments from this file."""

    NoGlobalTags = enum.auto()
    """Don't copy global tags from this file."""

    NoTrackTags = enum.auto()
    """Don't copy any track specific tags from this file."""


class TrackOption(enum.Enum):
    """Options for muxing tracks."""

    # String track attributes
    Name = enum.auto()
    """Sets the track name for the given track"""

    Language = enum.auto()
    """Sets the language for the given track. Both ISO 639-2 language codes and ISO 639-1 country codes are allowed. The country codes will be converted to language codes automatically."""

    Tags = enum.auto()
    """Read tags for the track from the file name"""

    Charset = enum.auto()
    """Sets the character set for the conversion to UTF-8 for UTF-8 subtitles. If not specified the charset will be derived from the current locale settings."""

    # Boolean track flags
    Default = enum.auto()
    """This track is eligible to be played by default."""

    Enabled = enum.auto()
    """Legacy option for compatibility. Best not to be used."""

    Forced = enum.auto()
    """This track contains onscreen text or foreign-language dialogue."""

    HearingImpaired = enum.auto()
    """This track is suitable for users with hearing impairments."""

    VisualImpaired = enum.auto()
    """This track is suitable for users with visual impairments."""

    TextDescriptions = enum.auto()
    """This track contains textual descriptions of video content."""

    OriginalLanguage = enum.auto()
    """This track is in the content's original language (not a translation)."""

    Commentary = enum.auto()
    """This track contains commentary."""

    # Unary flags
    ReduceToCore = enum.auto()
    """Drop all HD extensions from an audio track and keep only its lossy core. This works only for DTS tracks."""


_AnyOption = typing.Union[OutputOption, ContainerOption, TrackOption]

_option_formatters: dict[_AnyOption, _BaseOptionFormatter] = {
    # Output options
    OutputOption.Title: _StringOptionFormatter("--title"),
    #
    #
    # Container options
    ContainerOption.NoChapters: _UnaryOptionFormatter("--no-chapters"),
    ContainerOption.NoAttachments: _UnaryOptionFormatter("--no-attachments"),
    ContainerOption.NoGlobalTags: _UnaryOptionFormatter("--no-global-tags"),
    ContainerOption.NoTrackTags: _UnaryOptionFormatter("--no-track-tags"),
    #
    #
    # Track options
    TrackOption.Name: _StringOptionFormatter("--track-name"),
    TrackOption.Language: _StringOptionFormatter("--language"),
    TrackOption.Tags: _StringOptionFormatter("--tags"),
    TrackOption.Charset: _StringOptionFormatter("--sub-charset"),
    TrackOption.Default: _BooleanOptionFormatter("--default-track-flag"),
    TrackOption.Enabled: _BooleanOptionFormatter("--track-enabled-flag"),
    TrackOption.Forced: _BooleanOptionFormatter("--forced-display-flag"),
    TrackOption.HearingImpaired: _BooleanOptionFormatter(
        "--hearing-impaired-flag"
    ),
    TrackOption.VisualImpaired: _BooleanOptionFormatter(
        "--visual-impaired-flag"
    ),
    TrackOption.TextDescriptions: _BooleanOptionFormatter(
        "--text-descriptions-flag"
    ),
    TrackOption.OriginalLanguage: _BooleanOptionFormatter("--original-flag"),
    TrackOption.Commentary: _BooleanOptionFormatter("--commentary-flag"),
    TrackOption.ReduceToCore: _UnaryOptionFormatter("--reduce-to-core"),
}
"""Mapping of all output/container/track options to the correct formatter types."""

_container_options_for_type: dict[
    info.TrackType,
    dict[typing.Literal["select", "exclude"], str],
] = {
    info.TrackType.Video: {
        "select": "--video-tracks",
        "exclude": "--no-video",
    },
    info.TrackType.Audio: {
        "select": "--audio-tracks",
        "exclude": "--no-audio",
    },
    info.TrackType.Subtitle: {
        "select": "--subtitle-tracks",
        "exclude": "--no-subtitles",
    },
}
"""Mapping of track types to the corresponding CLI options for including/excluding tracks from a source container."""


class MuxJob:
    """Class representing a media mux operation resulting in a single output file."""

    output: pathlib.Path
    """File path of the output container."""

    _output_options: dict[OutputOption, OptionValue]
    _container_options: dict[
        info.Container, dict[ContainerOption, OptionValue]
    ]
    _track_options: dict[info.Track, dict[TrackOption, OptionValue]]
    _track_order: list[info.Track]

    def __init__(
        self,
        output: pathlib.Path,
        /,
        output_options: typing.Optional[
            dict[OutputOption, OptionValue]
        ] = None,
    ) -> None:
        self.output = output

        # Initialize all of the options instance vars
        self._output_options = output_options or {}
        self._container_options = {}
        self._track_options = {}
        self._track_order = []

    def set_output_options(
        self, options: dict[OutputOption, OptionValue]
    ) -> None:
        """Set the output options, replacing any previously stored values."""
        self._output_options = options

    def update_output_options(
        self, options: dict[OutputOption, OptionValue]
    ) -> None:
        """Update the output options in-place."""
        self._output_options.update(options)

    def get_output_options(self) -> dict[OutputOption, OptionValue]:
        """Return the stored output options."""
        return self._output_options

    def _is_container_referenced(self, container: info.Container) -> bool:
        for track in self._track_order:
            if track.container is container:
                return True
        return False

    def set_container_options(
        self,
        container: info.Container,
        options: dict[ContainerOption, OptionValue],
    ) -> None:
        """Set options for the specified container, replacing any previously stored values."""
        self._container_options[container] = options

    def update_container_options(
        self,
        container: info.Container,
        options: dict[ContainerOption, OptionValue],
    ) -> None:
        """Update options for the specified container in-place."""
        if container in self._container_options:
            self._container_options[container].update(options)
        else:
            self.set_container_options(container, options)

    def get_container_options(
        self, container: info.Container
    ) -> dict[ContainerOption, OptionValue]:
        """Return the stored options for the specified container."""
        return self._container_options.get(container, {})

    def delete_container_options(self, container: info.Container) -> None:
        """Delete any stored options for the specified container."""
        if container in self._container_options:
            del self._container_options[container]

    def set_track_options(
        self,
        track: info.Track,
        options: dict[TrackOption, OptionValue],
    ) -> None:
        """Set options for the specified track, replacing any previously stored values."""
        self._track_options[track] = options

    def update_track_options(
        self,
        track: info.Track,
        options: dict[TrackOption, OptionValue],
    ) -> None:
        """Update options for the specified track in-place."""
        if track in self._track_options:
            self._track_options[track].update(options)
        else:
            self.set_track_options(track, options)

    def get_track_options(
        self, track: info.Track
    ) -> dict[TrackOption, OptionValue]:
        """Return the stored options for the specified track."""
        return self._track_options.get(track, {})

    def delete_track_options(self, track: info.Track) -> None:
        """Delete any stored options for the specified track."""
        if track in self._track_options:
            del self._track_options[track]

    def _is_track_referenced(self, track: info.Track) -> bool:
        return track in self._track_order

    def append_track(
        self,
        track: info.Track,
        options: typing.Optional[dict[TrackOption, OptionValue]] = None,
    ) -> None:
        """Append a new track onto the output. Optionally, apply `options` to this track."""
        # Raise an exception if the track already exists. We can't duplicate tracks
        if self._is_track_referenced(track):
            raise exceptions.MuxDuplicateTrackFound(track)
        self._track_order.append(track)
        if options:
            self.set_track_options(track, options)

    def append_srt_track(
        self,
        container: info.Container,
        options: typing.Optional[dict[TrackOption, OptionValue]] = None,
    ) -> None:
        """
        Convenience function for appending an SRT container to a mux job.

        This method will automatically try to guess the charset of the subtitle
        file and set the appropriate option so that any charset conversion can take
        place when the mux operation is performed.

        The methodology used here may apply to other text-based subtitle formats,
        but the scope of this method will be strictly limited to SRT files.
        """
        assert container.format.format_name == "srt"

        charset = tools.guess_subtitle_charset(container.format.filename)

        self.append_track(
            container.tracks[0],
            {**(options or {}), TrackOption.Charset: charset},
        )

    def append_all_tracks(
        self,
        container: info.Container,
        /,
        container_options: typing.Optional[
            dict[ContainerOption, OptionValue]
        ] = None,
        common_track_options: typing.Optional[
            dict[TrackOption, OptionValue]
        ] = None,
    ) -> None:
        """
        Append all tracks from a container into the output.

        Args:
            container_options (optional): Options to apply to the container
            common_track_options (optional): Options that will be applied to every
                track copied from the container. Keep in mind that if you use this
                _and_ you want to apply options individually afterwards that you
                will need to use the `MuxJob.update_track_options` function instead
                of `MuxJob.set_track_options` or else the common options applied
                here will be removed.
        """
        if container_options:
            self.set_container_options(container, container_options)

        for track in container.tracks:
            self.append_track(track, common_track_options)

    def insert_track(self, index: int, track: info.Track) -> None:
        """Insert a new track onto the output at a specific index."""
        # Raise an exception if the track already exists. We can't duplicate tracks
        if self._is_track_referenced(track):
            raise exceptions.MuxDuplicateTrackFound(track)
        self._track_order.insert(index, track)

    def remove_track(
        self,
        track: info.Track,
        /,
        cleanup_track_options: bool = True,
        cleanup_container_options: bool = True,
    ) -> None:
        """
        Remove a track from the output.

        Args:
            cleanup_track_options (optional): Cleans up stored option values for this track. This is to prevent unexpected
                option values if the track is added again. Defaults to `True`.
            cleanup_container_options (optional): Cleans up stored container options IF AND ONLY IF this was the last
                track referencing the container. Useful to prevent unexpected option values if a track from this
                container is added again. Defaults to `True`.
        """
        # Raise an exception if the track DOES NOT exist
        if not self._is_track_referenced(track):
            raise exceptions.MuxTrackNotFound(track)
        self._track_order.remove(track)

        if cleanup_track_options:
            self.delete_track_options(track)

        container = track.container
        if (
            container
            and cleanup_container_options
            and not self._is_container_referenced(container)
        ):
            self.delete_container_options(container)

    def _infer_flags_from_name(self) -> None:
        # Iterate through all tracks and use their names to infer boolean flags
        # that should be assigned to them.
        for track in self._track_order:
            current_options = self.get_track_options(track)
            name = str(
                (current_options.get(TrackOption.Name, track.name) or "")
            ).lower()

            new_options: dict[TrackOption, OptionValue] = {}

            if "forced" in name:
                new_options[TrackOption.Forced] = True

            if "sdh" in name:
                new_options[TrackOption.HearingImpaired] = True

            if "descriptive" in name or "descriptions" in name:
                new_options[TrackOption.TextDescriptions] = True

            if "commentary" in name:
                new_options[TrackOption.Commentary] = True

            self.update_track_options(track, new_options)

    def _assign_default_flags(self) -> None:
        # Group all of the tracks by language and then by type of track
        tracks_by_language_by_type: dict[
            str, dict[info.TrackType, list[info.Track]]
        ] = {}
        for track in self._track_order:
            language = track.language or "und"
            if language not in tracks_by_language_by_type:
                tracks_by_language_by_type[language] = {}
            if track.type not in tracks_by_language_by_type[language]:
                tracks_by_language_by_type[language][track.type] = []
            tracks_by_language_by_type[language][track.type].append(track)

        # Next we will iterate through the tracks of each language and identify
        # candidates for default track. If a track is disqualified as a candidate
        # its flag will be immediate set to false
        for _, tracks_by_type in tracks_by_language_by_type.items():
            for _, tracks in tracks_by_type.items():
                default_found: bool = False
                alternate: typing.Optional[info.Track] = None
                for track in tracks:
                    current_options = self.get_track_options(track)
                    name = str(
                        (
                            current_options.get(TrackOption.Name, track.name)
                            or ""
                        )
                    ).lower()

                    new_options: dict[TrackOption, OptionValue] = {}

                    # Determine values of flags based on the current stored value
                    # in the track OR currently stored mux options
                    is_forced = bool(
                        current_options.get(
                            TrackOption.Forced, track.flags.forced
                        )
                    )
                    is_hi = bool(
                        current_options.get(
                            TrackOption.HearingImpaired,
                            track.flags.hearing_impaired,
                        )
                    )
                    is_commentary = bool(
                        current_options.get(
                            TrackOption.Commentary, track.flags.commentary
                        )
                    )
                    # I wish there was an MKV flag for this scenario but alas
                    is_compatibility = "compatibility" in name

                    # If any of these conditions are true, then the track should
                    # not be a default track, under normal circumstances
                    if is_forced or is_hi or is_commentary or is_compatibility:
                        new_options[TrackOption.Default] = False

                    # HI or compatibility tracks, in an ideal scenario,  will never
                    # be default. But they will remain an alternate should no other
                    # acceptable candidates be found
                    if (is_hi or is_compatibility) and not alternate:
                        alternate = track

                    # Else, this track is a candidate for default track
                    else:
                        new_options[TrackOption.Default] = not default_found
                        default_found = True

                    self.update_track_options(track, new_options)

                # If no default track was ever found, but there was an alternate,
                # the flag will be given to the alternate
                if not default_found and alternate:
                    default_found = True
                    self.update_track_options(
                        alternate, {TrackOption.Default: True}
                    )

                # If by some stroke of dumb luck a default track was not found,
                # then we need to debug
                assert default_found

    def _assign_sensible_names(self) -> None:
        # Determine if there are multiple video tracks
        multiple_video_tracks = (
            len(
                [
                    t
                    for t in self._track_order
                    if t.type is info.TrackType.Video
                ]
            )
            > 1
        )

        # Iterate through each output track and assign names based on guidelines
        for track in self._track_order:
            current_options = self.get_track_options(track)
            new_options: dict[TrackOption, OptionValue] = {}

            name = str(
                (current_options.get(TrackOption.Name, track.name) or "")
            )

            language = str(
                (
                    current_options.get(TrackOption.Language, track.language)
                    or ""
                )
            )

            is_default = bool(
                current_options.get(TrackOption.Default, track.flags.default)
            )

            is_hi = bool(
                current_options.get(
                    TrackOption.HearingImpaired,
                    track.flags.hearing_impaired,
                )
            )

            is_commentary = bool(
                current_options.get(
                    TrackOption.Commentary, track.flags.commentary
                )
            )

            # Video track rules
            if (
                track.type is info.TrackType.Video
                and not multiple_video_tracks
            ):
                new_options[TrackOption.Name] = ""

            # Audio track rules
            if track.type is info.TrackType.Audio:
                # Name not necessary if it's the default track and has a language
                # identifier
                if is_default and language:
                    new_options[TrackOption.Name] = ""

                # If it's commentary and doesn't have a name, give it a generic
                # name, because not all video players can recognize the commentary
                # MKV flag
                if is_commentary and not name:
                    new_options[TrackOption.Name] = "Commentary"

            # Sub track rules
            if track.type is info.TrackType.Subtitle:
                # Name not necessary if it's the default track and has a language
                # identifier
                if is_default and language:
                    new_options[TrackOption.Name] = ""

                # If it's an HI track give it the title "SDH" because not all video
                # players can recognize the hearing impaired flag.
                if is_hi:
                    new_options[TrackOption.Name] = "SDH"

            self.update_track_options(track, new_options)

    def auto_assign_track_options(
        self,
        /,
        infer_flags_from_name: bool = True,
        assign_sensible_names: bool = False,
    ) -> None:
        """
        Automatically assign various boolean flags and track names to the output
        based on sensible guidelines.

        This method is best used immediately before executing the mux operation.
        Invoking this multiple times _may_ result in undefined behavior.

        This method performs several operations in order:

        1.  If `infer_flags_from_name == True`, then the track names will be used
            to assign flags to the track; "commentary" will infer the commentary
            flag, "SDH" will infer the hearing_impaired flag, etc.

        2.  The tracks will be organized by language and type and (approx.) the
            first track of any given language and type will be assigned as the default
            track, and any special tracks (forced, commentary, etc.) will have
            any default flags removed.

        3.  If `assign_sensible_names == True`, then track names will be assigned
            or removed from tracks in a sensible fashion roughly following these
            rules:
                -   Video tracks will have no name unless there are multiple video
                    tracks.
                -   Audio tracks that are the default track AND have a language
                    identifier will have their names removed. Additional audio tracks
                    will keep their name.
                -   Subtitle tracks will not a name unless they have no language
                    identifier OR are a hearing impaired trackunder which case their
                    name will be "SDH" (this is because not all video players are
                    capable of indicating the presence of the hearing impaired flag).

        """
        if infer_flags_from_name:
            self._infer_flags_from_name()

        self._assign_default_flags()

        if assign_sensible_names:
            self._assign_sensible_names()

    def _format_option(
        self,
        option_type: _AnyOption,
        value: OptionValue,
        track: typing.Optional[info.Track] = None,
    ) -> typing.Generator[str, None, None]:
        if option_type not in _option_formatters:
            raise RuntimeError(
                f"There is no formatter defined for mux option: {option_type}"
            )
        formatter = _option_formatters[option_type]
        yield from formatter.format(value, track)

    def _generate_container_arguments(
        self, container: info.Container
    ) -> typing.Generator[str, None, None]:
        options = self.get_container_options(container)

        for option_type, option_value in options.items():
            yield from self._format_option(option_type, option_value)

        yield str(container.format.filename)

    def _generate_track_arguments(
        self, track: info.Track
    ) -> typing.Generator[str, None, None]:
        options = self.get_track_options(track)

        for option_type, option_value in options.items():
            yield from self._format_option(option_type, option_value, track)

    def _generate_output_arguments(self) -> typing.Generator[str, None, None]:
        yield "--output"
        yield str(self.output)

        options = self.get_output_options()
        for option_type, option_value in options.items():
            yield from self._format_option(option_type, option_value)

    def _generate_command_arguments(self) -> typing.Generator[str, None, None]:
        # To being with, we yield argument for the file output
        yield from self._generate_output_arguments()

        # We have to keep track of the absolute order of containers
        container_order: list[info.Container] = []

        # Group all of the source tracks by their container
        tracks_by_container: dict[info.Container, list[info.Track]] = {}
        for track in self._track_order:
            container = track.container

            # Ensure that the track has a parent container
            if container is None:
                raise exceptions.TrackNoParentContainer(track)

            if container not in tracks_by_container:
                tracks_by_container[container] = []

            tracks_by_container[container].append(track)

        # Iterate through each source container and generate all arguments
        for container, tracks in tracks_by_container.items():
            # Start by sorting the streams by type
            tracks_by_type: dict[info.TrackType, list[info.Track]] = {
                track_type: [
                    track for track in tracks if track.type is track_type
                ]
                for track_type in _container_options_for_type.keys()
            }

            # Iterate through each stream type and generator arguments
            for track_type, tracks in tracks_by_type.items():
                options = _container_options_for_type[track_type]
                select_option = options["select"]
                exclude_option = options["exclude"]

                # If there are no stream of this type, yield the exclude option
                if not tracks:
                    yield exclude_option
                    continue

                yield select_option
                yield ",".join([str(track.index) for track in tracks])

                # Yield arguments for the streams
                for track in tracks:
                    yield from self._generate_track_arguments(track)

            # Yield arguments for the container
            yield from self._generate_container_arguments(container)

            if container not in container_order:
                container_order.append(container)

        # Finally, generate and yield the track order
        stream_order_pairs: list[str] = []
        for track in self._track_order:
            assert track.container is not None
            container_idx = container_order.index(track.container)
            stream_order_pairs.append(f"{container_idx}:{track.index}")

        yield "--track-order"
        yield ",".join(stream_order_pairs)

    def run(self, fg=True):
        """Run the mux job command."""
        assert len(self._track_order) > 0  # quick sanity check
        arguments = list(self._generate_command_arguments())
        return _mkvmerge(*arguments, _fg=fg)
