### stdlib imports
import pathlib
import typing


def walk(
    top: pathlib.Path, topDown: bool = False, followLinks: bool = False
) -> typing.Generator[
    tuple[
        pathlib.Path,
        typing.Generator[pathlib.Path, None, None],
        typing.Generator[pathlib.Path, None, None],
    ],
    None,
    None,
]:
    """
    See Python docs for os.walk, exact same behavior but it yields Path() instances instead

    Adapted from http://ominian.com/2016/03/29/os-walk-for-pathlib-path/
    """
    names = list(top.iterdir())

    dirs = (node for node in names if node.is_dir() is True)
    nondirs = (node for node in names if node.is_dir() is False)

    if topDown:
        yield top, dirs, nondirs

    for name in dirs:
        if followLinks or name.is_symlink() is False:
            for x in walk(name, topDown, followLinks):
                yield x

    if topDown is not True:
        yield top, dirs, nondirs
