import sys
sys.path.insert(0, ".")
from app.core.config import settings
from app.core.providers.fmp_provider import FmpProvider

print("Settings FMP_BASE_URL:", settings.FMP_BASE_URL)
fmp = FmpProvider()
print("FMP provider _base_url:", fmp._base_url)
