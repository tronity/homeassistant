import asyncio
import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


CONFIG_FLOW_FILE = Path(__file__).resolve().parents[1] / "config_flow.py"
CONST_FILE = Path(__file__).resolve().parents[1] / "const.py"
ROOT_DIR = CONFIG_FLOW_FILE.parent


class FakeSchema:
    def __init__(self, spec):
        self.spec = spec

    def __call__(self, value):
        return value


def _required(key, default=None):
    return key


def _optional(key, default=None):
    return key


class FakeConfigFlowBase:
    def __init_subclass__(cls, **kwargs):
        return super().__init_subclass__()

    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def add_suggested_values_to_schema(self, schema, suggested_values):
        return schema


class FakeOptionsFlowBase:
    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}


@dataclass
class FakeConfigEntry:
    data: dict
    entry_id: str
    title: str = "Tronity Vehicle"


class FakeConfigEntriesManager:
    def __init__(self, entry):
        self._entry = entry
        self.updated_entry = None
        self.updated_title = None
        self.updated_data = None
        self.reloaded_entry_id = None

    def async_get_entry(self, entry_id):
        if self._entry.entry_id == entry_id:
            return self._entry
        return None

    def async_update_entry(self, entry, title=None, data=None):
        self.updated_entry = entry
        self.updated_title = title
        self.updated_data = data

    async def async_reload(self, entry_id):
        self.reloaded_entry_id = entry_id


class FakeHass:
    def __init__(self, config_entries):
        self.config_entries = config_entries


def _install_stubs() -> None:
    voluptuous_module = types.ModuleType("voluptuous")
    voluptuous_module.Required = _required
    voluptuous_module.Optional = _optional
    voluptuous_module.Schema = FakeSchema
    sys.modules["voluptuous"] = voluptuous_module

    aiohttp_module = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    aiohttp_module.ClientError = ClientError
    sys.modules["aiohttp"] = aiohttp_module

    homeassistant_module = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = homeassistant_module

    config_entries_module = types.ModuleType("homeassistant.config_entries")
    config_entries_module.ConfigFlow = FakeConfigFlowBase
    config_entries_module.OptionsFlow = FakeOptionsFlowBase
    config_entries_module.ConfigEntry = FakeConfigEntry
    sys.modules["homeassistant.config_entries"] = config_entries_module
    homeassistant_module.config_entries = config_entries_module

    core_module = types.ModuleType("homeassistant.core")
    core_module.HomeAssistant = FakeHass
    sys.modules["homeassistant.core"] = core_module

    data_entry_flow_module = types.ModuleType("homeassistant.data_entry_flow")
    data_entry_flow_module.FlowResult = dict
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow_module

    exceptions_module = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    exceptions_module.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant.exceptions"] = exceptions_module

    helpers_module = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers_module

    aiohttp_client_module = types.ModuleType("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(_hass):
        raise RuntimeError("Should not be called in reauth tests")

    aiohttp_client_module.async_get_clientsession = async_get_clientsession
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client_module


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_config_flow_module():
    package = types.ModuleType("tronity")
    package.__path__ = [str(ROOT_DIR)]
    sys.modules["tronity"] = package

    _load_module("tronity.const", CONST_FILE)
    return _load_module("tronity.config_flow", CONFIG_FLOW_FILE)


class TestConfigFlowReauth(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _install_stubs()
        cls.module = _load_config_flow_module()

    def test_reauth_success_updates_entry_and_reloads(self) -> None:
        entry = FakeConfigEntry(
            data={
                self.module.CONF_CLIENT_ID: "old_id",
                self.module.CONF_CLIENT_SECRET: "old_secret",
                self.module.CONF_VEHICLE_ID: "vehicle-1",
            },
            entry_id="entry-1",
            title="Old title",
        )
        manager = FakeConfigEntriesManager(entry)
        flow = self.module.ConfigFlow()
        flow.hass = FakeHass(manager)
        flow.context = {"entry_id": entry.entry_id}

        async def fake_validate_input(_hass, data):
            self.assertEqual(data[self.module.CONF_CLIENT_ID], "new_id")
            self.assertEqual(data[self.module.CONF_CLIENT_SECRET], "new_secret")
            return {"title": "New title"}

        self.module.validate_input = fake_validate_input

        first = asyncio.run(flow.async_step_reauth({}))
        self.assertEqual(first["type"], "form")
        self.assertEqual(first["step_id"], "reauth_confirm")

        result = asyncio.run(
            flow.async_step_reauth_confirm(
                {
                    self.module.CONF_CLIENT_ID: "new_id",
                    self.module.CONF_CLIENT_SECRET: "new_secret",
                }
            )
        )

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "reauth_successful")
        self.assertIs(manager.updated_entry, entry)
        self.assertEqual(manager.updated_title, "New title")
        self.assertEqual(manager.updated_data[self.module.CONF_CLIENT_ID], "new_id")
        self.assertEqual(
            manager.updated_data[self.module.CONF_CLIENT_SECRET], "new_secret"
        )
        self.assertEqual(manager.reloaded_entry_id, entry.entry_id)

    def test_reauth_invalid_auth_returns_error_form(self) -> None:
        entry = FakeConfigEntry(
            data={
                self.module.CONF_CLIENT_ID: "old_id",
                self.module.CONF_CLIENT_SECRET: "old_secret",
                self.module.CONF_VEHICLE_ID: "vehicle-1",
            },
            entry_id="entry-1",
            title="Old title",
        )
        manager = FakeConfigEntriesManager(entry)
        flow = self.module.ConfigFlow()
        flow.hass = FakeHass(manager)
        flow.context = {"entry_id": entry.entry_id}

        async def fake_validate_input(_hass, _data):
            raise self.module.InvalidAuth

        self.module.validate_input = fake_validate_input

        asyncio.run(flow.async_step_reauth({}))

        result = asyncio.run(
            flow.async_step_reauth_confirm(
                {
                    self.module.CONF_CLIENT_ID: "wrong_id",
                    self.module.CONF_CLIENT_SECRET: "wrong_secret",
                }
            )
        )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "reauth_confirm")
        self.assertEqual(result["errors"].get("base"), "invalid_auth")
        self.assertIsNone(manager.updated_entry)
        self.assertIsNone(manager.reloaded_entry_id)


if __name__ == "__main__":
    unittest.main()
