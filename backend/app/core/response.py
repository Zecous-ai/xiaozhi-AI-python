from __future__ import annotations

from typing import Any


class ResultStatus:
    SUCCESS = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    MOVED_PERM = 301
    SEE_OTHER = 303
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    BAD_METHOD = 405
    CONFLICT = 409
    UNSUPPORTED_TYPE = 415
    ERROR = 500
    NOT_IMPLEMENTED = 501


class ResultMessage(dict):
    CODE_TAG = "code"
    MSG_TAG = "message"
    DATA_TAG = "data"

    def __init__(self, code: int, message: str, data: Any | None = None):
        super().__init__()
        self[self.CODE_TAG] = code
        self[self.MSG_TAG] = message
        if data is not None:
            self[self.DATA_TAG] = data

    @staticmethod
    def success(message: str = "操作成功", data: Any | None = None) -> "ResultMessage":
        return ResultMessage(ResultStatus.SUCCESS, message, data)

    @staticmethod
    def error(message: str = "操作失败", data: Any | None = None, code: int = ResultStatus.ERROR) -> "ResultMessage":
        return ResultMessage(code, message, data)


__all__ = ["ResultMessage", "ResultStatus"]
