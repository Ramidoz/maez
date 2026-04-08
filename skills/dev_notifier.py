"""
dev_notifier.py — Sends operational notifications to Maez Dev bot.
Keeps Maez private bot clean for conversation only.
"""
import os
import requests
import logging

logger = logging.getLogger("maez")


def send_dev(text: str):
    """Send a message to the Maez Dev Telegram bot."""
    token = os.getenv('MAEZ_DEV_TOKEN')
    user_id = os.getenv('MAEZ_TELEGRAM_USER_ID')
    if not token or not user_id:
        logger.warning("MAEZ_DEV_TOKEN not set — dev notification dropped")
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': user_id, 'text': text},
            timeout=10,
        )
    except Exception as e:
        logger.error("Dev notification failed: %s", e)
