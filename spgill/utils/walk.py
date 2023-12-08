### stdlib imports
from collections.abc import Iterable
import pathlib
import typing


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
    topIterator = list(top.iterdir())
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


def find_files_by_suffix(
    sources: list[pathlib.Path],
    /,
    suffixes: typing.Optional[list[str]] = None,
    recurse: bool = True,
    sort: bool = False,
    prevent_duplicates: bool = True,
) -> typing.Generator[pathlib.Path, None, None]:
    """
    Given one or more source files and source directories, traverse directories
    and yield files that match the specified file suffix. If no suffixes are
    provided, _all_ files will be yielded.

    Args:
        sources: List of path objects to traverse. Can also directly include
            files, and they will be considered for return.
        suffixes: List of suffixes to accept from discovered files. If value is
            None or an empty list (or in general falsey), then all discovered
            files will be returned.
        recurse: If True, directories in `sources` will be recursed in their
            entirety to discover files. If False, directories will only have
            their immediate contents considered.
        sort: If True, will yield the discovered files in sorted alphabetical
            order. Unfortunately this comes at the cost of efficiency, as all
            files paths will need to be discovered and collected _before_ this
            function can yield any results.
        prevent_duplicates: If True, all discovered files will be screened
            for uniqueness and every unique file should only be yielded a single
            time by the generator, even with overlapping directory trees.
            Warning, this may cause issues with complex symlinks and may result
            in increased memory usage for directory trees with large numbers of
            files.
    """
    # If sorting is requested, yield from self via a sorted function
    if sort:
        yield from sorted(
            find_files_by_suffix(sources, suffixes=suffixes, sort=False)
        )
        return

    # If no suffixes were given, we default to yielding all files
    all_files = not suffixes

    # Track a set of the yielded files so we don't yield duplicates
    yielded_files: set[pathlib.Path] = set()

    for source in sources:
        # If the source is a file itself, we can consider it for yielding
        if source.is_file():
            if all_files or source.suffix in suffixes:
                if prevent_duplicates:
                    resolved_source = source.resolve()
                    if resolved_source not in yielded_files:
                        yielded_files.add(resolved_source)
                        yield source
                else:
                    yield source

        # Else if recursion is requested, we're going to walk the directory tree
        # for files
        elif recurse:
            for *_, sub_files in walk(source):
                for file in sub_files:
                    if all_files or file.suffix in suffixes:
                        if prevent_duplicates:
                            resolved_file = file.resolve()
                            if resolved_file not in yielded_files:
                                yielded_files.add(resolved_file)
                                yield file
                        else:
                            yield file

        # Else, we'll simply iterate through the directory's contents
        else:
            for path in source.iterdir():
                if path.is_file() and (all_files or path.suffix in suffixes):
                    if prevent_duplicates:
                        resolved_path = path.resolve()
                        if resolved_path not in yielded_files:
                            yielded_files.add(resolved_path)
                            yield path
                    else:
                        yield path
