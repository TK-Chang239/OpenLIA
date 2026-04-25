# openlia-core

Pure-Python core library for [OpenLIA](https://github.com/TK-Chang239/OpenLIA), the open-source self-hosted AI investor assistant. Provides the seven Department agents (Secretary, Equity Research, Earnings Update, Morning Briefing, Retail Sentiment, Macro Research, Panic Thermometer), LLM provider adapters (OpenAI, Anthropic, OpenRouter, Ollama), data adapters (EODHD, news), YAML prompt templates, and schema-first report generation. Zero web dependencies.

```bash
pip install openlia
```

The runnable server, CLI, and persistence layer ship in the [`openlia`](https://pypi.org/project/openlia/) package, which depends on this one. See the main [OpenLIA repo](https://github.com/TK-Chang239/OpenLIA) for usage, deployment recipes, and full architecture.

MIT License.
