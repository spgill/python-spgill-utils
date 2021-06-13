# stdlib imports
import datetime
import logging
import os
import pathlib
import json
import random
import re
import secrets
import sys
import uuid as uuidModule

# local imports
from .types import FrozenNamespace

### CONSTANTS ###
# Dictionary of extra json encoder options
_jsonOptions = {"sort_keys": True, "indent": 2}

# Parent directory name for app data
PARENT_DIRECTORY_NAME = ".chassis"


class _PropKey:
    def __init__(self, store, key):
        self._store = store
        self._key = key

    @property
    def value(self):
        return self._store._getValue(self._key)

    @property
    def defaultValue(self):
        return self._store._getDefaultValue(self._key)

    def isDefault(self):
        return self._store._isDefaultValue(self._key)

    @property
    def overrideValue(self):
        return self._store._getOverrideValue(self._key)

    def isOverridden(self):
        return self._store._isOverriddenValue(self._key)

    def setOverride(self, value):
        return self._store._setOverrideValue(self._key, value)

    def removeOverride(self):
        return self._store._removeOverrideValue(self._key)


class _PropStore:
    def __init__(
        self,
        propsFile: pathlib.Path,
        defaultValues: dict,
        overrideValues: dict,
    ):
        # Store the args away for future use
        self._path = propsFile
        self._keys = defaultValues.keys()
        self._defaults = defaultValues
        self._overrides = overrideValues

        # If the props file does not exist, create an empty one
        if not propsFile.exists():
            with propsFile.open("w") as fileHandle:
                json.dump({}, fileHandle)

        # Load up the props file and parse it
        with propsFile.open("r") as fileHandle:
            self._store = json.load(fileHandle)

    def __getattr__(self, key):
        # normal = self._normalize(key)
        if key in self._keys:
            return self.__getitem__(key)
        return super().__getattribute__(key)

    def __getitem__(self, key):
        # normal = self._normalize(key)
        if key in self._keys:
            return _PropKey(self, key)
        raise KeyError(f'Key "{key}" does not exist in the store')

    def __iter__(self):
        return self._keys.__iter__()

    def _getValue(self, key):
        if key in self._overrides:
            return self._overrides[key]

        return self._store.get(key, self._defaults[key])

    def _getDefaultValue(self, key):
        return self._defaults[key]

    def _getOverrideValue(self, key):
        return self._overrides[key]

    def _setOverrideValue(self, key, value):
        self._overrides[key] = value

    def _removeOverrideValue(self, key):
        del self._overrides[key]

    def _isDefaultValue(self, key):
        return (
            key not in self._store or self._store[key] == self._defaults[key]
        )

    def _isOverriddenValue(self, key):
        return key in self._overrides


class Chassis:
    """
    Create mixin/wrapper class for application resource management.

    All arguments are keyword arguments.

    Any class inheriting the returned class will share the same configuration
    data, path, etc. If you want the subclasses to have their own data, you
    must make a separate call to `createConfiguration` for each.

    Args:
        root (str, pathlib.Path, optional): Root directory for the application.
            Defaults to the location of the invoked script.
        uuid (str, uuid.UUID, optional): The UUID of the application. Can
            either be a string or an instance of `uuid.UUID`. Defaults to the
            contents of the `__uuid__` file in the directory specified in
            the `root` arg, or `None` if it does not exist.
        path (str, pathlib.Path, optional): Directory for storing application
            data in. Default is a subdirectory of
            `~/.chassis` named with the hex form of the
            value of the `uuid` arg. If neither are provided, a `RuntimeError`
            will be raised.
        propsFile (str, pathlib.Path, optional): Path to user configurable
            json file. If none is given, all values will be equal to their
            defined defaults. Can be override with the environment variable
            "CHASSIS_PROPS_FILE".
        features (dict): Dictionary of boolean flags to enable/disable
            optional features. Including (but not necessary limited to) the
            following options;
            `log`: Enable log files for every application session.
    """

    def __init__(
        self,
        root=None,
        uuid=None,
        path=None,
        propsFile=None,
        props={},
        overrides={},
        features={},
    ):
        # Determine and expand the root application path
        if not root:
            root = pathlib.Path(sys.argv[0])
            if root.is_file():
                root = root.parent
        root = pathlib.Path(root).expanduser().absolute()

        # If UUID is not given, try and open it from a file
        if uuid:
            uuid = uuidModule.UUID(uuid)
        else:
            try:
                with (root / "__uuid__").open("r") as uuidHandle:
                    uuid = uuidModule.UUID(uuidHandle.read().strip())
            except FileNotFoundError:
                pass

        # If path is not given, try and derive it from the UUID
        if envPath := os.environ.get("CHASSIS_PATH", None):
            path = pathlib.Path(envPath)
        elif path:
            path = pathlib.Path(path)
        elif uuid:
            path = pathlib.Path(f"~/{PARENT_DIRECTORY_NAME}/{uuid}")
        else:
            raise RuntimeError(
                "If no `path` is specified, then `uuid` must be specified "
                + "or a `__uuid__` file must be present in the root directory"
            )
        path = path.expanduser()
        path.mkdir(parents=True, exist_ok=True)  # Create the path

        # Resolve the path of the propsFile
        propsFile = (
            pathlib.Path(os.environ.get("CHASSIS_PROPS_FILE", propsFile))
            .expanduser()
            .absolute()
        )

        # Create the basic store configuration structure
        chassisStore = FrozenNamespace(
            **{
                # Configurable options
                "root": root,
                "uuid": uuid,
                "path": path,
                "propsFile": propsFile,
            }
        )

        # Open the props store
        chassisPropStore = _PropStore(
            propsFile=propsFile,
            defaultValues=props,
            overrideValues=overrides,
        )

        # Freeze the store, so it can't be modified later
        chassisStore._freeze()

        # Initialize the session information
        chassisSession = FrozenNamespace(
            **{
                "opened": datetime.datetime.utcnow(),
                "token": secrets.token_urlsafe(32),
                "key": secrets.token_bytes(32),
                "pin": "".join(random.choices("0123456789", k=4)),
            }
        )

        # Create the logger
        chassisSession.logPath = (
            chassisStore.path
            / "logs"
            / re.sub(r"\W", "", chassisSession.opened.isoformat())
        ).with_suffix(".log")
        if features.get("log", False):
            chassisSession.logPath.parent.mkdir(exist_ok=True)
            chassisSession.log = logging.basicConfig(
                filename=chassisSession.logPath
            )
        else:
            chassisSession.log = None

        # Freeze the session
        chassisSession._freeze()

        # Store the vars into the instance
        self.props = chassisPropStore
        self.store = chassisStore
        self.session = chassisSession


# Generate a uuid file on main
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uuid":
        path = pathlib.Path(sys.argv[2])
        if path.is_file():
            path = path.parent
        path = path / "__uuid__"
        with path.open("w") as uuidFile:
            uuidFile.write(str(uuidModule.uuid4()))
