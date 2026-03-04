from __future__ import annotations
from typing import Any, Optional
import httpx
from app.core.config import settings

def notify_slack(text: str, *, extra: Optional[dict[str, Any]] = None) -> None:
    """
    Envía un mensaje simple a Slack usando Incoming Webhook.
    Si no hay SLACK_WEBHOOK_URL o algo falla, se ignora silenciosamente.
    """
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        return
    payload = {"text": text}
    if extra:
        # Adjunta “datos técnicos” legibles
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "divider"},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*{k}:*\n`{v}`"} for k, v in extra.items()
            ]},
        ]
        payload = {"blocks": blocks}
    try:
        httpx.post(url, json=payload, timeout=5.0)
    except Exception:
        # no interrumpir el job por falla de notificación
        pass

def notify(subject: str, text: str, *, severity: str = "INFO", payload: dict | None = None) -> None:
    """
    Wrapper genérico de notificaciones. Por ahora usa Slack.
    A futuro puedes añadir SMTP aquí sin tocar el resto del código.
    """
    line = f"*{severity}* – {subject}\n{text}"
    # Reutilizamos tu notify_slack actual
    notify_slack(line, extra=payload)

