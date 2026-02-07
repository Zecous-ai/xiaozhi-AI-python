from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("email_utils")


def send_captcha_email(email: str, code: str) -> bool:
    if not settings.email_host or not settings.email_user or not settings.email_password:
        logger.error("邮件配置缺失")
        return False
    sender = settings.email_from or settings.email_user
    try:
        msg = MIMEText(f"您的验证码是：{code}，10分钟内有效。", "plain", "utf-8")
        msg["Subject"] = "验证码"
        msg["From"] = sender
        msg["To"] = email

        with smtplib.SMTP_SSL(settings.email_host, settings.email_port) as server:
            server.login(settings.email_user, settings.email_password)
            server.sendmail(sender, [email], msg.as_string())
        return True
    except Exception:
        logger.exception("发送邮件失败")
        return False


__all__ = ["send_captcha_email"]
