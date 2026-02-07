from __future__ import annotations

import hashlib
import os
import uuid
from typing import Optional

from fastapi import UploadFile

from app.core.config import settings

try:
    from qcloud_cos import CosConfig, CosS3Client
except Exception:  # pragma: no cover
    CosConfig = None
    CosS3Client = None


MAX_SIZE = 50 * 1024 * 1024


def assert_allowed(file: UploadFile) -> None:
    size = None
    try:
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
    except Exception:
        size = None
    if size is not None and size > MAX_SIZE:
        raise ValueError(f"文件大小超过限制，最大允许：{MAX_SIZE // 1024 // 1024}MB")


def calculate_sha256(file: UploadFile) -> str:
    file.file.seek(0)
    hasher = hashlib.sha256()
    for chunk in iter(lambda: file.file.read(8192), b""):
        hasher.update(chunk)
    file.file.seek(0)
    return hasher.hexdigest()


def _save_local(base_dir: str, relative_path: str, file_name: str, file: UploadFile) -> str:
    assert_allowed(file)
    directory = os.path.join(base_dir, relative_path)
    os.makedirs(directory, exist_ok=True)
    dest_path = os.path.join(directory, file_name)
    with open(dest_path, "wb") as out:
        while True:
            chunk = file.file.read(8192)
            if not chunk:
                break
            out.write(chunk)
    rel_path = os.path.join(base_dir, relative_path, file_name)
    return rel_path.replace("\\", "/")


def _upload_cos(file: UploadFile, cos_path: str) -> Optional[str]:
    if CosConfig is None or CosS3Client is None:
        return None
    if not settings.tencent_cos_secret_id or not settings.tencent_cos_secret_key:
        return None
    if not settings.tencent_cos_region or not settings.tencent_cos_bucket_name:
        return None

    config = CosConfig(
        Region=settings.tencent_cos_region,
        SecretId=settings.tencent_cos_secret_id,
        SecretKey=settings.tencent_cos_secret_key,
        Token=None,
        Scheme="https",
    )
    client = CosS3Client(config)

    original_name = file.filename or "file"
    suffix = os.path.splitext(original_name)[1]
    file_name = f"{uuid.uuid4().hex}{suffix}"
    key = f"{cos_path}{file_name}"

    file.file.seek(0)
    response = client.put_object(
        Bucket=settings.tencent_cos_bucket_name,
        Body=file.file,
        Key=key,
    )
    if response is None:
        return None
    return f"https://{settings.tencent_cos_bucket_name}.cos.{settings.tencent_cos_region}.myqcloud.com/{key}"


def smart_upload(base_dir: str, relative_path: str, file_name: str, file: UploadFile) -> str:
    cos_path = settings.tencent_cos_path_prefix
    if cos_path and not cos_path.endswith("/"):
        cos_path = cos_path + "/"
    cos_key_prefix = f"{cos_path}{relative_path}/" if cos_path else f"{relative_path}/"

    # 仅在配置完整时上传到 COS
    cos_url = _upload_cos(file, cos_key_prefix)
    if cos_url:
        return cos_url
    return _save_local(base_dir, relative_path, file_name, file)


__all__ = ["smart_upload", "calculate_sha256"]
