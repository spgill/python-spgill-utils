### stdlib imports
from collections.abc import Iterable
import pathlib


def walk(
    top: pathlib.Path,
    /,
    topDown: bool = False,
    followLinks: bool = False,
    sort: bool = False,
    reverse: bool = False,
) -> Iterable[
    tuple[
        pathlib.Path,
        Iterable[pathlib.Path],
        Iterable[pathlib.Path],
    ]
]:
    """
    Traverse a directory structure, yielding files and directories along the way.

    Nearly identical in usage to standard library `os.walk`. Primary difference
    is that `pathlib.Path` instances are yielded instead of strings, as well as
    the addition of sorting-related arguments.

    `sort` argument will sort the the directories and files before yielding them.
    Word of warning, this does slightly change execution, as it has to resolve all
    generators to lists before yielding results. Could potentially slow down
    execution on VERY large file structures. Use `reverse` argument to reverse the
    sort order.

    Adapted from http://ominian.com/2016/03/29/os-walk-for-pathlib-path/
    """
    topIterator = top.iterdir()
    if sort:
        topIterator = sorted(topIterator, reverse=reverse)

    dirs = (node for node in topIterator if node.is_dir() is True)
    nondirs = (node for node in topIterator if node.is_dir() is False)

    if sort:
        dirs = sorted(dirs, reverse=reverse)
        nondirs = sorted(nondirs, reverse=reverse)

    if topDown:
        yield top, dirs, nondirs

    for name in dirs:
        if followLinks or name.is_symlink() is False:
            for x in walk(
                name,
                topDown=topDown,
                followLinks=followLinks,
                sort=sort,
                reverse=reverse,
            ):
                yield x

    if not topDown:
        yield top, dirs, nondirs
