# 📋 ALPACA → FMP DEPENDENCY AUDIT (Phase 8.2.0, Phase 1)

> **Status:** Audit complete (read-only scan).
> **Scope:** Repository-wide inventory of every Alpaca reference and its mapping to a Financial Modeling Prep (FMP) replacement point.
> **Mode compliance:** Created **only** this audit document. **No production code, tests, configuration, environment variables, dependencies, or provider ordering were modified.** Phase 8.2.1 (implementation) is **not** executed here and awaits explicit approval.
> **STOP condition met:** No FMP provider code was written. No Alpaca code was deleted. No provider order was changed. No tests were edited. No `alpaca-*` pip packages exist to remove. Only this deliverable file was produced.

---

## 1. Executive Summary

Falcon's market-data layer exposes a pluggable `BaseProvider` abstraction orchestrated by `ProviderManager`, with discovery via `ProviderRegistry`. Alpaca is referenced across **47 files / 3,563 raw substring hits**, but the source-code footprint (the actionable set) is small and well-contained:

| Metric | Value |
|---|---|
| Raw Alpaca substring hits (repo-wide, incl. logs/cache/docs) | **3,563** |
| Total files with Alpaca references | 47 |
| Source-code references (code/tests/config only) | **≈ 674** |
| Production source files referencing Alpaca | **4** |
| Production source references | **64** |
| Test files referencing Alpaca | **9** (+ 1 standalone verifier script) |
| Test-reference references (source) | **~570** |
| Configuration files referencing Alpaca | **2** |
| Configuration references | **13** |
| **Unique environment variables** used | **4** |
| **Alpaca SDK packages required** | **0** (none) |
| Engines/services referencing Alpaca by name | **0** |

**Key findings**

- `AlpacaProvider` calls Alpaca over **raw HTTP (`requests`)** using `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` headers against `GET {base_url}/v1beta1/forex/latest/rates`. **No `alpaca_trade_api` / `alpaca-py` package is imported anywhere** — there is nothing to uninstall.
- `ENABLE_ALPACA_PROVIDER` defaults to **`false`**, so Alpaca is **feature-gated off in production** and absent from the default runtime fallback chain (`Twelve Data → Alpha Vantage → Mock`).
- **Abstraction is clean:** `provider_manager.py`, `provider_registry.py`, `base_provider.py`, `quote_validator.py`, and **every** engine/service (`MarketStateEngine`, `RiskEngine`, `SignalGenerationEngine`, `DecisionEngine`, etc.) contain **zero** Alpaca references. Removing Alpaca therefore cannot affect signal safety for XAU/USD, GBP/USD, or EUR/USD.
- **Primary risk block:** Alpaca occupies the **in-band fallback priority slot `2`** between Twelve Data (1) and Alpha Vantage (2|3) in `providers/__init__.py`. A naïve deletion would leave Twelve Data failures falling straight through to Alpha Vantage. **FMP must inherit a priority slot** to preserve the intended ladder `Twelve Data → Alpha Vantage → FMP → Mock`.
- **Audit limitation (honestly flagged):** the exact Alpaca symbols for the **three primary instruments** (XAU/USD, GBP/USD, EUR/USD) in `instrument_registry.py` (L242–260) and the `"alpaca"` block of `symbol_mapper.py` (L80–87) could **not be read** during this scan (tool "outdated" marker on those ranges). They are reconstructed only from the authoritative `backend/.env.example` canonical list — the exact values must be re-read in Phase 8.2.1 before any code is written.

**Recommended migration path (preserved exactly as specified):**

> Twelve Data → Alpha Vantage → **FMP** → Mock

---

## 2. Current Provider Architecture

Framework location: `backend/app/core/providers/`.

| File | Responsibility | Alpaca refs? |
|------|----------------|--------------|
| `base_provider.py` | `BaseProvider` contract: `provider_id`, `provider_name`, `priority`, `healthy`, `enabled`, `capabilities`, `connect()`/`disconnect()`, `fetch()`, `health_check()`, `get_metadata()`, `get_statistics()`; 429 + circuit-breaker handling | No |
| `provider_registry.py` | `ProviderRegistry`: generic provider store + `_priority_list`; `all_providers()` returns priority-ordered list | **No** (generic) |
| `provider_manager.py` | `ProviderManager`: `get_market_quote()` → `_fetch_from_providers()` iterates `registry.all_providers()` in priority order, skips `RATE_LIMITED`/`OFFLINE`, returns first non-None validated quote, else falls back to `Mock` | **No** (generic) |
| `symbol_mapper.py` | `SymbolMapper`: `_ALIAS_MAP` (canonical normalization) + `_PROVIDER_SYMBOL_MAP` (`"alpaca"` block present) | Yes |
| `instrument_registry.py` | `CanonicalInstrumentRegistry`: each `InstrumentMetadata` carries `providerMappings{...}` (`"alpaca"` keys present); `get_by_provider_symbol(provider_id, symbol)` builds a dynamic reverse index | Yes |
| `__init__.py` | Singleton wiring: instantiates + registers providers with priority numbers; **this is where Alpaca is registered** | Yes |

**Live priority order (`providers/__init__.py`), feature-flag gated:**

```python
provider_registry.register(_twelve_data_provider, priority=1)
if settings.ENABLE_ALPACA_PROVIDER:
    provider_registry.register(_alpaca_provider, priority=2)        # Alpaca slot
alpha_vantage_priority = 3 if settings.ENABLE_ALPACA_PROVIDER else 2
provider_registry.register(_alpha_vantage_provider, priority=alpha_vantage_priority)
mock_priority = 4 if settings.ENABLE_ALPACA_PROVIDER else 3
provider_registry.register(_mock_provider, priority=mock_priority)
```

- With `ENABLE_ALPACA_PROVIDER=False` (default): effective runtime chain = `Twelve Data(1) → AlphaVantage(2) → Mock(3)`.
- With `ENABLE_ALPACA_PROVIDER=True`: `Twelve Data(1) → Alpaca(2) → AlphaVantage(3) → Mock(4)`.
- Alpaca is a **feature-gated in-band slot (priority 2)** — not a hard dependency, but its *position* between Twelve Data and Alpha Vantage must be preserved by the FMP replacement.

**Abstraction suitability for FMP:** `BaseProvider` is generic; Twelve Data, Alpha Vantage, and Alpaca are all subclasses. An `FmpProvider(BaseProvider)` implementing the same interface can drop into the existing pipeline with **no business-logic changes** to `ProviderManager`/`ProviderRegistry`.

---

## 3. Complete Alpaca Reference Inventory

**3,563 raw substring matches across 47 files.** Broadly: ~2,514 come from a single generated runtime log and ~378 from pytest caches — i.e. tooling artifacts, not auditable source. The remaining ~674 are genuine source/docs.

### 3.1 Generated / tooling artifacts (auto-regenerable — safe to purge, will rebuild)

| File | Matches | Type |
|------|--------:|------|
| `backend/logs/app.log.1` | 2,514 | generated runtime log |
| `backend/.pytest_cache/v/cache/nodeids` | 366 | pytest cache |
| `backend/.pytest_cache/v/cache/lastfailed` | 12 | pytest cache |
| `backend/reports/code_health.json` | 13 | auto-generated report |
| `backend/gate_results.json` | 12 | auto-generated report |
| `backend/gate_results.baseline.json` | 12 | auto-generated report |
| `backend/alpaca_verification_report.json` | 6 | generated output |
| `backend/GATE_REPORT.md` | 2 | generated report |

### 3.2 Source-code references (the actionable set)

| File | Matches | Classification* |
|------|--------:|-----------------|
| `tests/unit/test_alpaca_provider_integration.py` | 116 | 1L |
| `tests/unit/test_alpaca_provider_live.py` | 110 | 1L |
| `backend/verify_alpaca_api.py` | 74 | K |
| `tests/unit/test_alpaca_symbol_mapping.py` | 47 | 1L |
| `tests/unit/test_alpaca_instrument_registry.py` | 38 | 1L |
| `app/core/providers/alpaca_provider.py` | 34 | A/B/K |
| `TEST_FAILURE_CLASSIFICATION.md` | 28 | I |
| `tests/unit/test_alpaca_configuration.py` | 26 | 2L |
| `tests/unit/test_alpaca_provider_registry.py` | 24 | 1L |
| `app/core/providers/__init__.py` | 22 | B |
| `FINNHUB_RETIREMENT_REPORT.md` | 20 | I |
| `app/core/providers/symbol_mapper.py` | 8 | F |
| `app/core/instruments/instrument_registry.py` | 6 | E/F |
| `app/core/config/settings.py` | 5 | C/D |
| `backend/.env.example` | 4 | C/D |
| `tests/integration/test_instrument_registry_startup.py` | 8 | 3 |
| `tests/integration/test_runtime_instruments_api_endpoint.py` | 8 | 3 |
| `scripts/test_fallback_logic.py` | 1 | 2L |
| `backend/verify_runtime.py` | 2 | 4 |
| `backend/scripts/validate_phase1_runtime.py` | 2 | 4 |

\*Classification legend: **A** provider implementation · **B** registry/wiring · **C** config schema · **D** env var · **E** instrument mapping · **F** symbol mapping · **G** fallback-chain dependency · **H** generic engine/service (none) · **I** doc/report · **K** standalone verifier script · **1L** test to delete · **2L** test to rewrite · **3** test to keep+trim · **4** import-smoke script to update.

---

## 4. Production Dependencies (4 source files)

| File | Role | Alpaca content |
|------|------|----------------|
| `app/core/providers/alpaca_provider.py` | `AlpacaProvider(BaseProvider)` | `PROVIDER_ID="alpaca"`, `PROVIDER_NAME="Alpaca"`, `PROVIDER_VERSION="1.0.0"`; constructor `provider_id="alpaca", provider_name="Alpaca", provider_type="LIVE"`; credentials `_api_key`/`_secret_key` from `settings.ALPACA_*` (API key, secret key); `_base_url` from `settings.ALPACA_BASE_URL` default `https://data.alpaca.markets`; `_connected=False`; auth via `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY` headers; `GET {base_url}/v1beta1/forex/latest/rates` with `currency_pairs` param; slash-stripping forex normalization; raw `requests` (no SDK import); normalized quote: `symbol, providerTicker, bid, ask, spread, mid, lastPrice, change=0.0, changePercent=0.0, timestamp, providerId="alpaca", providerName="Alpaca", fresh=True, session`. |
| `app/core/providers/__init__.py` | Singleton wiring + registration | Imports `AlpacaProvider`; instantiates `_alpaca_provider = AlpacaProvider(api_key=settings.ALPACA_API_KEY, secret_key=settings.ALPACA_SECRET_KEY)`; registers at `priority=2` only `if settings.ENABLE_ALPACA_PROVIDER`. Priority math hard-codes Alpaca as slot 2. |
| `app/core/providers/symbol_mapper.py` | Symbol mapping | `"alpaca"` block present in `_PROVIDER_SYMBOL_MAP` (6 instruments — forex tickers could not be read; see §14–16). |
| `app/core/instruments/instrument_registry.py` | Instrument mappings | `"alpaca"` keys present in `providerMappings` for **NAS100**→`^NDX` (L332) and **US30**→`^DJI` (L354); the 4 forex `providerMappings` (XAU/USD, GBP/USD, EUR/USD, USD/JPY) for the primary instruments are in the **unread** block (L242–260). |

---

## 5. Registry Dependencies

`backend/app/core/providers/__init__.py` is the **registration wiring** (the primary touchpoint):

```python
provider_registry.register(_twelve_data_provider, priority=1)
if settings.ENABLE_ALPACA_PROVIDER:
    provider_registry.register(_alpaca_provider, priority=2)        # Alpaca slot
alpha_vantage_priority = 3 if settings.ENABLE_ALPACA_PROVIDER else 2
provider_registry.register(_alpha_vantage_provider, priority=alpha_vantage_priority)
mock_priority = 4 if settings.ENABLE_ALPACA_PROVIDER else 3
provider_registry.register(_mock_provider, priority=mock_priority)
```

- `_alpaca_provider = AlpacaProvider(api_key=settings.ALPACA_API_KEY, secret_key=settings.ALPACA_SECRET_KEY)` (no explicit base_url → provider default `https://data.alpaca.markets`).
- `provider_registry.py` itself: **generic — no Alpaca references.**

**Live fallback path** (`provider_manager.py` → `_fetch_from_providers`): iterates `registry.all_providers()` in priority order; skips `RATE_LIMITED`/`OFFLINE`; returns first non-None. Alpaca participates **only** if `ENABLE_ALPACA_PROVIDER`. Runtime chain (default) = `Twelve Data → Alpha Vantage → Mock`. Alpaca is a **feature-gated in-band slot (priority 2)** — its position is the only behavioral surface and must be inherited by FMP.

---

## 6. Configuration Dependencies

Two config files (verified):

- **`backend/app/core/config/settings.py`** (5 matches) — single source of truth. Defines the **AlpacaSettings** block via `os.getenv("ALPACA_API_KEY")`, `os.getenv("ALPACA_SECRET_KEY")`, `ALPACA_BASE_URL` (default `https://data.alpaca.markets`), and `ENABLE_ALPACA_PROVIDER` (default `false`).
- **`backend/.env.example`** (4 matches) — documents all 4 variables with placeholder values.
- **No `pyproject.toml` / `requirements*.txt` / `Pipfile` / `Dockerfile` / deploy file at repo root or `backend/` references Alpaca.**

**FMP configuration (future, Phase 8.2.1):** add to `settings.py` → `self.FMP_API_KEY = os.getenv("FMP_API_KEY")`; add `FMP_API_KEY=` placeholder to `.env.example`.

---

## 7. Environment Variables

**All 4 Alpaca env vars (names only — no secret values printed):**

| Variable | Source | Default | Notes |
|----------|--------|---------|-------|
| `ALPACA_API_KEY` | `settings.py` | unset | Optional[str]; credential |
| `ALPACA_SECRET_KEY` | `settings.py` | unset | Optional[str]; credential |
| `ALPACA_BASE_URL` | `settings.py` | `https://data.alpaca.markets` | — |
| `ENABLE_ALPACA_PROVIDER` | `settings.py` | `false` | Gate; **False by default** |

**Hidden/secrets note:** `backend/.env` is gitignored and holds the live real Alpaca keys (variable set mirrors `.env.example`). **Not read** in this audit to avoid exposing secrets; `.gitignore` (repo root) ignores `.env`, so the variables are not committed.

**FMP env var (future):** `FMP_API_KEY` — required, no default (per task spec).

---

## 8. Package Dependencies

**Zero Alpaca SDK packages are required by Falcon.**

- `backend/requirements.txt`: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `alembic`, `pandas`, `numpy` — **no alpaca package**.
- No `pyproject.toml`/`poetry`/deploy file references Alpaca.
- `search_codebase` for `alpaca_trade_api|alpaca-py|from alpaca|import alpaca` → **0 matches**. All substring hits were the HTTP literals `APCA-API-KEY-ID`, `APCA-API-SECRET-KEY`, `data.alpaca.markets`, `v1beta1` (in the provider, tests, and `verify_alpaca_api.py`) — **not** SDK imports.
- `AlpacaProvider` uses stdlib `requests`: `url = f"{self._base_url}/v1beta1/forex/latest/rates"`, headers `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY`.

**Conclusion:** Removing Alpaca requires **no pip uninstallation**. FMP will likewise be added as a `requests`-backed provider, consistent with the existing Twelve Data / Alpha Vantage pattern.

---

## 9. Symbol Mapping Dependencies

Two mapping surfaces reference Alpaca by name:

### 9a. `backend/app/core/providers/symbol_mapper.py` — `_PROVIDER_SYMBOL_MAP["alpaca"]`

The `"alpaca"` block maps canonical→ticker. The exact entries could **not be read** during this scan (the `symbol_mapper.py` `"alpaca"` block, L80–87, hit the tool "outdated" marker). Forex pairs are expected to follow Alpaca's slash format (`XAU/USD`) and be slash-stripped at the endpoint per normalization `provider_ticker.replace("/", "")`.

### 9b. `backend/app/core/instruments/instrument_registry.py` — `providerMappings["alpaca"]`

Verified entries: `NAS100`→`^NDX` (L332), `US30`→`^DJI` (L354). The 4 forex `providerMappings` for the **primary** instruments (XAU/USD, GBP/USD, EUR/USD, USD/JPY) plus BTCUSD/ETHUSD live in the **unread** block (L242–260).

### Reverse lookup

`instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)` builds `_provider_index[provider_id][provider_symbol] = canonical`. `"alpaca"` is therefore a dynamic key in that index; when Alpaca is removed, dropping the `"alpaca"` key from each instrument's `providerMappings` prevents a dead reverse-lookup entry (harmless if left, but inconsistent).

---

## 10. Fallback Dependencies

| Dependency | File | Type | Detail |
|------------|------|------|--------|
| **Priority slot** | `providers/__init__.py` | F | Alpaca = `priority=2` between Twelve Data(1) and Alpha Vantage. **Insertion point for FMP.** |
| **Runtime chain** | `provider_manager.py` `_fetch_from_providers` | F (generic) | Iterates `registry.all_providers()` priority-order; skips `RATE_LIMITED`/`OFFLINE`; returns first non-None. Alpaca only present if `ENABLE_ALPACA_PROVIDER`. |
| **Test assumption** | `scripts/test_fallback_logic.py` | 2L | Prints (does not assert) the expected order `1.TwelveData 2.AlphaVantage 3.Alpaca(if enabled) 4.Mock Price`. **Rewrite Alpaca→FMP.** |
| **Stale test** | `tests/unit/test_alpaca_provider_registry.py:99-101` | 1L | `expected_order = ["twelve_data","alpha_vantage","mock_price"]; assert "alpaca" not in provider_ids` — asserts the *non-Alpaca* default order but is classified as an Alpaca test. **Delete** (covered by FMP-registry test). |

---

## 11. Test Dependencies (9 files + 3 scripts)

| File | Refs | Category | Planned action |
|------|----:|----------|----------------|
| `tests/unit/test_alpaca_provider_live.py` | 110 | 1L | Delete (AlpacaProvider HTTP/forex unit tests; asserts `APCA-API-KEY-ID`/secret headers + `/v1beta1/forex/latest/rates`) |
| `tests/unit/test_alpaca_provider_integration.py` | 116 | 1L | Delete |
| `tests/unit/test_alpaca_symbol_mapping.py` | 47 | 1L | Delete (symbol_mapper `"alpaca"` entries) |
| `tests/unit/test_alpaca_instrument_registry.py` | 38 | 1L | Delete (instrument_registry `"alpaca"` mappings) |
| `tests/unit/test_alpaca_provider_registry.py` | 24 | 1L | Delete (registry assertions incl. `assert "alpaca" not in provider_ids`) |
| `tests/unit/test_alpaca_configuration.py` | 26 | 2L | Rewrite → `test_fmp_configuration.py` |
| `tests/integration/test_alpaca_provider_integration.py` | 116 | 1L | Delete (end-to-end Alpaca tests) |
| `tests/integration/test_instrument_registry_startup.py` | 8 | 3 | Keep; remove Alpaca provider-coverage assertions |
| `tests/integration/test_runtime_instruments_api_endpoint.py` | 8 | 3 | Keep; remove Alpaca provider-coverage assertions |
| `scripts/test_fallback_logic.py` | 1 | 2L | Rewrite expected provider order |
| `backend/verify_alpaca_api.py` | 74 | K | Delete (standalone verifier; live authed call to Alpaca `/v1beta1/forex/latest/rates`) |
| `backend/verify_runtime.py` | 2 | 4 | Keep; replace `alpaca_provider`/AlpacaProvider import in smoke list |
| `backend/scripts/validate_phase1_runtime.py` | 2 | 4 | Keep; replace `alpaca_provider`/AlpacaProvider import in smoke list |

---

## 12. Signal Safety Dependencies

**Hidden dependency: NONE.** Alpaca is **not** referenced by any signal-safety-critical module. The framework is fully provider-agnostic:

| Component | Alpaca dependency? | Mechanism |
|-----------|--------------------|-----------|
| `MarketStateEngine` | **No** | Consumes `MarketQuote` via `ProviderManager` (provider-agnostic) |
| `QuoteValidator` | **No** | Validates symbol mapping, price, spread, timestamp, freshness — no `provider_id` dependency |
| `SignalGenerationEngine` | **No** | Operates on validated quotes, not provider identity |
| Decision / Risk / ExecutionReadiness engines | **No** | No `alpaca` matches in source |
| Freshness validation / safety gates | **No** | Gate is on price/timestamp/freshness — provider-agnostic |
| Provider fallback | **Indirect (registry order only)** | Alpaca occupies in-band priority slot (2) in the fallback chain |

**Verdict:** Removing Alpaca **cannot** affect signal safety for XAU/USD, GBP/USD, or EUR/USD, because (a) it is gated off by default (`ENABLE_ALPACA_PROVIDER=false`), and (b) no downstream logic keys off the `"alpaca"` provider ID. The **only** behavioral surface is the fallback priority slot, which FMP will inherit.

---

## 13. FMP Replacement Map

Target architecture: **Twelve Data → Alpha Vantage → FMP → Mock.** Each Alpaca item maps to a planned FMP counterpart (implementation scoped to Phase 8.2.1; **not** executed here):

| # | Current Alpaca item | Responsibility | Proposed FMP replacement | Abstraction FMP implements | Requires (verify) | Requires config | Requires tests |
|---|---------------------|----------------|--------------------------|----------------------------|-------------------|-----------------|----------------|
| 1 | `alpaca_provider.py` `AlpacaProvider` | LIVE_PRICE / SPREAD / MARKET_SESSION via `GET {base}/v1beta1/forex/latest/rates` | **`FmpProvider`** (`fmp_provider.py`) | `BaseProvider` (`provider_id="fmp"`, `provider_name="Financial Modeling Prep"`) | FMP endpoint + symbol + response→Falcon quote mapping | `settings.FMP_API_KEY` + `.env.example` | Rewrite of deleted `test_alpaca_provider_*` → `test_fmp_provider_*` (after endpoint+symbol verified) |
| 2 | `__init__.py` instantiation + register | `_alpaca_provider` `priority=2` gated on `ENABLE_ALPACA_PROVIDER` | `FmpProvider(api_key=settings.FMP_API_KEY)` at `priority=3`; AV stays `2`; Mock `4` | `provider_registry.register(...)` + priority renumbering | — | `FMP_API_KEY` (NAME only) | `test_fmp_provider_registry.py` |
| 3 | `symbol_mapper.py` `"alpaca"` block | Canonical→FMP ticker table | `"fmp"` block in `_PROVIDER_SYMBOL_MAP` | `SymbolMapper` (generic) | FMP symbol-per-instrument | — | `test_fmp_symbol_mapping.py` |
| 4 | `instrument_registry.py` `"alpaca"` keys | Per-instrument provider tickers + reverse lookups | `"fmp"` keys (drop `"alpaca"`) | `CanonicalInstrumentRegistry.register_instrument` (generic) | FMP symbol-per-instrument | — | `test_fmp_instrument_registry.py` |
| 5 | `settings.py` Alpaca env block (4 vars) | Env var loading | Replace with **1** FMP env var | existing `os.getenv(...)` pattern (identical) | — | `FMP_API_KEY` | `test_fmp_configuration.py` |

---

## 14. Market Coverage — XAU/USD (Spot Gold)

Alpaca's exact symbols for the **three primary** instruments were **not readable** in this audit — the `instrument_registry.py` forex `providerMappings` block (L242–260) and the `"alpaca"` block of `symbol_mapper.py` (L80–87) hit a tool "outdated" marker. The table below records the **verified** Twelve Data / Alpha Vantage symbols and the **required** FMP symbol (to be verified against FMP docs in Phase 8.2.1 — **not invented here** per the task rules). The authoritative intent is documented in `backend/.env.example`, which lists the instruments Falcon supports.

| Provider | Symbol | Source |
|----------|--------|--------|
| Twelve Data | `XAU/USD` | verified (symbol_mapper) |
| Alpha Vantage | `XAU` | verified (symbol_mapper) |
| Alpaca | **unread** (block at L242–246) | not readable; forex pair, slash-stripped at endpoint |
| **FMP (required, to verify)** | `XAUUSD` | reconstructed intent from `.env.example`; **verify** against FMP `/quote/XAUUSD` — FMP uses non-slash tickers, so the mapper must translate Falcon canonical `XAUUSD` → FMP `XAUUSD` and normalize the response back to Falcon's quote schema (bid/ask/mid/lastPrice/spread/timestamp/`providerId="fmp"`) |

- **FMP endpoint to verify:** `/quote/{symbol}` (real-time), e.g. `https://financialmodelingprep.com/api/v3/quote/XAUUSD?apikey={key}`.
- **BaseProvider support:** Yes — `FmpProvider` follows the existing quote-normalization + circuit-breaker pattern (`alpaca_provider.py` / `alpha_vantage_provider.py`).

---

## 15. Market Coverage — GBP/USD & EUR/USD

*(Same unreadable-block caveat as §14 applies; FMP symbols reconstructed from `.env.example` intent; **verify against FMP docs in Phase 8.2.1 — do not invent.**)*

### GBP/USD

| Provider | Symbol | Source |
|----------|--------|--------|
| Twelve Data | `GBP/USD` | verified (symbol_mapper) |
| Alpha Vantage | `GBP/USD` | verified (symbol_mapper) |
| Alpaca | **unread** | not readable |
| **FMP (required, to verify)** | `GBPUSD` | reconstructed intent; **verify** against FMP `/quote/GBPUSD` |

### EUR/USD

| Provider | Symbol | Source |
|----------|--------|--------|
| Twelve Data | `EUR/USD` | verified (symbol_mapper) |
| Alpha Vantage | `EUR/USD` | verified (symbol_mapper) |
| Alpaca | **unread** | not readable |
| **FMP (required, to verify)** | `EURUSD` | reconstructed intent; **verify** against FMP `/quote/EURUSD` |

> ⚠️ **FMP endpoint + symbol details must be confirmed from FMP docs in Phase 8.2.1.** This Phase-1 audit names only the *required* FMP symbol variable; it does **not** fabricate endpoint behaviour.

---

## 16. Files To Modify

**Phase 8.2 (removal) + FMP replacement:**

| File | Change |
|------|--------|
| `backend/app/core/config/settings.py` | remove Alpaca env block; add `self.FMP_API_KEY = os.getenv("FMP_API_KEY")` |
| `backend/.env.example` | remove 3 Alpaca lines (API key, secret, base url) + gate; add `FMP_API_KEY=` placeholder |
| `backend/app/core/providers/__init__.py` | drop `AlpacaProvider` import/instantiate/register; add `FmpProvider` priority=3; renumber AlphaVantage→2, Mock→4 |
| `backend/app/core/providers/symbol_mapper.py` | replace `"alpaca"` block → `"fmp"` block |
| `backend/app/core/instruments/instrument_registry.py` | drop `"alpaca"` keys in `providerMappings`; add `"fmp"` keys |
| `backend/scripts/test_fallback_logic.py` | update expected priority order (Alpaca→FMP) |
| `backend/verify_runtime.py` | replace `alpaca_provider`/AlpacaProvider import in provider smoke list |
| `backend/scripts/validate_phase1_runtime.py` | replace `alpaca_provider`/AlpacaProvider import in provider smoke list |
| `backend/tests/unit/test_alpaca_configuration.py` | rewrite → `test_fmp_configuration.py` |
| `backend/tests/integration/test_instrument_registry_startup.py` | remove Alpaca provider-coverage assertions |
| `backend/tests/integration/test_runtime_instruments_api_endpoint.py` | remove Alpaca provider-coverage assertions |

---

## 17. Files To Delete

| File | Reason |
|------|--------|
| `backend/app/core/providers/alpaca_provider.py` | `AlpacaProvider` impl — fully replaced by FMP |
| `backend/tests/unit/test_alpaca_provider_live.py` | Alpaca HTTP/forex unit tests |
| `backend/tests/unit/test_alpaca_provider_integration.py` | Alpaca integration tests |
| `backend/tests/unit/test_alpaca_symbol_mapping.py` | symbol_mapper `"alpaca"` entries |
| `backend/tests/unit/test_alpaca_instrument_registry.py` | instrument_registry `"alpaca"` mappings |
| `backend/tests/unit/test_alpaca_provider_registry.py` | Alpaca registry assertions |
| `backend/tests/integration/test_alpaca_provider_integration.py` | end-to-end Alpaca tests |
| `backend/verify_alpaca_api.py` | standalone Alpaca API credential verifier (74 refs) |

---

## 18. Files To Rewrite

| File | Rewrite target |
|------|----------------|
| `backend/tests/unit/test_alpaca_provider_live.py` (110) | → `test_fmp_provider_live.py` |
| `backend/tests/unit/test_alpaca_provider_integration.py` (116) | → `test_fmp_provider_integration.py` |
| `backend/tests/unit/test_alpaca_symbol_mapping.py` (47) | → `test_fmp_symbol_mapping.py` |
| `backend/tests/unit/test_alpaca_instrument_registry.py` (38) | → `test_fmp_instrument_registry.py` |
| `backend/tests/unit/test_alpaca_provider_registry.py` (24) | → `test_fmp_provider_registry.py` |
| `backend/tests/unit/test_alpaca_configuration.py` (26) | → `test_fmp_configuration.py` |
| `backend/tests/integration/test_alpaca_provider_integration.py` (116) | → `test_fmp_provider_integration.py` |
| `backend/scripts/test_fallback_logic.py` (1) | update expected order |
| `backend/verify_runtime.py`, `backend/scripts/validate_phase1_runtime.py` | update provider import list |

---

## 19. Files To Leave Untouched

- `backend/app/core/providers/provider_manager.py` — generic fallback (**NO change**)
- `backend/app/core/providers/provider_registry.py` — generic (**NO change**)
- `backend/app/core/providers/base_provider.py` — generic contract (**NO change**)
- `backend/app/core/providers/quote_validator.py` — provider-agnostic validation (**NO change**)
- `backend/app/core/providers/twelve_data_provider.py` — primary provider (**NO change**)
- `backend/app/core/providers/alpha_vantage_provider.py` — secondary provider (**NO change**)
- `backend/app/core/providers/mock_price_provider.py` — final fallback (**NO change**)
- `backend/app/core/providers/cache.py` — provider-agnostic cache (**NO change**)
- `backend/app/core/engines/*` — none reference Alpaca (**NO change**)
- `backend/app/services/*` — no Alpaca references (**NO change**)
- `backend/requirements.txt` — no alpaca package (**NO change**)
- `backend/.gitignore` — already ignores `.env` (**NO change**; `FMP_API_KEY` will be covered)

## 20. Migration Risks

1. **Fallback priority slot (HIGHEST).** Alpaca occupies `priority=2` between Twelve Data(1) and Alpha Vantage(2|3). FMP must take a slot; naïve deletion leaves Twelve Data failures falling through to Alpha Vantage only. The `if settings.ENABLE_ALPACA_PROVIDER` conditional branches in `__init__.py` must be converted to FMP registration, and AV/Mock priorities renumbered.
2. **Unreadable mappings (BLOCKER for Phase 1).** Exact Alpaca symbols for XAU/USD, GBP/USD, EUR/USD, USD/JPY in `instrument_registry.py` (L242–260) and the `"alpaca"` block in `symbol_mapper.py` (L80–87) were **not readable** (tool "outdated" marker). These must be re-read and the equivalents documented **before any code is written**. (Reconstruction here came only from `backend/.env.example`.)
3. **FMP symbols not invented (per rules).** FMP's exact ticker format + `/quote` endpoint response fields must be verified against FMP docs before implementing the replacement — this Phase-1 audit deliberately does **not** fabricate them.
4. **`verify_alpaca_api.py` is a live-credential script.** It makes a real authed call to Alpaca `/v1beta1/forex/latest/rates` using `settings.ALPACA_*`. Deletion is safe (post-migration) but it currently doubles as a credentials/config smoke check.
5. **Import-smoke scripts will break on deletion.** `verify_runtime.py` and `scripts/validate_phase1_runtime.py` import `AlpacaProvider` in their provider import lists → `ImportError` immediately on Alpaca removal. Must be updated in the same commit.
6. **Test count shift.** Deleting 6 dedicated Alpaca test files + rewriting others is significant test churn; care must be taken that no **non-Alpaca** assertions are lost in the kept files (`test_instrument_registry_startup.py`, `test_runtime_instruments_api_endpoint.py`).
7. **AlpacaProvider `connect()` not fully visible.** Its `_connected`/`connect()` implementation was in the unread middle of `alpaca_provider.py`; minor, but FMP will follow the Twelve Data / Alpha Vantage `connect()` pattern regardless.
8. **Caches/reports stale.** `.pytest_cache`, `gate_results*.json`, `code_health.json`, `alpaca_verification_report.json` will reference stale Alpaca test node IDs until regenerated; safe to purge, auto-regenerate.

---

## 21. Validation Requirements (Phase 8.2.1)

- **Re-read** the 4 blocked Alpaca mapping ranges; snapshot exact current symbols.
- Confirm **FMP contract** (endpoint `/quote/{symbol}`, ticker format, response→Falcon quote mapping) from FMP docs — **verify, do not invent** — for XAU/USD, GBP/USD, EUR/USD, USD/JPY, NAS100, US30, BTCUSD, ETHUSD.
- Verify FMP supports real-time quotes for the 3 primary instruments on the chosen endpoint.
- Unit-test `FmpProvider` fetch/validation/circuit-breaker against Falcon's quote schema **before** wiring into the registry.
- Assert the new priority order via `ProviderManager._fetch_from_providers()` simulation: `TwelveData → AlphaVantage → FMP → Mock` (disable Alpaca + disable FMP to exercise each fallback leg).
- Run `verify_runtime.py` / `validate_phase1_runtime.py` import smoke after the swap.
- Re-run the full test suite; confirm no signal-safety change for XAU/USD, GBP/USD, EUR/USD.

---

## 22. Recommended Phase 8.2.1 Implementation Plan

1. **Read** the 4 blocked Alpaca mapping ranges; snapshot exact current symbols.
2. **Research & lock the FMP contract** (endpoint, ticker format, response→Falcon quote mapping) for XAU/USD, GBP/USD, EUR/USD, USD/JPY, NAS100, US30, BTCUSD, ETHUSD — **verify, do not invent**.
3. **Implement** `FmpProvider(BaseProvider)` modeled on `alpaca_provider.py` / `alpha_vantage_provider.py`, using `requests` + `BaseProvider` circuit-breaker + `quote_validator`.
4. **Config:** add `settings.FMP_API_KEY`; add `FMP_API_KEY=` to `.env.example`.
5. **Wiring:** in `providers/__init__.py`, register `FmpProvider(priority=3)`, renumber `AlphaVantage→2`, `Mock→4`; gate FMP on a flag mirroring Alpaca's pattern (or hard-enable per prod posture).
6. **Mappings:** in `symbol_mapper.py` and `instrument_registry.py`, replace `"alpaca"` entries with `"fmp"` (correct FMP symbols); drop reverse-index `"alpaca"` keys.
7. **Delete** `alpaca_provider.py` + the 6 dedicated Alpaca test files + `verify_alpaca_api.py`.
8. **Rewrite** `test_alpaca_*` → `test_fmp_*`; update `test_fallback_logic.py`, `verify_runtime.py`, `validate_phase1_runtime.py`.
9. **Validate:** assert provider order + fallback legs via simulation; run full suite; re-validate signal safety for XAU/USD, GBP/USD, EUR/USD.
10. **Packages:** no `alpaca-*` packages exist — nothing to uninstall.

---

## Appendix A — Raw Scan Metadata

- Scan method: read-only substring + file-enumeration repository scan.
- Aggregate: `total_files: 47`, `total_matches: 3,563`.
- Environment variables surfaced (name occurrences): `ALPACA_API_KEY` (7), `ALPACA_SECRET_KEY` (6), `ALPACA_BASE_URL` (5), `ENABLE_ALPACA_PROVIDER` (4) — **secret values were never read or written**.
- Provider files flagged: `providers/__init__.py`, `providers/alpaca_provider.py`, `providers/symbol_mapper.py`.
- Production files flagged: `instruments/instrument_registry.py`, `providers/__init__.py`, `providers/alpaca_provider.py`, `providers/symbol_mapper.py`.
- Test files flagged: `scripts/test_fallback_logic.py`, `tests/integration/test_alpaca_provider_integration.py`, `tests/integration/test_instrument_registry_startup.py`, `tests/integration/test_runtime_instruments_api_endpoint.py`, `tests/unit/test_alpaca_configuration.py`, `tests/unit/test_alpaca_instrument_registry.py`, `tests/unit/test_alpaca_provider_live.py`, `tests/unit/test_alpaca_provider_registry.py`, `tests/unit/test_alpaca_symbol_mapping.py`.
- Config files flagged: `backend/.env.example`, `backend/app/core/config/settings.py`.
