"""Per-template loader functions producing TemplateSpec instances.

Each module in this package defines a `load_<template_id>_template()` callable
and registers it with `openlia.reports.frameworks.registry.default_registry` at
import time. Importing this package eagerly imports every shipped loader, which
is what makes the default templates discoverable via `default_registry.get(...)`.
"""

from __future__ import annotations

from openlia.reports.frameworks.loaders import stock_initiation  # noqa: F401
