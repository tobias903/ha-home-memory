"""Persistent topic store for Home Memory."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    EVENT_MEMORY_CHANGED,
    MAX_CONTENT_LENGTH,
    SIGNAL_INDEX_UPDATED,
    SIGNAL_TOPIC_ADDED,
    SIGNAL_TOPIC_REMOVED,
    SIGNAL_TOPIC_UPDATED,
    STORAGE_KEY,
    STORAGE_VERSION,
)


def topic_slug(topic: str) -> str:
    """Return the stable key for a topic name."""
    slug = slugify(str(topic).strip())
    if not slug:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_topic"
        )
    return slug


class MemoryStore:
    """Holds all topics and persists them in .storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.topics: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.topics = data.get("topics", {})

    async def _async_save(self) -> None:
        await self._store.async_save({"topics": self.topics})

    def get(self, slug: str) -> dict[str, Any] | None:
        return self.topics.get(slug)

    def index(self) -> dict[str, dict[str, Any]]:
        """Small overview without the content itself."""
        return {
            slug: {
                "title": t["title"],
                "updated": t["updated"],
                "size": len(t["content"]),
                "refs": t.get("refs", []),
            }
            for slug, t in sorted(self.topics.items())
        }

    async def async_set(
        self,
        topic: str,
        content: str,
        refs: list[str] | None = None,
        title: str | None = None,
    ) -> str:
        slug = topic_slug(topic)
        _check_length(content)
        existing = self.topics.get(slug)
        is_new = existing is None
        self.topics[slug] = {
            "title": title or (existing["title"] if existing else str(topic).strip()),
            "content": content,
            "refs": refs if refs is not None else (existing or {}).get("refs", []),
            "updated": dt_util.utcnow().isoformat(),
            "previous_content": existing["content"] if existing else None,
        }
        await self._async_save()
        self._notify(slug, "created" if is_new else "updated", is_new=is_new)
        return slug

    async def async_append(self, topic: str, text: str) -> str:
        slug = topic_slug(topic)
        existing = self.topics.get(slug)
        if existing is None:
            return await self.async_set(topic, text)
        joined = f"{existing['content'].rstrip()}\n{text}" if existing["content"] else text
        return await self.async_set(topic, joined)

    async def async_delete(self, topic: str) -> str:
        slug = topic_slug(topic)
        if slug not in self.topics:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_topic",
                translation_placeholders={"topic": slug},
            )
        del self.topics[slug]
        await self._async_save()
        async_dispatcher_send(self.hass, SIGNAL_TOPIC_REMOVED.format(slug))
        self._notify(slug, "deleted", send_update=False)
        return slug

    async def async_restore(self, topic: str) -> str:
        """Swap current and previous content (undo the last change)."""
        slug = topic_slug(topic)
        existing = self.topics.get(slug)
        if existing is None or existing.get("previous_content") is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="nothing_to_restore",
                translation_placeholders={"topic": slug},
            )
        existing["content"], existing["previous_content"] = (
            existing["previous_content"],
            existing["content"],
        )
        existing["updated"] = dt_util.utcnow().isoformat()
        await self._async_save()
        self._notify(slug, "restored")
        return slug

    def _notify(
        self, slug: str, action: str, *, is_new: bool = False, send_update: bool = True
    ) -> None:
        if is_new:
            async_dispatcher_send(self.hass, SIGNAL_TOPIC_ADDED, slug)
        elif send_update:
            async_dispatcher_send(self.hass, SIGNAL_TOPIC_UPDATED.format(slug))
        async_dispatcher_send(self.hass, SIGNAL_INDEX_UPDATED)
        self.hass.bus.async_fire(EVENT_MEMORY_CHANGED, {"topic": slug, "action": action})


def _check_length(content: str) -> None:
    if len(content) > MAX_CONTENT_LENGTH:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="content_too_long",
            translation_placeholders={"max": str(MAX_CONTENT_LENGTH)},
        )
