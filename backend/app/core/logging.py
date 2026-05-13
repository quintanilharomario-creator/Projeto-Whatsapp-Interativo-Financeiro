"""
Sistema de logging estruturado da aplicação.

Uso em qualquer arquivo:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("user_created", user_id=42)
"""

import logging
import sys

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """
    Configura o sistema de logging da aplicação.
    Chamado UMA vez na inicialização do main.py.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_development:
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        processors = shared_processors + [structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Retorna um logger configurado para o módulo informado.

    Uso:
        logger = get_logger(__name__)
        logger.info("evento", chave="valor")
        logger.error("erro", exc_info=True)
    """
    return structlog.get_logger(name)
