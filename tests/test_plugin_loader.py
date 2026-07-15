from src.plugins.loader import PluginRegistry
from src.plugins.base import OEMPlugin, VehicleInfo


def test_discover_finds_gm_and_ford():
    registry = PluginRegistry("plugins")
    manifests = registry.discover()
    oems = {m.oem for m in manifests}
    assert "gm" in oems
    assert "ford" in oems


def test_load_gm_plugin_class():
    registry = PluginRegistry("plugins")
    registry.discover()
    cls = registry.load("gm")
    assert issubclass(cls, OEMPlugin)
    assert cls.oem == "gm"


def test_instantiate_and_initialize():
    registry = PluginRegistry("plugins")
    registry.discover()
    plugin = registry.instantiate("gm")
    plugin.initialize(VehicleInfo(vin="YS3FD45Y381234567", make="Saab", model="9-3", year=2008))
    assert plugin.vehicle.vin == "YS3FD45Y381234567"
    pids = plugin.get_extended_pids()
    assert len(pids) > 0


def test_supports_vehicle_year_range():
    registry = PluginRegistry("plugins")
    registry.discover()
    assert registry.supports_vehicle("gm", 2008) is True
    assert registry.supports_vehicle("gm", 1980) is False


def test_ford_flash_is_stubbed_not_implemented():
    registry = PluginRegistry("plugins")
    registry.discover()
    plugin = registry.instantiate("ford")
    import pytest
    with pytest.raises(NotImplementedError):
        plugin.execute_flash([])
