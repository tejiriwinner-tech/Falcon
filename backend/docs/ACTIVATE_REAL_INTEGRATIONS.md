# Guide: Remove Sample Data and Activate Real Integrations

## Overview

This guide explains how to remove the sample data responses that were added during Phase 1 and activate the real data provider integrations and decision engine.

## Prerequisites

Before proceeding, ensure you have:

1. **Valid API Keys** for the following services:
   - TwelveData API Key (for market data)
   - Financial Modeling Prep (FMP) API Key (for economic calendar)
   - Alpha Vantage API Key (for quotes and historical data)

2. **Environment Configuration**:
   - Copy `.env.example` to `.env`
   - Fill in your actual API keys

3. **Database Setup**:
   - PostgreSQL or SQLite configured
   - DATABASE_URL set in `.env`

## Files with Sample Data

The following files currently return sample data instead of real data:

### 1. Dashboard Service
**File**: `app/core/services/dashboard_service.py`
**Lines with sample data**: ~33, ~78, ~133

**Current behavior**: Returns hardcoded sample trading signals
**Real behavior**: Should call the decision engine to generate real signals

### 2. News Service  
**File**: `app/core/services/news_service.py`
**Lines with sample data**: ~15

**Current behavior**: Returns hardcoded sample economic calendar events
**Real behavior**: Should fetch real economic calendar from FMP API

### 3. Intelligence API
**File**: `app/api/v1/intelligence.py`
**Lines with sample data**: ~44-102

**Current behavior**: Returns hardcoded sample trading intelligence
**Real behavior**: Should call the IntelligenceService to generate real intelligence

## Step-by-Step Instructions

### Step 1: Configure API Keys

Edit your `.env` file:

```bash
# Data Provider API Keys
TWELVEDATA_API_KEY=your_actual_twelvedata_api_key_here
FMP_API_KEY=your_actual_fmp_api_key_here
ALPHA_VANTAGE_API_KEY=your_actual_alpha_vantage_api_key_here

# Database
DATABASE_URL=postgresql://user:password@host:port/database
# or for SQLite:
# DATABASE_URL=sqlite:///./falcon_market_data.db
```

### Step 2: Remove Sample Data from Dashboard Service

**File**: `app/core/services/dashboard_service.py`

**Current code** (around line 33):
```python
# Return sample data for Phase 1.1 to avoid timeout
return {
    "signals": [SignalItem(...)],
    "market_status": {...},
    "news": [...]
}
```

**Change to**:
```python
# Call the real decision engine
try:
    # Use the real signal service
    signals_response = await signal_service.get_signals()
    return {
        "signals": signals_response.signals,
        "market_status": await _get_market_status(),
        "news": await news_service.get_economic_calendar()
    }
except Exception as e:
    logger.error(f"Dashboard service error: {e}")
    raise
```

**Note**: You may need to implement `_get_market_status()` method or use existing market data services.

### Step 3: Remove Sample Data from News Service

**File**: `app/core/services/news_service.py`

**Current code** (around line 15):
```python
# Return sample economic calendar events for Phase 1.2
return {
    "events": [
        {"date": "2024-01-15", "event": "Federal Reserve Meeting", ...},
        ...
    ]
}
```

**Change to**:
```python
# Fetch real economic calendar from FMP API
from app.core.providers.fmp_provider import FMPProvider

fmp_provider = FMPProvider()
try:
    calendar = await fmp_provider.get_economic_calendar(
        days_ahead=settings.CALENDAR_LOOKAHEAD_DAYS
    )
    return calendar
except Exception as e:
    logger.error(f"Failed to fetch economic calendar: {e}")
    raise
```

**Note**: Ensure `FMPProvider` is properly configured and the `get_economic_calendar` method exists.

### Step 4: Remove Sample Data from Intelligence API

**File**: `app/api/v1/intelligence.py`

**Current code** (around line 44-102):
```python
# Return sample intelligence data for Phase 1.4
sample_data = {
    'XAUUSD': {
        'decision': 'BUY',
        'confidence': 75.0,
        ...
    },
    ...
}
data = sample_data.get(symbol, {...})
```

**Change to**:
```python
# Call the real IntelligenceService
intelligence_service = IntelligenceService(db)
try:
    result = await intelligence_service.get_intelligence(
        symbol=symbol,
        timeframe=timeframe
    )
    return {
        'success': True,
        'data': result
    }
except Exception as e:
    logger.error(f"Intelligence API error for {symbol}: {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Failed to generate intelligence: {str(e)}"
    )
```

### Step 5: Test API Key Validity

Before removing sample data, test that your API keys work:

```bash
# Test TwelveData
curl "https://api.twelvedata.com/time_series?symbol=XAUUSD&interval=1h&apikey=YOUR_TWELVEDATA_KEY"

# Test FMP
curl "https://financialmodelingprep.com/stable/economic_calendar?apikey=YOUR_FMP_KEY"

# Test Alpha Vantage
curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=XAUUSD&apikey=YOUR_ALPHA_KEY"
```

Expected responses should return JSON data, not error messages.

### Step 6: Verify Decision Engine Works

The decision engine should be functional. Test it:

```bash
# Start the backend
cd backend
python main.py

# In another terminal, test the decision engine endpoint
curl http://localhost:8000/api/v1/intelligence?symbol=XAUUSD
```

If this times out or fails, the decision engine needs debugging before removing sample data.

### Step 7: Gradual Rollout (Recommended)

Instead of removing all sample data at once, do it gradually:

1. **First**: Remove sample data from news service (easiest, external API only)
2. **Second**: Remove sample data from intelligence API (depends on decision engine)
3. **Third**: Remove sample data from dashboard service (depends on multiple services)

### Step 8: Monitor and Debug

After removing sample data:

1. **Check logs** for any errors:
   ```bash
   docker-compose logs -f falcon-backend
   # or
   tail -f logs/app.log
   ```

2. **Test endpoints**:
   ```bash
   # Test news
   curl http://localhost:8000/api/v1/news

   # Test intelligence
   curl http://localhost:8000/api/v1/intelligence?symbol=XAUUSD

   # Test dashboard
   curl http://localhost:8000/api/v1/dashboard
   ```

3. **Monitor response times** - if endpoints are slow, consider:
   - Adding caching
   - Optimizing database queries
   - Adjusting timeout values

### Step 9: Run Integration Tests

After removing sample data, run the integration tests:

```bash
# Start the backend in one terminal
cd backend
python main.py

# In another terminal, run tests
python -m pytest tests/test_api_integration.py -v
```

Fix any failing tests by updating expected responses or fixing the underlying issues.

### Step 10: Update Mobile App (if needed)

If the mobile app was relying on specific sample data formats, update it to handle the real data formats:

**File**: `mobile/lib/services/api/api_service.dart`

Check that the model parsing matches the real API responses. Update models if necessary.

## Troubleshooting

### Issue: API Key Errors

**Symptom**: `401 Unauthorized` or `403 Forbidden` from data providers

**Solution**:
- Verify API keys are correct in `.env`
- Check API key hasn't expired
- Ensure you have sufficient API quota

### Issue: Decision Engine Timeout

**Symptom**: Request to `/api/v1/intelligence` times out

**Solution**:
- Check decision engine logs for errors
- Increase timeout in settings
- Ensure database is accessible
- Check if market data is available

### Issue: No Data Returned

**Symptom**: Endpoints return empty arrays or null values

**Solution**:
- Verify data providers are returning data
- Check database has historical data
- Ensure market is open (some providers only return data during market hours)

### Issue: Format Mismatches

**Symptom**: Mobile app fails to parse API responses

**Solution**:
- Compare sample data format with real data format
- Update mobile app models to match real API responses
- Add schema validation in backend

## Fallback Plan

If real integrations don't work as expected:

1. **Keep sample data as fallback**:
   ```python
   try:
       # Try real integration
       return await real_service.get_data()
   except Exception as e:
       logger.warning(f"Real integration failed, using sample data: {e}")
       return get_sample_data()
   ```

2. **Add feature flag**:
   ```python
   USE_REAL_DATA = os.getenv("USE_REAL_DATA", "false").lower() == "true"
   
   if USE_REAL_DATA:
       return await real_service.get_data()
   else:
       return get_sample_data()
   ```

## Verification Checklist

After completing the integration activation:

- [ ] All API keys are configured in `.env`
- [ ] API keys are tested and return valid data
- [ ] Sample data removed from dashboard_service.py
- [ ] Sample data removed from news_service.py
- [ ] Sample data removed from intelligence.py
- [ ] Backend starts without errors
- [ ] `/api/v1/news` returns real data
- [ ] `/api/v1/intelligence` returns real data
- [ ] `/api/v1/dashboard` returns real data
- [ ] Integration tests pass
- [ ] Mobile app can parse real data responses
- [ ] Response times are acceptable (< 5 seconds)
- [ ] Error handling works for failed API calls

## Additional Resources

- **TwelveData Documentation**: https://twelvedata.com/docs
- **FMP Documentation**: https://site.financialmodelingprep.com/developer/docs
- **Alpha Vantage Documentation**: https://www.alphavantage.co/documentation/
- **Falcon Decision Engine**: See `app/services/decision/` directory

## Support

If you encounter issues:

1. Check the logs for specific error messages
2. Verify API keys are valid and have quota
3. Test API endpoints directly using curl
4. Review the provider documentation for any changes
5. Check if market is open for real-time data