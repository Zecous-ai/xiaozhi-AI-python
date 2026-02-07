from __future__ import annotations

from math import ceil
from typing import Any, Dict, List


def build_page(items: List[Any], total: int, page_num: int, page_size: int, navigate_pages: int = 8) -> Dict[str, Any]:
    page_num = page_num if page_num > 0 else 1
    page_size = page_size if page_size > 0 else 10
    pages = ceil(total / page_size) if page_size else 0

    size = len(items)
    if total == 0 or size == 0:
        start_row = 0
        end_row = 0
    else:
        start_row = (page_num - 1) * page_size + 1
        end_row = start_row + size - 1

    pre_page = page_num - 1 if page_num > 1 else 0
    next_page = page_num + 1 if page_num < pages else 0

    is_first = page_num == 1
    is_last = page_num >= pages if pages > 0 else True

    has_prev = page_num > 1
    has_next = page_num < pages

    # 计算导航页码
    if pages <= navigate_pages:
        navigate_nums = list(range(1, pages + 1))
    else:
        half = navigate_pages // 2
        start = page_num - half
        end = page_num + half
        if navigate_pages % 2 == 0:
            end -= 1
        if start < 1:
            start = 1
            end = navigate_pages
        if end > pages:
            end = pages
            start = pages - navigate_pages + 1
        navigate_nums = list(range(start, end + 1))

    return {
        "list": items,
        "total": total,
        "pageNum": page_num,
        "pageSize": page_size,
        "size": size,
        "startRow": start_row,
        "endRow": end_row,
        "pages": pages,
        "prePage": pre_page,
        "nextPage": next_page,
        "isFirstPage": is_first,
        "isLastPage": is_last,
        "hasPreviousPage": has_prev,
        "hasNextPage": has_next,
        "navigatePages": navigate_pages,
        "navigatepageNums": navigate_nums,
        "navigateFirstPage": navigate_nums[0] if navigate_nums else 0,
        "navigateLastPage": navigate_nums[-1] if navigate_nums else 0,
    }


__all__ = ["build_page"]
