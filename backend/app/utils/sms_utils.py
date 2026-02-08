from __future__ import annotations

import json
import logging

from app.core.config import settings

logger = logging.getLogger("sms_utils")


def _is_config_ready() -> bool:
    return bool(
        settings.sms_aliyun_access_key_id
        and settings.sms_aliyun_access_key_secret
        and settings.sms_aliyun_sign_name
        and settings.sms_aliyun_template_code
    )


def send_verification_sms(phone: str, code: str) -> bool:
    if not _is_config_ready():
        logger.error("SMS config missing")
        return False

    try:
        from alibabacloud_dysmsapi20170525 import models as dysms_models
        from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models
    except Exception as exc:
        logger.error("SMS SDK unavailable: %s", exc)
        return False

    try:
        config = open_api_models.Config(
            access_key_id=settings.sms_aliyun_access_key_id,
            access_key_secret=settings.sms_aliyun_access_key_secret,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = DysmsClient(config)

        request = dysms_models.SendSmsRequest(
            sign_name=settings.sms_aliyun_sign_name,
            template_code=settings.sms_aliyun_template_code,
            phone_numbers=phone,
            template_param=json.dumps({"code": code}, ensure_ascii=False),
        )
        runtime = util_models.RuntimeOptions()
        response = client.send_sms_with_options(request, runtime)

        resp_code = (response.body.code or "").upper()
        if resp_code == "OK":
            logger.info("SMS sent successfully to %s", phone)
            return True

        logger.error("SMS send failed: code=%s, message=%s", response.body.code, response.body.message)
        return False
    except Exception as exc:
        logger.error("SMS send error: %s", exc)
        return False


__all__ = ["send_verification_sms"]
