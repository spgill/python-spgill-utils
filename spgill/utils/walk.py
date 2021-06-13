def walk(top, topdown=False, followlinks=False):
    """
    See Python docs for os.walk, exact same behavior but it yields Path() instances instead

    Adapted from http://ominian.com/2016/03/29/os-walk-for-pathlib-path/
    """
    names = list(top.iterdir())

    dirs = (node for node in names if node.is_dir() is True)
    nondirs = (node for node in names if node.is_dir() is False)

    if topdown:
        yield top, dirs, nondirs

    for name in dirs:
        if followlinks or name.is_symlink() is False:
            for x in walk(name, topdown, followlinks):
                yield x

    if topdown is not True:
        yield top, dirs, nondirs
