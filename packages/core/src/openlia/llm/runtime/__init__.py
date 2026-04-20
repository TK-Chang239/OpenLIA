"""LLM runtime — public exports.

Server routes depend on these names. Do not rename without coordinated
changes in `openlia_server.routes.*` and the department-plan tests.
"""

from __future__ import annotations

from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatReportThumbnail,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
    SseEvent,
    to_wire,
)
from openlia.llm.runtime.messages import (
    Attachment,
    BatchItem,
    BatchResult,
    ChatMessage,
    ReportRequest,
)
from openlia.llm.runtime.prompts import PromptLoader, PromptSlotNotFound
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import (
    DataProviderDispatcher,
    ToolCallResult,
    ToolDispatcher,
)
from openlia.llm.runtime.web_search import (
    WebSearchAdapter,
    WebSearchResolution,
    WebSearchResult,
    resolve_web_search,
)

__all__ = [
    "Attachment",
    "BatchItem",
    "BatchResult",
    "BatchRunner",
    "CancellationToken",
    "ChatDone",
    "ChatError",
    "ChatMessage",
    "ChatReportThumbnail",
    "ChatRunner",
    "ChatStart",
    "ChatToken",
    "ChatToolCallResult",
    "ChatToolCallStart",
    "DataProviderDispatcher",
    "PromptLoader",
    "PromptSlotNotFound",
    "ReportComplete",
    "ReportError",
    "ReportPhase",
    "ReportRequest",
    "ReportRunner",
    "ReportStart",
    "ReportToolCall",
    "SseEvent",
    "ToolCallResult",
    "ToolDispatcher",
    "WebSearchAdapter",
    "WebSearchResolution",
    "WebSearchResult",
    "await_with_grace",
    "resolve_web_search",
    "to_wire",
]
