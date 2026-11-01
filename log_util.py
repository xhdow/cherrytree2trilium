"""
Shared logging helper for the cherrytree-to-Trilium tools.

All modules log through this helper so the output format stays consistent.
Log records go to stderr, which keeps stdout clean for real program output
(for example JSON printed by a command).
"""

import logging
import sys

#: Format used by every tool: level, then message.
LOG_FORMAT = "%(levelname)-7s %(message)s"


def get_logger(name):
    '''
    Return a logger for the given module name.

    The basic configuration is applied only once per process. When
    ``main.py`` configures logging first, that configuration is reused.

    Args:
        name (str): Logger name, usually the module name.

    Returns:
        logging.Logger: The configured logger.
    '''
    logger = logging.getLogger(name)
    if not logger.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    return logger
