"""Server-side implementations of runtime tools declared in core.

The core ``openlia.llm.runtime`` package owns the schema + dispatch
contract for tools the LLM can invoke during a chat turn (slice 12's
``recall_artifacts``, future cross-package tools). Production
implementations live here because they need server-side dependencies
the core package must never import — DB sessions, embedding providers,
HTTP clients.

The ``ChatRunner`` accepts these implementations as injected callables
at construction time, so the core/server boundary stays clean.
"""
