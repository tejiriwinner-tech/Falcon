from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.core.providers import provider_registry, provider_manager
from app.schemas.provider_models import (
    ProviderListResponse,
    ProviderSnapshot,
    MarketDataSnapshot,
)

router = APIRouter(tags=["providers"])


# ------------------------------------------------------------------
# Provider endpoints
# ------------------------------------------------------------------

@router.get("/providers", response_model=ProviderListResponse)
def get_providers():
    """Return all registered providers with health and statistics."""
    provider_registry.heartbeat()
    return ProviderListResponse(
        providers=provider_registry.get_all_snapshots(),
        summary=provider_registry.get_summary(),
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/providers/health")
def get_provider_health():
    """Return a lightweight health summary of all providers."""
    provider_registry.heartbeat()
    snapshots = provider_registry.get_all_snapshots()
    return {
        "providers": [
            {
                "providerId": s.providerId,
                "name": s.metadata.providerName,
                "status": s.metadata.status.value,
                "health": s.metadata.health.value,
            }
            for s in snapshots
        ],
        "summary": provider_registry.get_summary().model_dump(),
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/providers/capabilities")
def get_provider_capabilities():
    """Return all capabilities currently supported by registered providers."""
    all_caps = set()
    for provider in provider_registry.all_providers():
        meta = provider.get_metadata()
        for cap in meta.capabilities:
            all_caps.add(cap.value)

    return {
        "capabilities": sorted(all_caps),
        "providerCount": len(provider_registry.all_providers()),
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/providers/{provider_id}", response_model=ProviderSnapshot)
def get_provider_by_id(provider_id: str):
    """Return a single provider's full snapshot."""
    snapshot = provider_registry.get_snapshot(provider_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    return snapshot


# ------------------------------------------------------------------
# Market data endpoints
# ------------------------------------------------------------------

@router.get("/market-data/{symbol:path}", response_model=MarketDataSnapshot)
def get_market_data(symbol: str):
    """Return a normalized market snapshot for a symbol or alias."""
    snapshot = provider_manager.get_market_data(symbol)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' is not supported or no provider is available",
        )
    return snapshot
