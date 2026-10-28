# Home Memory

A topic-based memory for AI assistants in Home Assistant.

Home Assistant knows your entities, areas and automations. It does not know *why* things are set up the way they are: that the heat pump runs on its own meter, that the pool light changes colour by toggling, that a sensor is offline every winter on purpose. Home Memory stores this kind of knowledge inside Home Assistant, so any assistant can read it and keep it current without touching your YAML files.

## How it works

- After setup the memory is empty. Topics are created when something writes to them.
- Each topic becomes a sensor, `sensor.home_memory_<topic>`. The state is the time of the last change, the attribute `content` holds the knowledge, `refs` links entities, devices or areas.
- `sensor.home_memory` lists all topics (title, last change, size, refs) without their content, so an assistant can find the right topic cheaply.
- Data lives in `.storage/home_memory` and is excluded from the recorder database.
- Every change fires the event `home_memory_changed` and shows up in the logbook. The previous version of a topic is kept and can be restored.

## Installation

1. HACS → three-dot menu → *Custom repositories* → add `https://github.com/tobias903/ha-home-memory`, type *Integration*.
2. Install *Home Memory*, restart Home Assistant.
3. Settings → Devices & services → *Add integration* → *Home Memory*.

## Actions

| Action | Fields | Effect |
|---|---|---|
| `home_memory.set` | `topic`, `content`, optional `refs`, `title` | Create or replace a topic |
| `home_memory.append` | `topic`, `text` | Add text at the end, creates the topic if needed |
| `home_memory.delete` | `topic` | Remove topic and sensor |
| `home_memory.restore` | `topic` | Undo the last change |

All actions optionally return the topic key.

## Use with AI assistants

- **Any MCP server that can read states and call actions** (for example the community *MCP Server* integration): read `sensor.home_memory`, then the topic sensor you need; write with the actions above.
- **Official Model Context Protocol Server / Assist:** Home Memory registers an LLM API named *Home Memory* with the tools `home_memory_list`, `home_memory_read`, `home_memory_write` and `home_memory_append`. Enable it in the MCP server or conversation agent options.

See [docs/AI_GUIDE.md](docs/AI_GUIDE.md) for instructions you can give your assistant.

## Limits

- One topic holds up to 16,000 characters. Split larger knowledge into several topics.
- Do not store secrets. The content is visible to everyone who can see the entity.
