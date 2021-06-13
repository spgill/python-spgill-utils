# stdlib imports
import types

# vendor imports

# local imports


class FrozenNamespace(types.SimpleNamespace):
    """A SimpleNamespace that can be frozen after being hydrated."""

    def __init__(self, *args, _frozen=False, **kwargs):
        """
        Initialize a new FrozenNamespace instance.

        All extra args and kwargs are passed through to the underlying
        `types.SimpleNamespace`.

        Args:
            frozen (boolean, optional): Whether or not the namespace is frozen
                after class initialization. Defaults to False.
        """
        super().__init__(*args, **kwargs)
        self._frozen = _frozen

    def __setattr__(self, *args):
        if hasattr(self, "_frozen") and self._frozen:
            raise RuntimeError("This namespace is frozen")
        super().__setattr__(*args)

    def __delattr__(self, *args):
        if hasattr(self, "_frozen") and self._frozen:
            raise RuntimeError("This namespace is frozen")
        super().__delattr__(*args)

    def _freeze(self):
        """
        Freeze the namespace to prevent further mutations.

        If the namespace is already frozen, raises a RuntimeError.

        Returns:
            Returns self, to allow this to be chained directly with class
            instantiation. E.g., `FrozenNamespace(a='b')._freeze()`
        """
        if self._frozen:
            raise RuntimeError("This namespace is ALREADY frozen")
        self._frozen = True
        return self
