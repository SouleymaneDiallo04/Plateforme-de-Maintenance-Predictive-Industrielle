"""Notifications email (SMTP)."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["Notifications"])


class AlertNotification(BaseModel):
    machine_id   : str
    alert_type   : str
    message      : str
    health_index : float
    recipient    : str


def _smtp_config() -> dict:
    """Configuration SMTP depuis le .env (noms alignés : SMTP_*)."""
    return {
        "server"  : os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "port"    : int(os.getenv("SMTP_PORT", "587") or 587),
        "sender"  : os.getenv("SMTP_SENDER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
    }


def send_email(to: str, subject: str, body: str) -> None:
    """Envoie un email HTML via SMTP. Lève une exception en cas d'échec."""
    cfg = _smtp_config()
    if not cfg["sender"] or not cfg["password"]:
        raise RuntimeError(
            "SMTP non configuré — définir SMTP_SENDER et SMTP_PASSWORD dans .env"
        )

    msg            = MIMEMultipart()
    msg["From"]    = cfg["sender"]
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP(cfg["server"], cfg["port"], timeout=15) as server:
        server.starttls()
        server.login(cfg["sender"], cfg["password"])
        server.send_message(msg)


def _alert_body(alert: AlertNotification) -> str:
    return f"""
    <h2>⚠️ Alerte Maintenance Prédictive</h2>
    <table>
      <tr><td><b>Machine</b></td><td>{alert.machine_id}</td></tr>
      <tr><td><b>Type d'alerte</b></td><td>{alert.alert_type}</td></tr>
      <tr><td><b>Message</b></td><td>{alert.message}</td></tr>
      <tr><td><b>Health Index</b></td><td>{alert.health_index}%</td></tr>
    </table>
    <p>Connectez-vous à PrognoSense pour plus de détails.</p>
    """


@router.post("/notifications/alert")
def send_alert_notification(alert: AlertNotification,
                            background_tasks: BackgroundTasks):
    """Notification email d'alerte (envoi asynchrone, non bloquant)."""
    subject = f"[PrognoSense] Alerte {alert.alert_type} — {alert.machine_id}"
    background_tasks.add_task(send_email, alert.recipient, subject, _alert_body(alert))
    return {"message": f"Notification programmée pour {alert.recipient}"}


@router.post("/notifications/test")
def test_notification(recipient: str):
    """
    Envoi SYNCHRONE d'un email de test → renvoie le vrai résultat
    (succès/échec), contrairement à un envoi en tâche de fond.
    """
    try:
        send_email(
            recipient,
            "[PrognoSense] Email de test",
            "<h3>✅ Test PrognoSense</h3>"
            "<p>La configuration SMTP fonctionne correctement.</p>",
        )
        return {"success": True, "message": f"Email de test envoyé à {recipient}"}
    except Exception as e:
        raise HTTPException(500, f"Échec de l'envoi : {e}")


@router.get("/notifications/config")
def notifications_config():
    """Diagnostic : état de la configuration SMTP (sans exposer le secret)."""
    cfg = _smtp_config()
    return {
        "smtp_server"        : cfg["server"],
        "smtp_port"          : cfg["port"],
        "sender_configured"  : bool(cfg["sender"]),
        "password_configured": bool(cfg["password"]),
        "sender_masked"      : (cfg["sender"][:3] + "***@" + cfg["sender"].split("@")[-1])
                               if "@" in cfg["sender"] else None,
        "ready"              : bool(cfg["sender"] and cfg["password"]),
    }
