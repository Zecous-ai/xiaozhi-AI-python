from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("sms_utils")


def send_verification_sms(phone: str, code: str) -> bool:
    if not settings.sms_aliyun_access_key_id or not settings.sms_aliyun_access_key_secret:
        logger.error("短信配置缺失")
        return False
    # TODO: 完整对接阿里云短信服务
    logger.warning("短信发送未实现，已跳过")
    return False


__all__ = ["send_verification_sms"]
