"""Per-department HTTP routers."""

from openlia_server.routes.departments.earnings_update import (
    build_earnings_update_router,
)
from openlia_server.routes.departments.equity_research import (
    build_equity_research_router,
)
from openlia_server.routes.departments.equity_research_v2 import (
    build_equity_research_v2_router,
)
from openlia_server.routes.departments.equity_research_v2_models import (
    build_equity_research_v2_models_router,
)
from openlia_server.routes.departments.macro_research import (
    build_macro_research_router,
)
from openlia_server.routes.departments.morning_briefing import (
    build_morning_briefing_router,
)
from openlia_server.routes.departments.panic_thermometer import (
    build_panic_thermometer_router,
)
from openlia_server.routes.departments.retail_sentiment import (
    build_retail_sentiment_router,
)
from openlia_server.routes.departments.secretary import build_secretary_router

__all__ = [
    "build_earnings_update_router",
    "build_equity_research_router",
    "build_equity_research_v2_models_router",
    "build_equity_research_v2_router",
    "build_macro_research_router",
    "build_morning_briefing_router",
    "build_panic_thermometer_router",
    "build_retail_sentiment_router",
    "build_secretary_router",
]
