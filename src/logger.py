import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

def _get_log_level():
    """Obtiene el nivel de logging desde LOG_LEVEL. Por defecto INFO."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    return level_mapping.get(log_level_str, logging.INFO)

def setup_logger(name: str = "agent_orchestrator"):
    """
    Configura y devuelve un logger básico.
    El nivel de logging se lee de la variable de entorno LOG_LEVEL (por defecto INFO).
    """
    log_level = _get_log_level()
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if root_logger.handlers:
        return logging.getLogger(name)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return logging.getLogger(name)
