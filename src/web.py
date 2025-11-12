import logging
import re
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup


URL_PATTERN = re.compile(r"https?://\S+")
logger = logging.getLogger("ghostwriter.web")


def pick_url(text: str) -> Optional[str]:
    match = URL_PATTERN.search(text)
    if match:
        return match.group(0)
    return None


async def fetch_page_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    text_parts = [segment.strip() for segment in soup.get_text(separator=" ").splitlines()]
    filtered = [segment for segment in text_parts if segment]
    return " ".join(filtered)[:4000]


async def fetch_theme_samples(channel_slug: str, hashtag: str, limit: int = 5, max_pages: int = 4) -> List[str]:
    base_url = f"https://t.me/s/{channel_slug}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        )
    }
    hashtag_lower = hashtag.lower().strip()
    samples: List[str] = []
    seen: set[str] = set()
    before: Optional[str] = None

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            params = {"embed": "1", "q": hashtag}
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            first_found = 0
            for message_block in soup.select("div.tgme_widget_message"):
                text_block = message_block.select_one("div.tgme_widget_message_text")
                if text_block is None:
                    continue
                raw_text = text_block.get_text("\n", strip=True)
                normalized = raw_text.replace("\xa0", " ").strip()
                if hashtag_lower in normalized.lower():
                    if normalized not in seen:
                        samples.append(normalized)
                        seen.add(normalized)
                        first_found += 1
                        if len(samples) >= limit:
                            break
            logger.info("Поиск q=%s дал %d совпадений (взято %d)", hashtag, first_found, len(samples))
            if len(samples) >= limit:
                return samples[:limit]
        except Exception:
            logger.exception("Ошибка при поиске q по %s", hashtag)

        for page in range(max_pages):
            params = {"embed": "1"}
            if before:
                params["before"] = before
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            message_blocks = soup.select("div.tgme_widget_message")
            if not message_blocks:
                logger.info("Страница %d пуста для %s", page + 1, channel_slug)
                break
            page_found = 0
            min_id: Optional[int] = None
            for message_block in message_blocks:
                text_block = message_block.select_one("div.tgme_widget_message_text")
                if text_block is None:
                    continue
                raw_text = text_block.get_text("\n", strip=True)
                normalized = raw_text.replace("\xa0", " ").strip()
                if hashtag_lower in normalized.lower():
                    if normalized not in seen:
                        samples.append(normalized)
                        seen.add(normalized)
                        page_found += 1
                        if len(samples) >= limit:
                            break
                data_post = message_block.get("data-post") or ""
                parts = data_post.split("/")
                if len(parts) == 2 and parts[1].isdigit():
                    msg_id = int(parts[1])
                    if min_id is None or msg_id < min_id:
                        min_id = msg_id
            logger.info(
                "Страница %d: найдено %d, всего %d для %s/%s",
                page + 1,
                page_found,
                len(samples),
                channel_slug,
                hashtag,
            )
            if len(samples) >= limit:
                break
            if min_id is None:
                break
            before = str(min_id)
    logger.info(
        "Итого примеров: %d для %s/%s",
        len(samples),
        channel_slug,
        hashtag,
    )
    return samples
