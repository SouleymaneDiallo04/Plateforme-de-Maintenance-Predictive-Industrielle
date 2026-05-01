"""Notifications email."""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

router = APIRouter(tags=["Notifications"])


class EmailConfig(BaseModel):
    recipient  : str
    smtp_server: str = "smtp.gmail.com"
    smtp_port  : int = 587
    sender     : str = ""
    password   : str = ""


class AlertNotification(BaseModel):
    machine_id   : str
    alert_type   : str
    message      : str
    health_index : float
    recipient    : str


def send_email(to: str, subject: str, body: str,
               cfg: EmailConfig):
    """Envoie un email d'alerte."""
    msg            = MIMEMultipart()
    msg['From']    = cfg.sender or os.getenv("EMAIL_SENDER", "")
    msg['To']      = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    password = cfg.password or os.getenv("EMAIL_PASSWORD", "")

    with smtplib.SMTP(cfg.smtp_server, cfg.smtp_port) as server:
        server.starttls()
        server.login(msg['From'], password)
        server.send_message(msg)


@router.post("/notifications/alert")
def send_alert_notification(alert: AlertNotification,
                              background_tasks: BackgroundTasks):
    """Envoie une notification email lors d'une alerte critique."""
    subject = f"[PrognoSense] Alerte {alert.alert_type} — {alert.machine_id}"
    body    = f"""
    <h2>⚠️ Alerte Maintenance Prédictive</h2>
    <table>
      <tr><td><b>Machine</b></td><td>{alert.machine_id}</td></tr>
      <tr><td><b>Type d'alerte</b></td><td>{alert.alert_type}</td></tr>
      <tr><td><b>Message</b></td><td>{alert.message}</td></tr>
      <tr><td><b>Health Index</b></td><td>{alert.health_index}%</td></tr>
    </table>
    <p>Connectez-vous à PrognoSense pour plus de détails.</p>
    """

    cfg = EmailConfig(recipient=alert.recipient)
    background_tasks.add_task(
        send_email, alert.recipient, subject, body, cfg
    )

    return {"message": f"Notification envoyée à {alert.recipient}"}


@router.post("/notifications/test")
def test_notification(recipient: str,
                       background_tasks: BackgroundTasks):
    """Envoie un email de test."""
    alert = AlertNotification(
        machine_id  = "TEST",
        alert_type  = "test",
        message     = "Email de test PrognoSense",
        health_index= 85.0,
        recipient   = recipient
    )
    return send_alert_notification(alert, background_tasks)