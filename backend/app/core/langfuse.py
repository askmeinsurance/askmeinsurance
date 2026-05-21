import logging

from langfuse import Langfuse

from app.core.config import get_settings

logger = logging.getLogger("askmeinsurance.langfuse")


def init_langfuse() -> bool:
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse not configured — tracing disabled")
        return False
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    logger.info("Langfuse initialized host=%s", settings.langfuse_host or "cloud.langfuse.com")
    return True
