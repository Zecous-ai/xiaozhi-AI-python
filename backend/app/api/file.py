from __future__ import annotations

import datetime
import os
import uuid

from fastapi import APIRouter, File, UploadFile

from app.core.response import ResultMessage
from app.utils.cms_utils import get_server_address
from app.utils.file_upload import calculate_sha256, smart_upload


router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), type: str = "common"):
    date_path = datetime.datetime.now().strftime("%Y/%m/%d")
    relative_path = f"{type}/{date_path}"
    original_filename = file.filename or "file"
    _, ext = os.path.splitext(original_filename)
    file_name = f"{uuid.uuid4().hex}{ext}"
    try:
        file_path_or_url = smart_upload("uploads", relative_path, file_name, file)
        file_hash = calculate_sha256(file)
        result = ResultMessage.success("上传成功")
        result["fileName"] = original_filename
        result["newFileName"] = file_name
        result["hash"] = file_hash
        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            result["url"] = file_path_or_url
        else:
            result["relativePath"] = file_path_or_url
            result["url"] = f"{get_server_address()}/{file_path_or_url}"
        return result
    except Exception as exc:
        return ResultMessage.error(f"文件上传失败: {exc}")

