"""Tests for Home Memory."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import llm

from custom_components.home_memory.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_lifecycle(hass: HomeAssistant) -> None:
    await _setup(hass)
    assert hass.states.get("sensor.home_memory").state == "0"

    resp = await hass.services.async_call(
        DOMAIN, "set",
        {"topic": "Pool", "content": "außer Betrieb", "refs": ["switch.pump"]},
        blocking=True, return_response=True,
    )
    await hass.async_block_till_done()
    assert resp == {"topic": "pool", "entity_id": "sensor.home_memory_pool"}
    state = hass.states.get("sensor.home_memory_pool")
    assert state.attributes["content"] == "außer Betrieb"
    assert state.attributes["refs"] == ["switch.pump"]
    assert hass.states.get("sensor.home_memory").state == "1"
    assert "pool" in hass.states.get("sensor.home_memory").attributes["topics"]

    await hass.services.async_call(
        DOMAIN, "append", {"topic": "pool", "text": "Licht über Schaltimpulse"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.home_memory_pool")
    assert state.attributes["content"] == "außer Betrieb\nLicht über Schaltimpulse"
    assert state.attributes["previous_content"] == "außer Betrieb"

    await hass.services.async_call(DOMAIN, "restore", {"topic": "pool"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_memory_pool").attributes["content"] == "außer Betrieb"

    await hass.services.async_call(DOMAIN, "delete", {"topic": "pool"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_memory_pool") is None
    assert er.async_get(hass).async_get("sensor.home_memory_pool") is None
    assert hass.states.get("sensor.home_memory").state == "0"


async def test_errors(hass: HomeAssistant) -> None:
    await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "delete", {"topic": "gibtsnicht"}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set", {"topic": "x", "content": "a" * 20000}, blocking=True
        )


async def test_persistence(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    await hass.services.async_call(
        DOMAIN, "set", {"topic": "energie", "content": "Kaskade"}, blocking=True
    )
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_memory_energie").attributes["content"] == "Kaskade"


async def test_llm_api(hass: HomeAssistant) -> None:
    await _setup(hass)
    context = llm.LLMContext(
        platform="test", context=None, language="de", assistant=None, device_id=None
    )
    api = await llm.async_get_api(hass, DOMAIN, context)
    names = {t.name for t in api.tools}
    assert names == {"home_memory_list", "home_memory_read", "home_memory_write", "home_memory_append"}

    await api.async_call_tool(
        llm.ToolInput(tool_name="home_memory_write", tool_args={"topic": "heizung", "content": "FBH EG/OG"})
    )
    await hass.async_block_till_done()
    result = await api.async_call_tool(
        llm.ToolInput(tool_name="home_memory_read", tool_args={"topic": "heizung"})
    )
    assert result["content"] == "FBH EG/OG"
    assert hass.states.get("sensor.home_memory_heizung") is not None
