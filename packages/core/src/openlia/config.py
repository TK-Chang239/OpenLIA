"""Reserved placeholder for a future core config loader.

This module has no importers today and does not load anything. Environment
configuration is loaded by the server CLI (`openlia_server.cli` reads `.env`
via python-dotenv at startup) and consumed directly from `os.environ` by the
modules that need it. Config flows one direction: env vars -> server startup
-> core.
"""
