"""Constants for Home Memory."""

DOMAIN = "home_memory"

STORAGE_KEY = "home_memory"
STORAGE_VERSION = 1

SIGNAL_TOPIC_ADDED = f"{DOMAIN}_topic_added"
SIGNAL_TOPIC_UPDATED = f"{DOMAIN}_topic_updated_{{}}"
SIGNAL_TOPIC_REMOVED = f"{DOMAIN}_topic_removed_{{}}"
SIGNAL_INDEX_UPDATED = f"{DOMAIN}_index_updated"

EVENT_MEMORY_CHANGED = f"{DOMAIN}_changed"

SERVICE_SET = "set"
SERVICE_APPEND = "append"
SERVICE_DELETE = "delete"
SERVICE_RESTORE = "restore"

ATTR_TOPIC = "topic"
ATTR_CONTENT = "content"
ATTR_TEXT = "text"
ATTR_REFS = "refs"
ATTR_TITLE = "title"

# Upper bound for one topic. Keeps state attributes and LLM context small.
MAX_CONTENT_LENGTH = 16000
