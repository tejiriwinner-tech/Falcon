# Falcon Intelligence Layer - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FALCON INTELLIGENCE LAYER                    │
│                     Institutional-Grade AI Trading Intelligence      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│  Flutter App                                                         │
│  ├── IntelligenceScreen (UI)                                        │
│  └── IntelligenceModel (Data Model)                                 │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓ HTTP GET
┌─────────────────────────────────────────────────────────────────────┐
│                             API LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  FastAPI Router                                                      │
│  ├── GET /api/v1/intelligence?symbol=X&timeframe=Y                  │
│  └── GET /api/v1/intelligence/statistics                            │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│  IntelligenceService                                                 │
│  ├── Coordinates with existing services                             │
│  ├── Manages database sessions                                      │
│  └── Provides facade for intelligence engine                        │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          INTELLIGENCE ENGINE                         │
├─────────────────────────────────────────────────────────────────────┤
│  Main Orchestrator                                                   │
│  └── Combines all engines into final decision                       │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         SPECIALIZED ENGINES                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ Market Analyzer │  │  Signal Scorer  │  │   Risk Engine   │    │
│  │                 │  │                 │  │                 │    │
│  │ • Trend         │  │ • Score 0-100   │  │ • Stop Loss     │    │
│  │ • Momentum      │  │ • Quality       │  │ • Take Profit   │    │
│  │ • Structure     │  │ • Components    │  │ • Risk/Reward   │    │
│  │ • Liquidity     │  │ • Thresholds    │  │ • Position Risk │    │
│  │ • Volatility    │  │                 │  │                 │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ Trend Detector  │  │ Entry Optimizer │  │Volatility Analyz│    │
│  │                 │  │                 │  │                 │    │
│  │ • Primary       │  │ • Best Entry    │  │ • ATR Analysis  │    │
│  │ • Secondary     │  │ • Confirmation  │  │ • BB Width      │    │
│  │ • Intraday      │  │ • Aggressive    │  │ • State         │    │
│  │ • Swing         │  │ • Conservative  │  │ • Expansion     │    │
│  │ • Strength      │  │ • Late          │  │ • Contraction   │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │Confidence Engine│  │Confluence Analyz│  │Structure Analyze│    │
│  │                 │  │                 │  │                 │    │
│  │ • Very High     │  │ • EMA           │  │ • BOS/CHoCH     │    │
│  │ • High          │  │ • RSI           │  │ • HH/HL/LL/LH   │    │
│  │ • Medium        │  │ • MACD          │  │ • Liquidity     │    │
│  │ • Low           │  │ • ATR           │  │ • Supply/Demand │    │
│  │ • Avoid         │  │ • S/R           │  │ • OB/FVG        │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      EXISTING FALCON SERVICES                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  Trend Service  │  │Structure Service│  │Indicator Service│    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │Confluence Servic│  │  Provider       │                          │
│  │                 │  │  Factory        │                          │
│  └─────────────────┘  └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  SQLAlchemy ORM                                                      │
│  ├── MarketCandle (OHLCV data)                                      │
│  └── Other existing models                                          │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          DATABASE                                    │
├─────────────────────────────────────────────────────────────────────┤
│  SQLite / PostgreSQL                                                 │
│  └── falcon.db                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Request
    ↓
Flutter App (IntelligenceScreen)
    ↓
HTTP GET /api/v1/intelligence?symbol=XAUUSD&timeframe=H1
    ↓
FastAPI Router (intelligence.py)
    ↓
IntelligenceService
    ├─→ TrendService → Database → TrendResult
    ├─→ StructureService → Database → StructureResult
    ├─→ IndicatorService → Database → IndicatorResponse
    ├─→ ConfluenceService → Database → ConfluenceResult
    └─→ MarketProvider → API → CurrentPrice
    ↓
IntelligenceEngine (Orchestrator)
    ├─→ MarketAnalyzer → MarketState, Session, Trend, Momentum
    ├─→ SignalScorer → SignalScore (0-100)
    ├─→ RiskEngine → StopLoss, TakeProfit, RiskReward
    ├─→ TrendDetector → Primary, Secondary, Intraday Trends
    ├─→ EntryOptimizer → EntryQuality, EntryTypes
    ├─→ VolatilityAnalyzer → VolatilityState, ATR
    ├─→ ConfidenceEngine → ConfidenceLevel (%)
    └─→ ConfluenceAnalyzer → ConfluenceScore (0-100)
    ↓
Final Decision: BUY/SELL/WAIT/AVOID
    ↓
IntelligenceDecision (Complete Intelligence)
    ↓
JSON Response
    ↓
Flutter App Display
```

## Component Responsibilities

### API Layer
- **Role**: HTTP request handling
- **Responsibility**: Route requests, validate input, return responses
- **Dependencies**: Service layer

### Service Layer
- **Role**: Business logic coordination
- **Responsibility**: Orchestrate services, manage database sessions
- **Dependencies**: Engine layer, existing services

### Engine Layer
- **Role**: Intelligence generation
- **Responsibility**: Analyze data, calculate scores, make decisions
- **Dependencies**: Data models

### Data Layer
- **Role**: Data persistence
- **Responsibility**: Store and retrieve market data
- **Dependencies**: Database

## Design Patterns

### 1. Service Layer Pattern
```
API → Service → Engine → Data
```

### 2. Facade Pattern
```
IntelligenceService (Facade)
    └─→ Multiple Engines (Subsystems)
```

### 3. Strategy Pattern
```
IntelligenceEngine
    └─→ Different analysis strategies (engines)
```

### 4. Repository Pattern
```
Service → Repository → Database
```

### 5. Dependency Injection
```
Service(db: Session) ← Injected dependency
```

## Scalability

```
┌──────────────┐
│ Load Balancer│
└──────┬───────┘
       │
   ┌───┴────┐
   │        │
┌──▼──┐  ┌──▼──┐
│API 1│  │API 2│  ← Horizontal scaling
└──┬──┘  └──┬──┘
   │        │
   └───┬────┘
       │
┌──────▼───────┐
│   Database   │
└──────────────┘
```

## Caching Strategy

```
Request → Check Cache (60s TTL)
    ├─→ Cache Hit → Return cached result
    └─→ Cache Miss → Calculate → Store in cache → Return result
```

## Error Handling Flow

```
Request
    ↓
Try:
    Service Logic
    ↓
    Engine Logic
    ↓
    Success Response
Except HTTPException:
    ↓
    Return HTTP error
Except Exception:
    ↓
    Log error
    ↓
    Return 500 error
```

## Performance Optimization

```
Optimization Layers:
1. Caching (60s TTL) → 80%+ hit rate
2. Database indexing → Fast queries
3. Efficient algorithms → O(n) complexity
4. Minimal object creation → Low memory
5. Synchronous execution → No async overhead
```

## Security Layers

```
1. Input Validation → Enum validation, SQL injection prevention
2. Error Handling → No sensitive data in errors
3. Rate Limiting → (Optional) Prevent abuse
4. Authentication → (Optional) API key required
5. HTTPS → (Production) Encrypted transport
```

---

This architecture ensures:
- ✅ Clean separation of concerns
- ✅ High testability
- ✅ Easy maintenance
- ✅ Horizontal scalability
- ✅ Production readiness
