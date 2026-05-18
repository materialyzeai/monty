"""Developer-facing utilities, e.g. decorators for deprecating methods or classes."""

from __future__ import annotations

import functools
import inspect
import sys
import warnings
from dataclasses import is_dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def deprecated(
    replacement: Callable | str | None = None,
    message: str = "",
    deadline: tuple[int, int, int] | None = None,
    category: type[Warning] = FutureWarning,
) -> Callable:
    """Decorator to mark classes or functions as deprecated, with a possible replacement.

    Args:
        replacement (Callable | str): A replacement class or function.
        message (str): A warning message to be displayed.
        deadline (Optional[tuple[int, int, int]]): Optional deadline for removal
            of the old function/class, in format (yyyy, MM, dd). A CI warning would
            be raised after this date if is running in code owner' repo.
        category (Warning): Choose the category of the warning to issue. Defaults
            to FutureWarning. Another choice can be DeprecationWarning. Note that
            FutureWarning is meant for end users and is always shown unless silenced.
            DeprecationWarning is meant for developers and is never shown unless
            python is run in developmental mode or the filter is changed. Make
            the choice accordingly.

    Returns:
        Original function/class, but with a warning to use the replacement.

    """

    def craft_message(
        old: Callable | type,
        replacement: Callable | str | None,
        message: str,
        deadline: datetime | None,
    ) -> str:
        msg = f"{old.__name__} is deprecated"

        if deadline is not None:
            msg += f", and will be removed on {_deadline:%Y-%m-%d}\n"

        if replacement is not None:
            if deadline is None:
                msg += "; use "  # for better formatting
            else:
                msg += "Use "

            if isinstance(replacement, str):
                msg += f"{replacement} instead."

            else:
                if isinstance(replacement, property):
                    r = replacement.fget
                elif isinstance(replacement, (classmethod, staticmethod)):
                    r = replacement.__func__
                else:
                    r = replacement

                msg += f"{r.__name__} in {r.__module__} instead."

        if message:
            msg += "\n" + message
        return msg

    def deprecated_function_decorator(old: Callable) -> Callable:
        # Craft the warning message once at decoration time; the inputs are
        # all closed over and immutable, so there is no need to rebuild the
        # string on every call (this used to dominate hot deprecated paths).
        msg = craft_message(old, replacement, message, _deadline)

        @functools.wraps(old)
        def wrapped(*args, **kwargs):
            warnings.warn(msg, category=category, stacklevel=2)
            return old(*args, **kwargs)

        return wrapped

    def deprecated_class_decorator(cls: type) -> type:
        # Modify __post_init__ for dataclass
        if is_dataclass(cls) and hasattr(cls, "__post_init__"):
            original_init = cls.__post_init__
        else:
            original_init = cls.__init__  # type: ignore[misc]

        msg = craft_message(cls, replacement, message, _deadline)

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            warnings.warn(msg, category=category, stacklevel=2)
            original_init(self, *args, **kwargs)

        if is_dataclass(cls) and hasattr(cls, "__post_init__"):
            cls.__post_init__ = new_init
        else:
            cls.__init__ = new_init  # type: ignore[misc]

        return cls

    # Convert deadline to `datetime` type
    _deadline: datetime | None = datetime(*deadline) if deadline is not None else None

    def decorator(target: Callable) -> Callable:
        if inspect.isfunction(target):
            return deprecated_function_decorator(target)
        if inspect.isclass(target):
            return deprecated_class_decorator(target)
        raise TypeError(
            "The @deprecated decorator can only be applied to classes or functions"
        )

    return decorator


class requires:
    """Decorator to mark classes or functions as requiring a specified condition.

    This can be used to present useful error messages for optional
    dependencies. For example, decorating the following code will check if
    scipy is present and if not, a runtime error will be raised if someone
    attempts to call the use_scipy function:

        try:
            import scipy
        except ImportError:
            scipy = None

        @requires(scipy is not None, "scipy is not present.")
        def use_scipy():
            print(scipy.majver)

    Args:
        condition: Condition necessary to use the class or function.
        message: A message to be displayed if the condition is not True.

    """

    def __init__(
        self, condition: bool, message: str, err_cls: type[Exception] = RuntimeError
    ) -> None:
        """Initialize the requires decorator.

        Args:
            condition: An expression returning a bool.
            message: Message to display if condition is False.
            err_cls: Exception class to raise when condition is False.

        """
        self.condition = condition
        self.message = message
        self.err_cls = err_cls

    def __call__(self, _callable: Callable) -> Callable:
        """Wrap ``_callable`` so it raises when the condition is False.

        Args:
            _callable: Callable function.

        """

        @functools.wraps(_callable)
        def decorated(*args, **kwargs):
            if not self.condition:
                raise self.err_cls(self.message)
            return _callable(*args, **kwargs)

        return decorated


def install_excepthook(hook_type: str = "color", **kwargs) -> int:
    """Replace the default Python traceback with an improved version from IPython.

    Use ``color`` for colourful traceback formatting or ``verbose`` for the
    Ka-Ping Yee ``cgitb.py`` style. ``kwargs`` are forwarded to the hook
    constructor; see ``IPython.core.ultratb`` for details.

    Returns:
        0 if hook is installed successfully.

    """
    try:
        from IPython.core import ultratb  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise ImportError("Cannot install excepthook, IPython not installed") from exc

    # Select the hook.
    hook = {
        "color": ultratb.ColorTB,
        "verbose": ultratb.VerboseTB,
    }.get(hook_type.lower())

    if hook is None:
        return 2

    sys.excepthook = hook(**kwargs)
    return 0
