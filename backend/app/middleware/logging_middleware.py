import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log the incoming request
        logger.info(f"Incoming request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log the response status and timing
            logger.info(f"Completed response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
            
            return response
        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(f"Unhandled exception during {request.method} {request.url.path} - Time: {process_time:.4f}s", exc_info=exc)
            raise
