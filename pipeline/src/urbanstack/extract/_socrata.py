"""Shared Socrata API pagination helper.

Used by FHWA and NTD extractors to deduplicate the while/offset/limit loop.
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)


def fetch_socrata_pages(
    base_url: str,
    params: dict[str, str],
    *,
    page_size: int = 50_000,
    max_pages: int = 100,
    delay: float = 0.5,
) -> list[dict]:
    """Fetch all pages from a Socrata API endpoint.

    Handles pagination via $limit/$offset. Stops when a page returns
    fewer rows than page_size or max_pages is reached.
    """
    all_rows: list[dict] = []
    offset = 0

    for _ in range(max_pages):
        page_params = {**params, "$limit": str(page_size), "$offset": str(offset)}

        resp = requests.get(base_url, params=page_params, timeout=60)
        resp.raise_for_status()
        page = resp.json()

        if not page:
            break

        all_rows.extend(page)
        logger.info(
            "Socrata %s: fetched %d rows (offset %d)",
            base_url.split("/")[-1][:8],
            len(page),
            offset,
        )

        if len(page) < page_size:
            break
        offset += page_size

        if offset > 0:
            time.sleep(delay)

    return all_rows
