### stdlib imports
import operator
import pathlib
import typing

### vendor imports
import sh

### local imports
import spgill.utils.mux.mediainfo as mediainfo


# Commands
mkvmerge = sh.Command("mkvmerge")


_argsByTrackType: dict[mediainfo.MediaTrackType, typing.Any] = {
    mediainfo.MediaTrackType.Video: {
        "select": "--video-tracks",
        "exclude": "--no-video",
    },
    mediainfo.MediaTrackType.Audio: {
        "select": "--audio-tracks",
        "exclude": "--no-audio",
    },
    mediainfo.MediaTrackType.Subtitles: {
        "select": "--subtitle-tracks",
        "exclude": "--no-subtitles",
    },
}


class MergeGlobalOptions(typing.TypedDict, total=False):
    title: str


class MergeContainerOptions(typing.TypedDict, total=False):
    noChapters: bool
    noAttachments: bool
    noGlobalTags: bool


class MergeTrackOptions(typing.TypedDict, total=False):
    name: str
    charset: str
    default: bool
    forced: bool
    language: str


MergeTrackEntry = tuple[mediainfo.MediaTrack, MergeTrackOptions]


# Mapping of `MergeTrackOptions` to their respective CLI arguments
_trackArgMap: dict[str, str] = {
    "name": "--track-name",
    "title": "--track-name",  # "title" is also valid for track name
    "charset": "--sub-charset",
    "default": "--default-track",
    "forced": "--forced-track",
    "language": "--language",
}


class MergeJob:
    # List of track types accepted as mux sources
    _acceptedTrackTypes: list[mediainfo.MediaTrackType] = [
        mediainfo.MediaTrackType.Video,
        mediainfo.MediaTrackType.Audio,
        mediainfo.MediaTrackType.Subtitles,
    ]

    def __init__(self, output: pathlib.Path) -> None:
        self.output = output

        # Create instance variables
        self._globalOptions: MergeGlobalOptions = {}
        self._containerOptions: dict[
            mediainfo.MediaFile, MergeContainerOptions
        ] = {}
        self._tracks: list[MergeTrackEntry] = []

    def setGlobalOptions(self, options: MergeGlobalOptions) -> None:
        """Set the global output options."""
        self._globalOptions = options

    def setContainerOptions(
        self, source: mediainfo.MediaFile, options: MergeContainerOptions
    ) -> None:
        """Set the options for a source container."""
        self._containerOptions[source] = options

    def addTrack(
        self, source: mediainfo.MediaTrack, options: MergeTrackOptions = {}
    ) -> None:
        """Add a new source track to the output, with options."""
        if source.type not in self._acceptedTrackTypes:
            raise RuntimeError(
                f"Track type of '{source.type}' is not support as a mux source."
            )
        self._tracks.append((source, options))

    def addAllTracks(
        self, source: mediainfo.MediaFile, options: MergeTrackOptions = {}
    ) -> None:
        """
        Quickly add all tracks from a media file to the output.

        NOTE: Silently ignores incompatible track types. These types can be found
        in the `MergeJob._acceptedTrackTypes` class attribute.
        """
        for track in source.tracks:
            if track.type in self._acceptedTrackTypes:
                self.addTrack(track, options)

    def autoAssignDefaultTracks(self):
        """Go through all source tracks and assign default flags automatically."""
        defaultsFoundByLanguage: dict[
            str, dict[mediainfo.MediaTrackType, bool]
        ] = {}
        for track, trackOptions in self._tracks:
            if trackOptions.get("forced", None) is True or (
                trackOptions.get("forced", None) is None and track.forced
            ):
                trackOptions["default"] = False
                continue
            trackLanguage = (
                trackOptions.get("language", None) or track.language or "und"
            )
            if trackLanguage not in defaultsFoundByLanguage:
                defaultsFoundByLanguage[trackLanguage] = {
                    mediainfo.MediaTrackType.Video: True,
                    mediainfo.MediaTrackType.Audio: True,
                    mediainfo.MediaTrackType.Subtitles: True,
                }
            trackOptions["default"] = defaultsFoundByLanguage[trackLanguage][
                track.type
            ]
            defaultsFoundByLanguage[trackLanguage][track.type] = False

    def _generateGlobalArguments(self) -> list[str, pathlib.Path]:
        arguments: list[str, pathlib.Path] = ["-o", self.output]
        return arguments

    def _generateContainerArguments(
        self, container: mediainfo.MediaFile
    ) -> list[str, pathlib.Path]:
        arguments: list[str, pathlib.Path] = []
        containerOptions = self._containerOptions.get(container, {})

        if containerOptions.get("noChapters", False):
            arguments.append("--no-chapters")

        if containerOptions.get("noAttachments", False):
            arguments.append("--no-attachments")

        if containerOptions.get("noGlobalTags", False):
            arguments.append("--no-global-tags")

        return arguments + [container.path]

    def _formatTrackFlag(
        self,
        track: mediainfo.MediaTrack,
        flagName: str,
        flagValue: typing.Union[None, str, bool],
    ) -> list[str]:
        if flagValue is None:
            return [flagName]

        value: str = ""

        if isinstance(flagValue, str):
            value = flagValue
        elif isinstance(flagValue, bool):
            value = str(int(flagValue))

        return [flagName, f"{track.id}:{value}"]

    def _generateTrackArguments(
        self, track: mediainfo.MediaTrack, options: MergeTrackOptions
    ):
        arguments: list[str] = []

        for optionKey, optionValue in options.items():
            if (argName := _trackArgMap.get(optionKey, None)) is not None:
                arguments += self._formatTrackFlag(track, argName, optionValue)

        return arguments

    def _generateCommandArguments(self) -> list[str, pathlib.Path]:
        arguments: list[str, pathlib.Path] = []

        # We need to track order of tracks and source containers
        absoluteTrackOrder: list[mediainfo.MediaTrack] = []
        containerOrder: list[mediainfo.MediaFile] = []

        # We first need to group all of the source tracks by their container file
        tracksByContainer: dict[
            mediainfo.MediaFile,
            list[MergeTrackEntry],
        ] = {}
        for entry in self._tracks:
            source = entry[0].container
            if source not in tracksByContainer:
                tracksByContainer[source] = []
            tracksByContainer[source].append(entry)
            absoluteTrackOrder.append(entry[0])

        # Iterate through each source container and generate all arguments
        for container, trackEntries in tracksByContainer.items():
            # Sort the tracks by type
            tracksByType: dict[
                mediainfo.MediaTrackType, list[MergeTrackEntry]
            ] = {
                trackType: [
                    entry
                    for entry in trackEntries
                    if entry[0].type is trackType
                ]
                for trackType in _argsByTrackType
            }

            # Iterate through each track type and generate arguments
            for trackType, trackEntries in tracksByType.items():
                selectKey, excludeKey = operator.itemgetter(
                    "select", "exclude"
                )(_argsByTrackType[trackType])
                if not len(trackEntries):
                    arguments.append(excludeKey)
                    continue
                arguments += [
                    selectKey,
                    ",".join([str(track.id) for track, _ in trackEntries]),
                ]
                for track, trackOptions in trackEntries:
                    arguments += self._generateTrackArguments(
                        track, trackOptions
                    )

            # Append arguments for container
            arguments += self._generateContainerArguments(container)
            containerOrder.append(container)

        # Generate and append the track order argument
        orderEntries: list[str] = []
        for track in absoluteTrackOrder:
            fileId = containerOrder.index(track.container)
            orderEntries.append(f"{fileId}:{track.id}")
        arguments += ["--track-order", ",".join(orderEntries)]

        # Prepend the global arguments
        return self._generateGlobalArguments() + arguments

    def run(self, fg: bool = True) -> sh.RunningCommand:
        """Execute the merge operation now."""
        return mkvmerge(self._generateCommandArguments(), _fg=fg)
