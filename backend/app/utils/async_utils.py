from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine


def run_coroutine_sync(coro: Coroutine[Any, Any, Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result["value"] = loop.run_until_complete(coro)
        except BaseException as exc:  # pragma: no cover - 需要抛出原异常
            error["exc"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error["exc"]
    return result.get("value")


def schedule_coro(coro: Coroutine[Any, Any, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)


__all__ = ["run_coroutine_sync", "schedule_coro"]
