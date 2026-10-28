"""Expose Home Memory as an LLM API (Assist, official MCP server)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN
from .store import MemoryStore, topic_slug

API_PROMPT = (
    "Home Memory holds durable knowledge about this home that Home Assistant itself "
    "does not know: how systems relate, house rules, seasonal setups, known quirks. "
    "Call home_memory_list first, then read only the topics you need. "
    "Write only facts the user stated or confirmed, keep topics short and factual, "
    "and never store passwords, tokens or personal identification numbers."
)


class _MemoryTool(llm.Tool):
    def __init__(self, store: MemoryStore) -> None:
        self.store = store


class ListTool(_MemoryTool):
    name = "home_memory_list"
    description = "List all memory topics with title, last update, size and linked entities."

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        return {"topics": self.store.index()}


class ReadTool(_MemoryTool):
    name = "home_memory_read"
    description = "Read the full content of one memory topic."
    parameters = vol.Schema({vol.Required("topic"): str})

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        slug = topic_slug(tool_input.tool_args["topic"])
        topic = self.store.get(slug)
        if topic is None:
            return {"error": f"unknown topic {slug}", "topics": list(self.store.topics)}
        return {"topic": slug, **{k: v for k, v in topic.items() if k != "previous_content"}}


class WriteTool(_MemoryTool):
    name = "home_memory_write"
    description = (
        "Create or replace a memory topic. Replaces the whole content; "
        "the previous version is kept for one undo."
    )
    parameters = vol.Schema(
        {
            vol.Required("topic"): str,
            vol.Required("content"): str,
            vol.Optional("refs"): [str],
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        args = tool_input.tool_args
        slug = await self.store.async_set(args["topic"], args["content"], args.get("refs"))
        return {"topic": slug, "result": "saved"}


class AppendTool(_MemoryTool):
    name = "home_memory_append"
    description = "Append a line to a memory topic (creates the topic if missing)."
    parameters = vol.Schema({vol.Required("topic"): str, vol.Required("text"): str})

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        args = tool_input.tool_args
        slug = await self.store.async_append(args["topic"], args["text"])
        return {"topic": slug, "result": "appended"}


@dataclass(slots=True, kw_only=True)
class HomeMemoryAPI(llm.API):
    store: MemoryStore

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(
            api=self,
            api_prompt=API_PROMPT,
            llm_context=llm_context,
            tools=[
                ListTool(self.store),
                ReadTool(self.store),
                WriteTool(self.store),
                AppendTool(self.store),
            ],
        )


def async_register_llm_api(hass: HomeAssistant, store: MemoryStore) -> Callable[[], None]:
    return llm.async_register_api(
        hass, HomeMemoryAPI(hass=hass, id=DOMAIN, name="Home Memory", store=store)
    )
