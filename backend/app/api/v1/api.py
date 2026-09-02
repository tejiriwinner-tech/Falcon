from fastapi import APIRouter
from app.api.v1 import health
from app.api.v1 import providers
from app.api.v1 import market_quotes
from app.api.v1 import signals
from app.api.v1 import news
from app.api.v1 import trade_journal
from app.api.v1 import trade_intelligence
from app.api.v1 import performance_analytics
from app.api.v1 import decision_engine
from app.api.v1 import strategies
from app.routers import markets
from app.api.v1 import market_data
from app.api.v1 import market_state
from app.api.v1 import signal_candidates
from app.api.v1 import validation_results
from app.api.v1 import risk_assessments
from app.api.v1 import execution_readiness
from app.api.v1 import decision_artifacts
from app.api.v1 import missions
from app.api.v1 import repository
from app.api.v1 import analytics
from app.api.v1 import strategy_intelligence
from app.api.v1 import strategy_optimizer
from app.api.v1 import learning_insights
from app.api.v1 import market_regimes
from app.api.v1 import outcome_analysis
from app.api.v1 import calibration
from app.api.v1 import dashboard
from app.api.v1 import intelligence
from app.api.v1 import live_intelligence
from app.api.v1 import runtime
from app.api.v1 import telegram_alerts
from app.api.v1 import orders

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(providers.router)
api_router.include_router(market_quotes.router)
api_router.include_router(signals.router, tags=["signals"])
api_router.include_router(strategies.router, tags=["strategies"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(markets.router, prefix="/markets", tags=["markets"])
api_router.include_router(trade_journal.router, tags=["trade_journal"])
api_router.include_router(trade_intelligence.router, tags=["trade_intelligence"])
api_router.include_router(performance_analytics.router, tags=["performance_analytics"])
api_router.include_router(decision_engine.router, tags=["decision_engine"])
api_router.include_router(market_data.router, tags=["market_data"])
api_router.include_router(market_state.router, tags=["market_state"])
api_router.include_router(signal_candidates.router, tags=["signal_candidates"])
api_router.include_router(validation_results.router, tags=["validation_results"])
api_router.include_router(risk_assessments.router, tags=["risk_assessments"])
api_router.include_router(execution_readiness.router, tags=["execution_readiness"])
api_router.include_router(decision_artifacts.router, tags=["decision_artifacts"])
api_router.include_router(missions.router, tags=["missions"])
api_router.include_router(repository.router, tags=["repository"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(strategy_intelligence.router, tags=["strategy_intelligence"])
api_router.include_router(strategy_optimizer.router, tags=["strategy_optimizer"])
api_router.include_router(learning_insights.router, tags=["learning_insights"])
api_router.include_router(market_regimes.router, tags=["market_regimes"])
api_router.include_router(outcome_analysis.router, tags=["outcome_analysis"])
api_router.include_router(calibration.router, tags=["calibration"])
api_router.include_router(dashboard.router)
api_router.include_router(intelligence.router, tags=["intelligence"])
api_router.include_router(live_intelligence.router, tags=["live_intelligence"])
api_router.include_router(runtime.router)
api_router.include_router(telegram_alerts.router)
api_router.include_router(orders.router)







