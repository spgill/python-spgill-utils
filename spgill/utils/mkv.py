# Standard Library imports
import enum
import json
import mimetypes
import pathlib
import subprocess
import sys
from pathlib import Path


exports = sys.modules[__name__]
exports._mkvtoolnix = None
exports._ffmpeg = None


def set_path(mkvpath, ffpath):
    """Set the path for the mkvtoolnix suite."""
    exports._mkvtoolnix = Path(mkvpath)
    exports._ffmpeg = Path(ffpath)


def _dedupe(d, key):
    i = 2
    newkey = key
    while newkey in d:
        newkey = key + " " + str(i)
        i += 1
    return newkey


def _wrap(s):
    # return '"' + str(s) + '"'
    return s


class TrackType(enum.Enum):
    VIDEO = V = "video"
    AUDIO = A = "audio"
    SUBTITLE = S = "subtitle"
    DATA = D = "data"


class ContainerFile(object):
    def __init__(self, path):
        """An object representing a container file with one to many streams."""
        # Normalize the path to a pathlib object
        if isinstance(path, (str, bytes)):
            self.path = pathlib.Path(path)
        else:
            self.path = path

        # Get the stream info for the file
        self._parse_file()

    def _parse_file(self):
        """Call ffprobe to get this container's streams."""
        if not exports._mkvtoolnix:
            raise RuntimeError("You must specify the location of mkvtoolnix")

        # Call mkvmerge -I to get all the track info
        self.info = info = json.loads(
            subprocess.run(
                args=[
                    exports._ffmpeg / "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_streams",
                    self.path,
                ],
                capture_output=True,
            ).stdout
        )

        # Iterate through the lines and generate tracks
        self.tracks = []
        for stream in info["streams"]:
            # Create a new track object using the info
            tags = stream.get("tags", {})
            track = ContainerTrack(
                parent=self,
                index=stream["index"],
                type=TrackType(stream["codec_type"]),
                codec=stream["codec_name"],
                name=tags.get("title", tags.get("TITLE", "")),
                language=tags.get("language", tags.get("LANGUAGE", "und")),
                default=bool(stream["disposition"]["default"]),
                forced=bool(stream["disposition"]["forced"]),
            )
            track.raw = stream
            self.tracks.append(track)

    def updateTrackHeaders(self):
        if self.path.suffix != ".mkv":
            raise RuntimeError(
                f'File path "{self.path.name}" is not an mkv container'
            )

        args = [exports._mkvtoolnix / "mkvpropedit", self.path]

        for track in self.tracks:
            args += [
                "--edit",
                f"track:{track.index + 1}",
            ]

            if track.name:
                args += [
                    "--set",
                    f"name={track.name}",
                ]
            else:
                args += [
                    "--delete",
                    "name",
                ]

        print(args)
        subprocess.run(args)


class ContainerTrack(object):
    """An object representing a single track of a container."""

    def __init__(self, parent, index, type, codec, name, language, **kwargs):
        # Unpack all the required attributes
        self.parent = parent
        self.index = index
        self.type = type
        self.codec = codec
        self.name = name
        self.language = language

        # Unpack optional attributes from kwargs
        self.default = kwargs.get("default", None)
        self.forced = kwargs.get("forced", None)

        # Unpack any extra kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        """Generate a quick string representation"""
        return (
            "mkv.ContainerTrack(parent={0}, index={1}, type={2}, "
            + "codec={3}, name={4}, language={5}, default={6}, forced={7})"
        ).format(
            repr(str(self.parent.path)),
            repr(self.index),
            repr(self.type),
            repr(self.codec),
            repr(self.name),
            repr(self.language),
            repr(self.default),
            repr(self.forced),
        )

    def extract(self, output_path):
        """Extract this track to its own file."""
        output_path = pathlib.Path(output_path)

        args = [
            str(exports._mkvtoolnix / "mkvextract"),
            "tracks",
            _wrap(self.parent.path),
            "{0}:{1}".format(self.index, _wrap(output_path)),
        ]

        print("CMD", " ".join(args))

        subprocess.run(" ".join(args))


class ForeignTrack(object):
    """An object representing a single track outside of a stream container."""

    def __init__(self, path, type=None, name="", language="und", **kwargs):
        # Unpack all the required attributes
        self.path = pathlib.Path(path)
        self.index = 0
        self.type = type
        self.name = name
        self.language = language

        # Try and guess the type if none given
        if self.type is None:
            if self.path.name.endswith(".srt"):
                self.type = "subtitles"
            else:
                guess = mimetypes.guess_type(self.path.name)
                if guess[0]:
                    self.type = guess[0].split("/")[0]
                else:
                    raise RuntimeError("Unknown filetype " + self.path.name)

        # Unpack optional attributes from kwargs
        self.default = kwargs.get("default", None)
        self.forced = kwargs.get("forced", None)

        # Unpack any extra kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        """Generate a quick string representation"""
        return (
            "mkv.ForeignTrack(path={0}, type={1}, "
            + "name={2}, language={3}, default={4}, forced={5})"
        ).format(
            repr(str(self.path)),
            repr(self.type),
            repr(self.name),
            repr(self.language),
            repr(self.default),
            repr(self.forced),
        )


class MultiplexJob(object):
    """An object representing a single muxing job."""

    def __init__(self, path, tracks, title=""):
        self.path = pathlib.Path(path)
        self.tracks = tracks
        self.title = title

    def command(self, ionice):
        """Generate the command for mkvmerge."""
        args = [
            str(exports._mkvtoolnix / "mkvmerge"),
            "--title",
            _wrap(self.title),
            "-o",
            _wrap(self.path),
        ]

        if ionice:
            args = ["ionice", "-c3"] + args

        flag = {
            TrackType.VIDEO: "-d",
            TrackType.AUDIO: "-a",
            TrackType.SUBTITLE: "-s",
        }

        tracksBySource = dict()
        for track in self.tracks:
            if isinstance(track, ContainerTrack):
                source = track.parent
            else:
                source = track.path

            if source not in tracksBySource:
                tracksBySource[source] = []

            tracksBySource[source].append(track)

        for source in tracksBySource:

            streamsByType = {TrackType.V: [], TrackType.A: [], TrackType.S: []}
            for stream in tracksBySource[source]:
                streamsByType[stream.type].append(stream)

            for streamType, streams in streamsByType.items():
                if len(streams) == 0:
                    args.append(flag[streamType].upper())
                    continue

                args.append(flag[streamType])
                args.append(
                    ",".join([str(stream.index) for stream in streams])
                )

                for stream in streams:
                    args.append("--track-name")
                    args.append("{0}:{1}".format(stream.index, stream.name))
                    args.append("--language")
                    args.append(
                        "{0}:{1}".format(
                            stream.index, stream.language or "und"
                        )
                    )

                    if stream.default:
                        args.append("--default-track")
                        args.append(
                            "{0}:{1}".format(
                                stream.index, str(stream.default).lower()
                            )
                        )

                    if stream.forced:
                        args.append("--forced-track")
                        args.append(
                            "{0}:{1}".format(
                                stream.index, str(stream.forced).lower()
                            )
                        )

                    if hasattr(track, "sync"):
                        args.append("--sync")
                        args.append(
                            "{0}:{1}".format(stream.index, stream.sync)
                        )

            if isinstance(source, ContainerFile):
                args.append(_wrap(source.path))
            else:
                args.append(_wrap(source))

        return args

    def run(self, ionice=False, *args, **kwargs):
        subprocess.run(self.command(ionice), *args, **kwargs)
        return ContainerFile(self.path)
