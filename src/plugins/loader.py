"""
SAAB-SUITE — OEM plugin loader.

Discovers plugins/<oem>/manifest.json, validates required fields, and
dynamically imports plugins/<oem>/plugin.py -> an OEMPlugin subclass.

Entry point:  python3 -m src.plugins.loader --list
"""

from __future__ import annotations
import argparse
import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Type

from src.plugins.base import OEMPlugin

logger = logging.getLogger(__name__)

REQUIRED_MANIFEST_FIELDS = [
    "oem", "protocols", "pidfiles", "flashhandler",
    "calibrationcatalog", "extendedservices", "minyear", "maxyear",
]


@dataclass
class PluginManifest:
    oem: str
    protocols: List[str]
    pidfiles: List[str]
    flashhandler: str
    calibrationcatalog: str
    extendedservices: List[str]
    minyear: int
    maxyear: int
    path: Path

    @classmethod
    def from_json(cls, path: Path) -> "PluginManifest":
        data = json.loads(path.read_text())
        missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in data]
        if missing:
            raise ValueError(f"{path}: manifest missing required fields: {missing}")
        return cls(path=path, **{k: data[k] for k in REQUIRED_MANIFEST_FIELDS})


class PluginLoadError(Exception):
    pass


class PluginRegistry:
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.manifests: Dict[str, PluginManifest] = {}
        self._plugin_classes: Dict[str, Type[OEMPlugin]] = {}

    def discover(self) -> List[PluginManifest]:
        self.manifests.clear()
        if not self.plugins_dir.exists():
            return []
        for manifest_path in sorted(self.plugins_dir.glob("*/manifest.json")):
            try:
                manifest = PluginManifest.from_json(manifest_path)
                self.manifests[manifest.oem] = manifest
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"[plugins] Skipping invalid manifest {manifest_path}: {e}")
        return list(self.manifests.values())

    def load(self, oem: str) -> Type[OEMPlugin]:
        if oem in self._plugin_classes:
            return self._plugin_classes[oem]
        if oem not in self.manifests:
            self.discover()
        if oem not in self.manifests:
            raise PluginLoadError(f"No manifest found for OEM '{oem}'")

        manifest = self.manifests[oem]
        plugin_py = manifest.path.parent / "plugin.py"
        if not plugin_py.exists():
            raise PluginLoadError(f"{plugin_py} does not exist (declared by {manifest.path})")

        spec = importlib.util.spec_from_file_location(f"saabsuite_plugin_{oem}", plugin_py)
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Could not load spec for {plugin_py}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        plugin_cls = getattr(module, "Plugin", None)
        if plugin_cls is None or not issubclass(plugin_cls, OEMPlugin):
            raise PluginLoadError(f"{plugin_py} must define a class `Plugin(OEMPlugin)`")

        self._plugin_classes[oem] = plugin_cls
        logger.info(f"[plugins] Loaded {oem} -> {plugin_cls.__name__}")
        return plugin_cls

    def instantiate(self, oem: str) -> OEMPlugin:
        return self.load(oem)()

    def supports_vehicle(self, oem: str, year: int) -> bool:
        manifest = self.manifests.get(oem)
        if not manifest:
            return False
        return manifest.minyear <= year <= manifest.maxyear


def run(args: argparse.Namespace) -> None:
    registry = PluginRegistry(args.plugins_dir)
    manifests = registry.discover()
    if args.list:
        for m in manifests:
            print(f"  {m.oem:10s} protocols={m.protocols} years={m.minyear}-{m.maxyear}")
    if args.load:
        cls = registry.load(args.load)
        print(f"[*] Loaded plugin class: {cls.__module__}.{cls.__name__}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OEM plugin loader")
    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--load", default=None, help="OEM name to load, e.g. gm")
    run(parser.parse_args())
