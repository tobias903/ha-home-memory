"""Sensors for Home Memory: one index sensor plus one sensor per topic."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HomeMemoryConfigEntry
from .const import (
    DOMAIN,
    SIGNAL_INDEX_UPDATED,
    SIGNAL_TOPIC_ADDED,
    SIGNAL_TOPIC_REMOVED,
    SIGNAL_TOPIC_UPDATED,
)
from .store import MemoryStore


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeMemoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    store = entry.runtime_data
    device = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Home Memory",
        entry_type=DeviceEntryType.SERVICE,
    )
    async_add_entities(
        [MemoryIndexSensor(store, entry.entry_id, device)]
        + [MemoryTopicSensor(store, entry.entry_id, device, slug) for slug in store.topics]
    )

    @callback
    def _add_topic(slug: str) -> None:
        async_add_entities([MemoryTopicSensor(store, entry.entry_id, device, slug)])

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_TOPIC_ADDED, _add_topic))


class MemoryIndexSensor(SensorEntity):
    """Number of topics; attribute `topics` lists them without content."""

    _attr_has_entity_name = True
    _attr_translation_key = "index"
    _attr_icon = "mdi:brain"
    _attr_should_poll = False

    def __init__(self, store: MemoryStore, entry_id: str, device: DeviceInfo) -> None:
        self._store = store
        self._attr_unique_id = f"{entry_id}_index"
        self._attr_device_info = device
        self.entity_id = f"sensor.{DOMAIN}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_INDEX_UPDATED, self.async_write_ha_state)
        )

    @property
    def native_value(self) -> int:
        return len(self._store.topics)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "topics": self._store.index(),
            "usage": (
                "Read a topic with the state of sensor.home_memory_<topic> (attribute content). "
                "Write with action home_memory.set / home_memory.append."
            ),
        }


class MemoryTopicSensor(SensorEntity):
    """One topic. State = last change, attribute `content` = the knowledge."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:note-text-outline"
    _attr_should_poll = False
    # Content can be long; keep it out of the recorder database.
    _unrecorded_attributes = frozenset({"content", "previous_content"})

    def __init__(
        self, store: MemoryStore, entry_id: str, device: DeviceInfo, slug: str
    ) -> None:
        self._store = store
        self._slug = slug
        self._attr_unique_id = f"{entry_id}_topic_{slug}"
        self._attr_device_info = device
        self._attr_name = store.topics[slug]["title"]
        self.entity_id = f"sensor.{DOMAIN}_{slug}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_TOPIC_UPDATED.format(self._slug), self._updated
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_TOPIC_REMOVED.format(self._slug), self._removed
            )
        )

    @callback
    def _updated(self) -> None:
        topic = self._store.get(self._slug)
        if topic:
            self._attr_name = topic["title"]
        self.async_write_ha_state()

    @callback
    def _removed(self) -> None:
        registry = er.async_get(self.hass)
        if self.registry_entry:
            registry.async_remove(self.entity_id)
        else:
            self.hass.async_create_task(self.async_remove())

    @property
    def available(self) -> bool:
        return self._slug in self._store.topics

    @property
    def native_value(self) -> datetime | None:
        topic = self._store.get(self._slug)
        return dt_util.parse_datetime(topic["updated"]) if topic else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        topic = self._store.get(self._slug) or {}
        return {
            "topic": self._slug,
            "content": topic.get("content"),
            "refs": topic.get("refs", []),
            "previous_content": topic.get("previous_content"),
        }
