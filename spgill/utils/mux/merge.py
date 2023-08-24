"""
THIS MODULE IS DEPRECATED. USE `spgill.utils.media.mux` INSTEAD.
"""

### stdlib imports
import operator
import pathlib
import typing

### vendor imports
import sh
import typing_extensions

### local imports
import spgill.utils.mux.info as info


# Commands
mkvmerge = sh.Command("mkvmerge")


_argsByTrackType: dict[info.MediaTrackType, typing.Any] = {
    info.MediaTrackType.Video: {
        "select": "--video-tracks",
        "exclude": "--no-video",
    },
    info.MediaTrackType.Audio: {
        "select": "--audio-tracks",
        "exclude": "--no-audio",
    },
    info.MediaTrackType.Subtitles: {
        "select": "--subtitle-tracks",
        "exclude": "--no-subtitles",
    },
}

# region Flag formatter functions
ArgInputValue = typing.Union[str, bool]
ArgFormatterMethod = typing.Callable[[int, ArgInputValue], list[str]]
ArgFormatterFactory = typing.Callable[[str], ArgFormatterMethod]


def argFormatterNameIdColonString(argName: str) -> ArgFormatterMethod:
    return lambda id, val: [argName, f"{id}:{val}"]


def argFormatterNameIdColonBoolean(argName: str) -> ArgFormatterMethod:
    return lambda id, val: [argName, f"{id}:{int(val)}"]


def argFormatterNameId(argName: str) -> ArgFormatterMethod:
    return lambda id, val: [argName, str(id)] if val else []


# endregion

# Mapping of `MergeTrackOptions` to their respective CLI arguments
_trackArgMap: dict[str, ArgFormatterMethod] = {
    "name": argFormatterNameIdColonString("--track-name"),
    "title": argFormatterNameIdColonString(
        "--track-name"
    ),  # "title" is also valid for track name
    "language": argFormatterNameIdColonString("--language"),
    "charset": argFormatterNameIdColonString("--sub-charset"),
    "default": argFormatterNameIdColonBoolean("--default-track"),
    "forced": argFormatterNameIdColonBoolean("--forced-track"),
    "reduceToCore": argFormatterNameId("--reduce-to-core"),
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
    reduceToCore: bool


MergeTrackEntry = tuple[info.MediaTrack, MergeTrackOptions]


@typing_extensions.deprecated
class MergeJob:
    # List of track types accepted as mux sources
    _acceptedTrackTypes: list[info.MediaTrackType] = [
        info.MediaTrackType.Video,
        info.MediaTrackType.Audio,
        info.MediaTrackType.Subtitles,
    ]

    def __init__(self, output: pathlib.Path) -> None:
        self.output = output

        # Create instance variables
        self._globalOptions: MergeGlobalOptions = {}
        self._containerOptions: dict[
            info.MediaFile, MergeContainerOptions
        ] = {}
        self._tracks: list[MergeTrackEntry] = []

    def setGlobalOptions(self, options: MergeGlobalOptions) -> None:
        """Set the global output options."""
        self._globalOptions = options

    def setContainerOptions(
        self, source: info.MediaFile, options: MergeContainerOptions
    ) -> None:
        """Set the options for a source container."""
        self._containerOptions[source] = options

    def addTrack(
        self, source: info.MediaTrack, options: MergeTrackOptions = {}
    ) -> None:
        """Add a new source track to the output, with options."""
        if source.Type not in self._acceptedTrackTypes:
            raise RuntimeError(
                f"Track type of '{source.Type}' is not support as a mux source."
            )
        self._tracks.append((source, options.copy()))

    def addAllTracks(
        self, source: info.MediaFile, options: MergeTrackOptions = {}
    ) -> None:
        """
        Quickly add all tracks from a media file to the output.

        NOTE: Silently ignores incompatible track types. These types can be found
        in the `MergeJob._acceptedTrackTypes` class attribute.
        """
        for track in source.tracks:
            if track.Type in self._acceptedTrackTypes:
                self.addTrack(track, options.copy())

    def autoAssignDefaultFlags(self):
        """Go through all source tracks and assign default flags automatically."""
        defaultsFoundByLanguage: dict[
            str, dict[info.MediaTrackType, bool]
        ] = {}
        for track, trackOptions in self._tracks:
            if trackOptions.get("forced", None) is True or (
                trackOptions.get("forced", None) is None and track.Forced
            ):
                trackOptions["default"] = False
                continue
            trackLanguage = (
                trackOptions.get("language", None) or track.Language or "und"
            )
            if trackLanguage not in defaultsFoundByLanguage:
                defaultsFoundByLanguage[trackLanguage] = {
                    info.MediaTrackType.Video: True,
                    info.MediaTrackType.Audio: True,
                    info.MediaTrackType.Subtitles: True,
                }
            trackOptions["default"] = defaultsFoundByLanguage[trackLanguage][
                track.Type
            ]
            defaultsFoundByLanguage[trackLanguage][track.Type] = False

    def _generateGlobalArguments(self) -> list[str, pathlib.Path]:
        arguments: list[str, pathlib.Path] = ["-o", self.output]
        if "title" in self._globalOptions:
            arguments += ["--title", self._globalOptions["title"]]
        return arguments

    def _generateContainerArguments(
        self, container: info.MediaFile
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

    def _generateTrackArguments(
        self, track: info.MediaTrack, options: MergeTrackOptions
    ):
        arguments: list[str] = []

        for optionKey, optionValue in options.items():
            if formatter := _trackArgMap.get(optionKey, None):
                if optionValue is None:
                    optionValue = ""
                arguments += formatter(track.ID, optionValue)

        return arguments

    def _generateCommandArguments(self) -> list[str, pathlib.Path]:
        arguments: list[str, pathlib.Path] = []

        # We need to track order of tracks and source containers
        absoluteTrackOrder: list[info.MediaTrack] = []
        containerOrder: list[info.MediaFile] = []

        # We first need to group all of the source tracks by their container file
        tracksByContainer: dict[
            info.MediaFile,
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
            tracksByType: dict[info.MediaTrackType, list[MergeTrackEntry]] = {
                trackType: [
                    entry
                    for entry in trackEntries
                    if entry[0].Type is trackType
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
                    ",".join([str(track.ID) for track, _ in trackEntries]),
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
            orderEntries.append(f"{fileId}:{track.ID}")
        arguments += ["--track-order", ",".join(orderEntries)]

        # Prepend the global arguments
        return self._generateGlobalArguments() + arguments

    def run(self, fg: bool = True) -> sh.RunningCommand:
        """Execute the merge operation now."""
        return mkvmerge(self._generateCommandArguments(), _fg=fg)
