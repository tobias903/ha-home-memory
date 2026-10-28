"""Home Memory: persistent, topic-based knowledge about a home for AI assistants."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONTENT,
    ATTR_REFS,
    ATTR_TEXT,
    ATTR_TITLE,
    ATTR_TOPIC,
    DOMAIN,
    SERVICE_APPEND,
    SERVICE_DELETE,
    SERVICE_RESTORE,
    SERVICE_SET,
)
from .store import MemoryStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HomeMemoryConfigEntry = ConfigEntry[MemoryStore]

SET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TOPIC): cv.string,
        vol.Required(ATTR_CONTENT): cv.string,
        vol.Optional(ATTR_REFS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_TITLE): cv.string,
    }
)
APPEND_SCHEMA = vol.Schema(
    {vol.Required(ATTR_TOPIC): cv.string, vol.Required(ATTR_TEXT): cv.string}
)
TOPIC_SCHEMA = vol.Schema({vol.Required(ATTR_TOPIC): cv.string})


def _store(hass: HomeAssistant) -> MemoryStore:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise vol.Invalid("Home Memory is not set up")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services once, independent of the config entry."""

    async def handle_set(call: ServiceCall) -> ServiceResponse:
        slug = await _store(hass).async_set(
            call.data[ATTR_TOPIC],
            call.data[ATTR_CONTENT],
            call.data.get(ATTR_REFS),
            call.data.get(ATTR_TITLE),
        )
        return {"topic": slug, "entity_id": f"sensor.{DOMAIN}_{slug}"}

    async def handle_append(call: ServiceCall) -> ServiceResponse:
        slug = await _store(hass).async_append(call.data[ATTR_TOPIC], call.data[ATTR_TEXT])
        return {"topic": slug}

    async def handle_delete(call: ServiceCall) -> ServiceResponse:
        slug = await _store(hass).async_delete(call.data[ATTR_TOPIC])
        return {"topic": slug}

    async def handle_restore(call: ServiceCall) -> ServiceResponse:
        slug = await _store(hass).async_restore(call.data[ATTR_TOPIC])
        return {"topic": slug}

    for name, handler, schema in (
        (SERVICE_SET, handle_set, SET_SCHEMA),
        (SERVICE_APPEND, handle_append, APPEND_SCHEMA),
        (SERVICE_DELETE, handle_delete, TOPIC_SCHEMA),
        (SERVICE_RESTORE, handle_restore, TOPIC_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.OPTIONAL
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomeMemoryConfigEntry) -> bool:
    store = MemoryStore(hass)
    await store.async_load()
    entry.runtime_data = store
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Expose the memory as an LLM API, so Assist and the official MCP server can use it.
    try:
        from .llm_api import async_register_llm_api

        entry.async_on_unload(async_register_llm_api(hass, store))
    except Exception:  # noqa: BLE001 - optional feature, never block setup
        _LOGGER.warning("Home Memory: LLM API could not be registered", exc_info=True)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeMemoryConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
