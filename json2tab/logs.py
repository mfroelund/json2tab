"""Logger for json2tab."""

import logging

logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)
formatter = logging.Formatter(
    "{levelname} - {message}",
    style="{",
)
console_handler.setFormatter(formatter)
