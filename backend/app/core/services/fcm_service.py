import os
import json
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("falcon.fcm_service")

_firebase_initialized = False

def get_firebase_credentials() -> Optional[Dict[str, Any]]:
    # 1. From env var FIREBASE_SERVICE_ACCOUNT_JSON
    creds_json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if creds_json_str:
        try:
            return json.loads(creds_json_str)
        except Exception as e:
            logger.error(f"[FCM] Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON env: {e}")

    # 2. From file path in env var FIREBASE_SERVICE_ACCOUNT_PATH
    path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[FCM] Failed to read FIREBASE_SERVICE_ACCOUNT_PATH: {e}")

    # 3. From default backend/data/firebase_service_account.json
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    default_path = os.path.join(base_dir, "data", "firebase_service_account.json")
    if os.path.isfile(default_path):
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[FCM] Failed to read default service account file: {e}")

    return None

def initialize_firebase() -> bool:
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized by another module
        if firebase_admin._apps:
            _firebase_initialized = True
            return True

        creds_dict = get_firebase_credentials()
        if not creds_dict:
            logger.warning("[FCM] No Firebase credentials found. Remote push notifications will be inactive.")
            return False

        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("[FCM] Firebase Admin SDK initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"[FCM] Failed to initialize Firebase Admin SDK: {e}")
        return False

class FCMService:
    FALCON_SIGNALS_TOPIC = "falcon_signals"

    def __init__(self) -> None:
        self._ready = initialize_firebase()
        self._dedup_cache: Dict[str, float] = {}

    def send_signal_alert(
        self,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        topic: str = FALCON_SIGNALS_TOPIC,
    ) -> bool:
        """
        Dispatches a high-priority push notification to topic subscribers via Firebase Cloud Messaging.
        Enforces 4-hour deduplication to prevent duplicate alerts.
        """
        if not self._ready:
            self._ready = initialize_firebase()
            if not self._ready:
                logger.warning("[FCM] Skipping alert dispatch: Firebase not initialized.")
                return False

        # Strict canonical setup deduplication (prevents re-alerting across mission refreshes)
        d = data or {}
        canonical_key = str(
            d.get("canonical_signature")
            or (f"{d.get('symbol')}_{d.get('direction')}_{float(d.get('entry', 0)):.2f}" if d.get('symbol') and d.get('direction') and d.get('entry') else "")
            or d.get("signal_id", "")
            or d.get("trade_id", "")
            or title
        )
        is_test = str(d.get("is_test", "false")).lower() == "true"
        now = time.time()

        if not is_test and canonical_key:
            last_sent = self._dedup_cache.get(canonical_key, 0)
            if (now - last_sent) < 86400:  # 24-hour cooldown per unique trade setup
                logger.info(f"[FCM] Suppressing duplicate push alert for setup: {canonical_key}")
                return True
            self._dedup_cache[canonical_key] = now

        try:
            from firebase_admin import messaging

            string_data = {str(k): str(v) for k, v in (data or {}).items()}

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=string_data,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id="falcon_signals",
                        sound="default",
                        priority="high",
                        default_vibrate_timings=True,
                    ),
                ),
                topic=topic,
            )

            response = messaging.send(message)
            logger.info(f"[FCM] Successfully sent push notification to topic '{topic}': {response}")
            return True
        except Exception as e:
            logger.error(f"[FCM] Error sending push notification: {e}")
            return False

fcm_service = FCMService()
