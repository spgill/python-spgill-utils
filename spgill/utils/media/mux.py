"""
Module for performing mux operations on media files.

Module is based on the mkvtoolnix toolchain, so the output must always be
a Matroska file.
"""

### stdlib imports
import pathlib
import typing
import typing_extensions

### vendor imports
import sh

### local imports
from . import exceptions, info

mkvmerge = sh.Command("mkvmerge")


class OutputMuxOptions(typing.TypedDict, total=False):
    title: str


class ContainerMuxOptions(typing.TypedDict, total=False):
    no_chapters: bool
    no_attachments: bool
    no_global_tags: bool


class StreamMuxOptions(typing.TypedDict, total=False):
    # String attributes
    title: str
    charset: str

    # Boolean flags
    default: bool
    forced: bool
    reduce_to_core: bool

    enabled: bool
    """This is a legacy attribute. Best not to use it."""

    hearing_impaired: bool
    visual_impaired: bool
    text_descriptions: bool
    original_language: bool
    commentary: bool


_StreamMuxOptionPair = tuple[info.Track, StreamMuxOptions]

_container_options_for_type: dict[info.TrackType, dict[str, str]] = {
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


def _format_option_id_colon_value(
    option: str, index: int, value: typing.Optional[str]
) -> typing.Generator[str, None, None]:
    if value is not None:
        yield option
        yield f"{index}:{value}"


def _format_option_id_colon_boolean(
    option: str, index: int, value: typing.Optional[bool]
) -> typing.Generator[str, None, None]:
    if value is not None:
        yield option
        yield f"{index}:{int(value)}"


def _format_option_id(
    option: str, index: int, value: typing.Optional[bool]
) -> typing.Generator[str, None, None]:
    if value is True:
        yield option
        yield str(index)


class MuxJob:
    output: pathlib.Path

    _output_options: OutputMuxOptions
    _container_options: dict[info.Container, ContainerMuxOptions]
    _streams: list[_StreamMuxOptionPair]

    def __init__(
        self,
        output: pathlib.Path,
        /,
        output_options: typing.Optional[OutputMuxOptions] = None,
        containers: typing.Optional[
            dict[info.Container, ContainerMuxOptions]
        ] = None,
        streams: typing.Optional[list[_StreamMuxOptionPair]] = None,
    ) -> None:
        self.output = output

        self._output_options = output_options or {}
        self._container_options = containers or {}
        self._streams = streams or []

    def get_output_options(
        self,
    ) -> OutputMuxOptions:
        """Get the options for the output container."""
        return self._output_options

    def set_output_options(
        self,
        /,
        **options: typing_extensions.Unpack[OutputMuxOptions],
    ) -> None:
        """Replace the options for the output container."""
        self._output_options = options

    def get_container_options(
        self,
        container: info.Container,
    ) -> ContainerMuxOptions:
        """Get the options for a container in the mux job."""
        return self._container_options.get(container, {})

    def set_container_options(
        self,
        container: info.Container,
        /,
        **options: typing_extensions.Unpack[ContainerMuxOptions],
    ) -> None:
        """Replace the options for a container in the mux job."""
        self._container_options[container] = options

    def update_container_options(
        self,
        container: info.Container,
        /,
        **options: typing_extensions.Unpack[ContainerMuxOptions],
    ) -> None:
        """Replace the options for a container in the mux job."""
        if container in self._container_options:
            self._container_options[container].update(options)
        else:
            self._container_options[container] = options

    def _assert_stream_no_exist(self, stream: info.Track) -> None:
        for existing_stream, _ in self._streams:
            if stream is existing_stream:
                raise exceptions.MuxDuplicateTrackFound(stream)

    def _assert_stream_exist(self, stream: info.Track) -> None:
        for existing_stream, _ in self._streams:
            if stream is existing_stream:
                break
        else:
            raise exceptions.MuxTrackNotFound(stream)

    def _get_stream_entry(
        self, stream: info.Track
    ) -> typing.Optional[_StreamMuxOptionPair]:
        for entry in self._streams:
            if entry[0] is stream:
                return entry

    def append_stream(
        self,
        stream: info.Track,
        /,
        **options: typing_extensions.Unpack[StreamMuxOptions],
    ) -> None:
        """Append a stream to be written to the output."""
        self._assert_stream_no_exist(stream)
        self._streams.append((stream, options))

    def insert_stream(
        self,
        index: int,
        stream: info.Track,
        /,
        **options: typing_extensions.Unpack[StreamMuxOptions],
    ) -> None:
        """Insert a stream at a specific index to be written to the output."""
        self._assert_stream_no_exist(stream)
        self._streams.insert(index, (stream, options))

    def remove_stream(
        self, stream: info.Track, no_exist_okay: bool = True
    ) -> None:
        """Remove a previously added stream. Fails silently if stream doesn't exist."""
        if not no_exist_okay:
            self._assert_stream_exist(stream)
        if entry := self._get_stream_entry(stream):
            self._streams.remove(entry)

    def get_stream_options(
        self,
        stream: info.Track,
    ) -> StreamMuxOptions:
        """Get the options for a stream in the mux job."""
        self._assert_stream_exist(stream)
        existing_entry = self._get_stream_entry(stream)
        assert existing_entry is not None
        return existing_entry[1]

    def set_stream_options(
        self,
        stream: info.Track,
        /,
        **options: typing_extensions.Unpack[StreamMuxOptions],
    ) -> None:
        """Replace the options for a stream in the mux job."""
        self._assert_stream_exist(stream)
        if existing_entry := self._get_stream_entry(stream):
            index = self._streams.index(existing_entry)
            self._streams[index] = (existing_entry[0], options)

    def update_stream_options(
        self,
        stream: info.Track,
        /,
        **options: typing_extensions.Unpack[StreamMuxOptions],
    ) -> None:
        """Replace the options for a stream in the mux job."""
        self._assert_stream_exist(stream)
        if existing_entry := self._get_stream_entry(stream):
            existing_entry[1].update(options)

    def _generate_container_arguments(
        self, container: info.Container
    ) -> typing.Generator[str, None, None]:
        options = self.get_container_options(container)

        if options.get("no_chapters", False):
            yield "--no-chapters"

        if options.get("no_attachments", False):
            yield "--no-attachments"

        if options.get("no_global_tags", False):
            yield "--no-global-tags"

        # Finally, yield the filename
        yield container.format.filename

    def _generate_stream_arguments(
        self, stream: info.Track, options: StreamMuxOptions
    ) -> typing.Generator[str, None, None]:
        # String options
        yield from _format_option_id_colon_value(
            "--track-name", stream.index, options.get("title", None)
        )
        yield from _format_option_id_colon_value(
            "--language", stream.index, options.get("language", None)
        )
        yield from _format_option_id_colon_value(
            "--sub-charset", stream.index, options.get("charset", None)
        )

        # Boolean options
        yield from _format_option_id_colon_boolean(
            "--default-track-flag", stream.index, options.get("default", None)
        )
        yield from _format_option_id_colon_boolean(
            "--track-enabled-flag", stream.index, options.get("enabled", None)
        )
        yield from _format_option_id_colon_boolean(
            "--forced-display-flag", stream.index, options.get("forced", None)
        )
        yield from _format_option_id_colon_boolean(
            "--hearing-impaired-flag",
            stream.index,
            options.get("hearing_impaired", None),
        )
        yield from _format_option_id_colon_boolean(
            "--visual-impaired-flag",
            stream.index,
            options.get("visual_impaired", None),
        )
        yield from _format_option_id_colon_boolean(
            "--text-descriptions-flag",
            stream.index,
            options.get("text_descriptions", None),
        )
        yield from _format_option_id_colon_boolean(
            "--original-flag",
            stream.index,
            options.get("original_language", None),
        )
        yield from _format_option_id_colon_boolean(
            "--commentary-flag", stream.index, options.get("commentary", None)
        )

        # ID options
        yield from _format_option_id(
            "--reduce-to-core",
            stream.index,
            options.get("reduce_to_core", None),
        )

    def _generate_output_arguments(self) -> typing.Generator[str, None, None]:
        yield "--output"
        yield str(self.output)

        options = self.get_output_options()
        if (title := options.get("title", None)) is not None:
            yield "--title"
            yield title

    def _generate_command_arguments(self) -> typing.Generator[str, None, None]:
        # To being with, we yield argument for the file output
        yield from self._generate_output_arguments()

        # We have to keep track of the absolute order of streams and containers
        absolute_order: list[info.Track] = []
        container_order: list[info.Container] = []

        # Group all of the source streams by their container
        streams_by_container: dict[
            info.Container, list[_StreamMuxOptionPair]
        ] = {}
        for stream_pair in self._streams:
            stream = stream_pair[0]
            container = stream.container

            assert container is not None
            if container not in streams_by_container:
                streams_by_container[container] = []

            streams_by_container[container].append(stream_pair)
            absolute_order.append(stream)

        # Iterate through each source container and generate all arguments
        for container, stream_pairs in streams_by_container.items():
            # Start by sorting the streams by type
            stream_pairs_by_type: dict[
                info.TrackType, list[_StreamMuxOptionPair]
            ] = {
                stream_type: [
                    pair
                    for pair in stream_pairs
                    if pair[0].type is stream_type
                ]
                for stream_type in _container_options_for_type.keys()
            }

            # Iterate through each stream type and generator arguments
            for stream_type, stream_pairs in stream_pairs_by_type.items():
                options = _container_options_for_type[stream_type]
                select_option = options["select"]
                exclude_option = options["exclude"]

                # If there are no stream of this type, yield the exclude option
                if not stream_pairs:
                    yield exclude_option
                    continue

                yield select_option
                yield ",".join(
                    [str(stream.index) for stream, _ in stream_pairs]
                )

                # Yield arguments for the streams
                for stream, stream_options in stream_pairs:
                    yield from self._generate_stream_arguments(
                        stream, stream_options
                    )

            # Yield arguments for the container
            yield from self._generate_container_arguments(container)

            if container not in container_order:
                container_order.append(container)

        # Fianlly, generate and yield the track order
        stream_order_pairs: list[str] = []
        for stream in absolute_order:
            assert stream.container is not None
            container_idx = container_order.index(stream.container)
            stream_order_pairs.append(f"{container_idx}:{stream.index}")

        yield "--track-order"
        yield ",".join(stream_order_pairs)

    def run(self, fg=True):
        """Run the mux job command."""
        arguments = list(self._generate_command_arguments())
        return mkvmerge(*arguments, _fg=fg)
