import importlib.util
import asyncio
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


INIT_FILE = Path(__file__).resolve().parents[1] / "__init__.py"
ROOT_DIR = INIT_FILE.parent


class FakeResponse:
    def __init__(self, status: int, payload: Optional[dict] = None) -> None:
        self.status = status
        self._payload = payload or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, post_responses=None, get_responses=None) -> None:
        self._post_responses = list(post_responses or [])
        self._get_responses = list(get_responses or [])

    def post(self, *args, **kwargs):
        return self._post_responses.pop(0)

    def get(self, *args, **kwargs):
        return self._get_responses.pop(0)


class FakeConfigEntriesManager:
    async def async_forward_entry_setups(self, entry, platforms):
        return None

    async def async_unload_platforms(self, entry, platforms):
        return True


class FakeHass:
    def __init__(self, sessions) -> None:
        self.data = {}
        self._sessions = list(sessions)
        self.config_entries = FakeConfigEntriesManager()


@dataclass
class FakeConfigEntry:
    data: dict
    entry_id: str
    title: str = "Tronity Vehicle"


class FakeTTLCache(dict):
    def __init__(self, maxsize: int, ttl: int) -> None:
        super().__init__()
        self.maxsize = maxsize
        self.ttl = ttl


def _install_stubs() -> None:
    if not hasattr(asyncio, "timeout"):
        class _NoopAsyncTimeout:
            async def __aenter__(self):
                return None

            async def __aexit__(self, exc_type, exc, tb):
                return False

        def _timeout(_seconds):
            return _NoopAsyncTimeout()

        asyncio.timeout = _timeout

    cachetools_module = types.ModuleType("cachetools")
    cachetools_module.TTLCache = FakeTTLCache
    sys.modules["cachetools"] = cachetools_module

    aiohttp_module = types.ModuleType("aiohttp")
    class ClientError(Exception):
        pass

    aiohttp_module.ClientError = ClientError
    sys.modules["aiohttp"] = aiohttp_module

    homeassistant_module = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = homeassistant_module

    exceptions_module = types.ModuleType("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        pass

    exceptions_module.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    sys.modules["homeassistant.exceptions"] = exceptions_module

    core_module = types.ModuleType("homeassistant.core")
    core_module.HomeAssistant = FakeHass
    sys.modules["homeassistant.core"] = core_module

    config_entries_module = types.ModuleType("homeassistant.config_entries")
    config_entries_module.ConfigEntry = FakeConfigEntry
    sys.modules["homeassistant.config_entries"] = config_entries_module

    const_module = types.ModuleType("homeassistant.const")

    class Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        DEVICE_TRACKER = "device_tracker"

    const_module.Platform = Platform
    sys.modules["homeassistant.const"] = const_module

    helpers_module = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers_module

    aiohttp_client_module = types.ModuleType("homeassistant.helpers.aiohttp_client")

    def async_create_clientsession(hass):
        return hass._sessions.pop(0)

    aiohttp_client_module.async_create_clientsession = async_create_clientsession
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client_module

    update_coordinator_module = types.ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    class DataUpdateCoordinator:
        def __init__(
            self,
            hass,
            logger,
            name,
            update_method,
            update_interval,
        ):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_method = update_method
            self.update_interval = update_interval
            self.data = None

        async def async_config_entry_first_refresh(self):
            self.data = await self.update_method()

    update_coordinator_module.UpdateFailed = UpdateFailed
    update_coordinator_module.CoordinatorEntity = CoordinatorEntity
    update_coordinator_module.DataUpdateCoordinator = DataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator_module

    device_registry_module = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    device_registry_module.DeviceInfo = DeviceInfo
    sys.modules["homeassistant.helpers.device_registry"] = device_registry_module


def _load_integration_module():
    spec = importlib.util.spec_from_file_location(
        "tronity",
        INIT_FILE,
        submodule_search_locations=[str(ROOT_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["tronity"] = module
    spec.loader.exec_module(module)
    return module


class TestAuthRetryContract(unittest.TestCase):
    """Behavior tests for critical auth/retry behavior in runtime update flow."""

    @classmethod
    def setUpClass(cls) -> None:
        _install_stubs()
        cls.integration = _load_integration_module()

    def setUp(self) -> None:
        self.integration.token_cache.clear()

    def test_token_request_401_403_raises_config_entry_auth_failed(self) -> None:
        """Auth endpoint 401/403 must be treated as credential failure."""
        entry = FakeConfigEntry(
            data={
                self.integration.CONF_CLIENT_ID: "id",
                self.integration.CONF_CLIENT_SECRET: "secret",
                self.integration.CONF_VEHICLE_ID: "vehicle-1",
            },
            entry_id="entry-1",
        )
        hass = FakeHass(
            sessions=[
                FakeSession(post_responses=[FakeResponse(401)]),
            ]
        )

        with self.assertRaises(self.integration.ConfigEntryAuthFailed):
            asyncio.run(self.integration.async_setup_entry(hass, entry))

    def test_retry_flow_invalidates_token_before_refresh(self) -> None:
        """On auth failure during fetch, refresh token and retry successfully."""
        entry = FakeConfigEntry(
            data={
                self.integration.CONF_CLIENT_ID: "id",
                self.integration.CONF_CLIENT_SECRET: "secret",
                self.integration.CONF_VEHICLE_ID: "vehicle-1",
            },
            entry_id="entry-1",
        )
        payload = {"charging": False, "plugged": False}
        hass = FakeHass(
            sessions=[
                FakeSession(post_responses=[FakeResponse(200, {"access_token": "token-1"})]),
                FakeSession(get_responses=[FakeResponse(401)]),
                FakeSession(post_responses=[FakeResponse(200, {"access_token": "token-2"})]),
                FakeSession(get_responses=[FakeResponse(200, payload)]),
            ]
        )

        result = asyncio.run(self.integration.async_setup_entry(hass, entry))
        self.assertTrue(result)
        coordinator = hass.data[self.integration.DOMAIN][entry.entry_id][
            self.integration.CONF_DATA_COORDINATOR
        ]
        self.assertEqual(coordinator.data, payload)

    def test_second_auth_failure_escalates_to_config_entry_auth_failed(self) -> None:
        """If retry still fails auth, integration must escalate to re-auth state."""
        entry = FakeConfigEntry(
            data={
                self.integration.CONF_CLIENT_ID: "id",
                self.integration.CONF_CLIENT_SECRET: "secret",
                self.integration.CONF_VEHICLE_ID: "vehicle-1",
            },
            entry_id="entry-1",
        )
        hass = FakeHass(
            sessions=[
                FakeSession(post_responses=[FakeResponse(200, {"access_token": "token-1"})]),
                FakeSession(get_responses=[FakeResponse(401)]),
                FakeSession(post_responses=[FakeResponse(200, {"access_token": "token-2"})]),
                FakeSession(get_responses=[FakeResponse(401)]),
            ]
        )

        with self.assertRaises(self.integration.ConfigEntryAuthFailed):
            asyncio.run(self.integration.async_setup_entry(hass, entry))


if __name__ == "__main__":
    unittest.main()
