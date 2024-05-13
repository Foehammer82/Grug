import importlib
import inspect
import pkgutil
from pathlib import Path


def get_assistant_functions() -> list[callable]:
    """Return a list of all assistant functions."""

    output: list[callable] = []

    # Import all assistant_functions from the submodules
    for importer, modname, ispkg in pkgutil.iter_modules([Path(__file__).parent]):
        module = importlib.import_module(f".{modname}", package="grug.assistant_functions")

        for obj in inspect.getmembers(module):
            if (inspect.isfunction(obj[1]) or inspect.iscoroutinefunction(obj[1])) and (
                obj[1].__module__ == module.__name__
            ):
                output.append(obj[1])

    return output
