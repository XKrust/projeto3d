"""Coletor YouTube: videos mais populares por regiao e categoria."""

from app.collectors.base import CollectedItem, Collector
from app.http import get_with_retry

VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CATEGORY_IDS: tuple[int, ...] = (1, 20, 24)
MAX_TAGS = 10
MAX_RESULTS = 50
SKIPPED_STATUS_CODES = (400, 404)


def _maybe_int(value: str | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _to_item(video: dict, country: str) -> CollectedItem:
    snippet = video.get("snippet", {})
    statistics = video.get("statistics", {})
    views = int(statistics.get("viewCount", 0))
    thumb_url = snippet.get("thumbnails", {}).get("medium", {}).get("url")

    return CollectedItem(
        external_id=video["id"],
        title=snippet.get("title", ""),
        country=country,
        metric=float(views),
        tags=snippet.get("tags", [])[:MAX_TAGS],
        thumb_url=thumb_url,
        views=views,
        comments=_maybe_int(statistics.get("commentCount")),
        likes=_maybe_int(statistics.get("likeCount")),
    )


class YouTubeCollector(Collector):
    """Videos em `chart=mostPopular` do YouTube, por pais e categoria."""

    name = "youtube"
    label = "YouTube"
    kind = "api"
    needs_key = ("youtube",)
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        key = self.settings["api_keys"]["youtube"]
        items: list[CollectedItem] = []

        for country in self.settings["countries"]:
            for category_id in CATEGORY_IDS:
                response = get_with_retry(
                    self.http,
                    "GET",
                    VIDEOS_URL,
                    params={
                        "part": "snippet,statistics",
                        "chart": "mostPopular",
                        "regionCode": country,
                        "videoCategoryId": category_id,
                        "maxResults": MAX_RESULTS,
                        "key": key,
                    },
                )
                if response.status_code in SKIPPED_STATUS_CODES:
                    continue

                data = response.json()
                for video in data.get("items", []):
                    items.append(_to_item(video, country))

        return items
