import importlib
import pkgutil
from pathlib import Path

from fastapi import APIRouter

routers: list[APIRouter] = []

# Import all routers from the submodules
for importer, modname, ispkg in pkgutil.iter_modules([Path(__file__).parent]):
    module = importlib.import_module(f".{modname}", package="grug.api_routers")
    for attribute in dir(module):
        if not attribute.startswith("__") and isinstance(getattr(module, attribute), APIRouter):
            routers.append(getattr(module, attribute))
