"""Industry-mode overlay framework definitions (WS9).

Each overlay is a sparse JSON document deep-merged onto the base
`stock_initiation.json` framework by `runtime/report_v2/runner.py` at startup.
Right-overrides-left at scalar leaves; list extension at list leaves for
`consumer` fact lists. The base framework remains the SHARED root.
"""
