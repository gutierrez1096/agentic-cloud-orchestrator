import logging
import sys
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name: str = "agent_orchestrator"):
    """
    Configura y devuelve un logger básico.
    Configura el ROOT logger para que todos los módulos (src.*, app.py) escriban en consola.
    """
    # Configurar el logger RAÍZ para capturar logs de todas partes (incluyendo src.agents.*)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Evitar duplicar handlers si ya existen en el logger raíz
    if root_logger.handlers:
        return logging.getLogger(name)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    file_handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return logging.getLogger(name)
