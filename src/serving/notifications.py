"""
Notification system for alerts and updates
"""

import logging
import json
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


async def dispatch_notification(
    template_id: str,
    channels: List[str],
    payload: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Send notifications through configured channels

    Args:
        template_id: Notification template ID
        channels: List of channels (email, slack, teams, webhook)
        payload: Data to populate template

    Returns:
        Dispatch status
    """
    try:
        payload = payload or {}

        # Get template
        template = get_notification_template(template_id)

        # Render message
        message = render_template(template, payload)

        # Send to each channel
        results = []
        for channel in channels:
            result = await send_to_channel(channel, message)
            results.append({
                "channel": channel,
                "status": result.get("status", "sent"),
                "timestamp": datetime.now().isoformat()
            })

        return {
            "template_id": template_id,
            "channels": channels,
            "results": results,
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Error dispatching notification: {e}", exc_info=True)
        return {
            "error": str(e),
            "template_id": template_id,
            "status": "failed"
        }


async def send_to_channel(channel: str, message: Dict[str, Any]) -> Dict[str, Any]:
    """Send message to specific channel"""

    if channel == "email":
        logger.info(f"[EMAIL] {message.get('subject')}: {message.get('body')}")
        return {"status": "sent", "channel": "email"}

    elif channel == "slack":
        logger.info(f"[SLACK] {message.get('text')}")
        return {"status": "sent", "channel": "slack"}

    elif channel == "teams":
        logger.info(f"[TEAMS] {message.get('title')}: {message.get('text')}")
        return {"status": "sent", "channel": "teams"}

    elif channel == "webhook":
        logger.info(f"[WEBHOOK] {json.dumps(message)}")
        return {"status": "sent", "channel": "webhook"}

    elif channel == "console":
        print(f"\n{'='*60}")
        print(f"NOTIFICATION: {message.get('title', 'Alert')}")
        print(f"{'='*60}")
        print(message.get('body', message.get('text', '')))
        print(f"{'='*60}\n")
        return {"status": "sent", "channel": "console"}

    else:
        logger.warning(f"Unknown channel: {channel}")
        return {"status": "failed", "channel": channel, "error": "Unknown channel"}


def get_notification_template(template_id: str) -> Dict[str, str]:
    """Get notification template"""

    templates = {
        "model_trained": {
            "subject": "Model Training Complete",
            "title": "🎯 Model Training Complete",
            "body": "Model {model_id} has completed training.\n\nMetrics:\n{metrics}"
        },
        "backtest_complete": {
            "subject": "Backtest Results Ready",
            "title": "📊 Backtest Complete",
            "body": "Backtest for {model_id} finished.\n\nSharpe Ratio: {sharpe}\nMax Drawdown: {max_drawdown}"
        },
        "prediction_ready": {
            "subject": "Daily Predictions Available",
            "title": "🔮 Predictions Ready",
            "body": "Today's predictions from {model_id}:\n\nTop Signals:\n{top_signals}"
        },
        "experiment_complete": {
            "subject": "Experiment Finished",
            "title": "🧪 Experiment Complete",
            "body": "Experiment {run_id} has finished.\n\nRecipe: {recipe}\nStatus: {status}"
        },
        "error_alert": {
            "subject": "Error Alert",
            "title": "⚠️ Error Alert",
            "body": "An error occurred: {error}\n\nComponent: {component}\nTimestamp: {timestamp}"
        }
    }

    return templates.get(template_id, {
        "subject": "Notification",
        "title": "Notification",
        "body": "{message}"
    })


def render_template(template: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, str]:
    """Render template with payload data"""

    rendered = {}
    for key, value in template.items():
        try:
            rendered[key] = value.format(**payload)
        except KeyError:
            # If placeholder not in payload, leave as is
            rendered[key] = value

    return rendered
