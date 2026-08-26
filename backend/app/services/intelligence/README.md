# Falcon Intelligence Layer

## Quick Start

### API Usage

```python
# Get intelligence for a symbol
GET /api/v1/intelligence?symbol=XAUUSD&timeframe=H1

# Get statistics
GET /api/v1/intelligence/statistics
```

### Python Usage

```python
from app.services.intelligence.intelligence_service import IntelligenceService
from app.models.market_candle import Timeframe

# Initialize service with database session
service = IntelligenceService(db)

# Get intelligence
decision = service.get_intelligence(
    symbol="XAUUSD",
    timeframe=Timeframe.H1
)

# Access results
print(f"Decision: {decision.decision}")
print(f"Confidence: {decision.confidence}%")
print(f"Signal Score: {decision.signal_score}")
```

## Architecture

```
IntelligenceService (Service Layer)
    ↓
IntelligenceEngine (Orchestrator)
    ↓
10 Specialized Engines:
    1. MarketAnalyzer
    2. SignalScorer
    3. RiskEngine
    4. TrendDetector
    5. EntryOptimizer
    6. MarketStructureAnalyzer
    7. VolatilityAnalyzer
    8. ConfidenceEngine
    9. ConfluenceAnalyzer
    10. IntelligenceEngine
```

## Output

- **Decision**: BUY, SELL, WAIT, AVOID
- **Confidence**: 0-100%
- **Signal Score**: 0-100
- **Risk Score**: 0-100
- **Confluence Score**: 0-100
- **Market State**: BULLISH, BEARISH, RANGING, etc.
- **Trend**: Direction and strength
- **Entry Quality**: EXCELLENT, GOOD, AVERAGE, POOR
- **Risk Levels**: Entry, Stop, Target, R/R

## Testing

```bash
# Run test script
cd backend
python test_intelligence.py

# Or test via API
curl "http://localhost:8000/api/v1/intelligence?symbol=XAUUSD&timeframe=H1"
```

## Documentation

See `backend/docs/INTELLIGENCE_LAYER.md` for complete documentation.
