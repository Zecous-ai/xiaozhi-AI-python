from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass

from app.utils.email_utils import send_captcha_email
from app.utils.sms_utils import send_verification_sms

logger = logging.getLogger("captcha_utils")


@dataclass
class CaptchaResult:
    success: bool
    message: str

    @staticmethod
    def ok() -> "CaptchaResult":
        return CaptchaResult(True, "发送成功")

    @staticmethod
    def error(message: str) -> "CaptchaResult":
        return CaptchaResult(False, message)


def generate_code(length: int = 6) -> str:
    return "".join(random.choice("0123456789") for _ in range(length))


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email or ""))


def is_valid_phone(phone: str) -> bool:
    return bool(re.match(r"^1\d{10}$", phone or ""))


def send_email_captcha(email: str, code: str) -> CaptchaResult:
    if not is_valid_email(email):
        return CaptchaResult.error("邮箱格式不正确")
    ok = send_captcha_email(email, code)
    return CaptchaResult.ok() if ok else CaptchaResult.error("邮件发送失败，请检查邮箱配置")


def send_sms_captcha(phone: str, code: str) -> CaptchaResult:
    if not is_valid_phone(phone):
        return CaptchaResult.error("手机号格式不正确")
    ok = send_verification_sms(phone, code)
    return CaptchaResult.ok() if ok else CaptchaResult.error("短信发送失败，请检查短信配置")


__all__ = ["generate_code", "send_email_captcha", "send_sms_captcha", "CaptchaResult"]
