### stdlib imports
import enum
import pathlib
import typing

### vendor imports
import sh

### local imports
import spgill.utils.mux.info as info


# Commands
mkvpropedit = sh.Command("mkvpropedit")


class EditContainerOptions(typing.TypedDict, total=False):
    title: typing.Optional[str]


class EditTrackOptions(typing.TypedDict, total=False):
    name: typing.Optional[str]
    default: typing.Optional[bool]
    forced: typing.Optional[bool]
    language: typing.Optional[str]


class EditTagSelector(enum.Enum):
    All = "all"
    Global = "global"


class EditJob:
    # List of track types accepted as mux sources
    _acceptedTrackTypes: list[info.MediaTrackType] = [
        info.MediaTrackType.Video,
        info.MediaTrackType.Audio,
        info.MediaTrackType.Subtitles,
    ]

    def __init__(self, container: info.MediaFile) -> None:
        self._container = container

        # Sanity check that this is an MKV container. No other formats are supported.
        assert container.meta.Format == "Matroska"

        # Setup instance vars
        self._tagOptions: dict[
            typing.Union[EditTagSelector, info.MediaTrack],
            typing.Optional[pathlib.Path],
        ] = {}
        self._chapterOption: typing.Optional[
            typing.Union[bool, pathlib.Path]
        ] = False
        self._containerOptions: EditContainerOptions = {}
        self._trackOptions: dict[info.MediaTrack, EditTrackOptions] = {}

    def _ensureTrackIsValid(self, track: info.MediaTrack):
        if track not in self._container.tracks:
            raise RuntimeError(
                "The given track is not found in the container you are trying to edit!\n",
                track,
            )
        if track.Type not in self._acceptedTrackTypes:
            raise RuntimeError(
                "The given track is not a valid type for editing!\n",
                track,
            )

    def setTags(
        self,
        selector: typing.Union[EditTagSelector, info.MediaTrack],
        path: typing.Optional[pathlib.Path],
    ) -> None:
        """
        Set tag options for the all tracks, the container, or a specific track.

        If value is `None` the tracks will be cleared for the selector.
        """
        if isinstance(selector, info.MediaTrack):
            self._ensureTrackIsValid(selector)
        self._tagOptions[selector] = path

    def _generateTagArguments(self) -> list[str, pathlib.Path]:
        arguments: list[str] = []
        for selector, value in self._tagOptions.items():
            selectorArg = ""
            if isinstance(selector, EditTagSelector):
                selectorArg = selector.value
            else:
                selectorArg = f"track:{selector.ID + 1}"
            valueArg = "" if value is None else value
            arguments += ["--tags", f"{selectorArg}:{valueArg}"]
        return arguments

    def setChapters(self, value: typing.Optional[pathlib.Path]) -> None:
        """
        Set chapters on the container.

        A path (to an XML file) will update the container with the chapters within,
        a value of `None` will clear all chapters from the container.
        """
        self._chapterOption = value

    def _generateChapterArguments(self) -> list[str, pathlib.Path]:
        if self._chapterOption is False:
            return []
        return ["--chapters"] + (
            [] if self._chapterOption is None else [self._chapterOption]
        )

    def setContainerOptions(self, options: EditContainerOptions = {}):
        """Set container options for editing"""
        self._containerOptions = options

    def _formatPropertyEdit(
        self, key: str, value: typing.Optional[typing.Union[str, int, bool]]
    ) -> list[str]:
        if value is None:
            return ["--delete", key]
        elif isinstance(value, bool):
            return ["--set", f"flag-{key}={int(value)}"]
        elif isinstance(value, (str, int)):
            return ["--set", f"{key}={value}"]

    def _generateContainerArguments(self) -> list[str]:
        arguments: list[str] = (
            ["--edit", "info"] if self._containerOptions else []
        )
        for key, value in self._containerOptions.items():
            arguments += self._formatPropertyEdit(key, value)
        return arguments

    def setTrackOptions(
        self,
        track: info.MediaTrack,
        options: typing.Optional[EditTrackOptions] = None,
    ) -> None:
        if options is None:
            del self._trackOptions[track]
        else:
            self._trackOptions[track] = options

    def _generateTrackArguments(self) -> list[str, pathlib.Path]:
        arguments: list[str] = []
        for track, options in self._trackOptions.items():
            if options:
                arguments += ["--edit", f"track:{track.ID + 1}"]
            for key, value in options.items():
                arguments += self._formatPropertyEdit(key, value)
        return arguments

    def _generateCommandArguments(self) -> list[str, pathlib.Path]:
        return [
            self._container.path,
            *self._generateTagArguments(),
            *self._generateChapterArguments(),
            *self._generateContainerArguments(),
            *self._generateTrackArguments(),
        ]

    def run(self, fg: bool = True) -> sh.RunningCommand:
        """Execute the header edit operation now."""
        return mkvpropedit(self._generateCommandArguments(), _fg=fg)
