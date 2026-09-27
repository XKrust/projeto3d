"""Coletor Reddit: posts em alta (hot) de subreddits de cultura 3D e cultura pop."""

from pathlib import Path

import yaml

from app.collectors.base import CollectedItem, Collector
from app.constants import GLOBAL
from app.http import get_with_retry

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
HOT_URL = "https://oauth.reddit.com/r/{subreddit}/hot"
LIMIT = 50
SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "reddit.yaml"


def _load_subreddits() -> list[str]:
    with open(SEED_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _to_item(post: dict, subreddit: str) -> CollectedItem:
    flair = post.get("link_flair_text") or ""
    tags = [tag for tag in (subreddit, flair) if tag]
    score = int(post.get("score", 0))
    comments = int(post.get("num_comments", 0))

    return CollectedItem(
        external_id=post["id"],
        title=post.get("title", ""),
        country=GLOBAL,
        metric=float(score + 2 * comments),
        tags=tags,
        likes=score,
        comments=comments,
    )


class RedditCollector(Collector):
    """Posts `hot` dos subreddits de `app/seed/reddit.yaml` (sinal global, sem pais)."""

    name = "reddit"
    label = "Reddit"
    kind = "api"
    needs_key = ("reddit_client_id", "reddit_client_secret")
    interval_minutes = 60

    def collect(self) -> list[CollectedItem]:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        items: list[CollectedItem] = []
        for subreddit in _load_subreddits():
            response = get_with_retry(
                self.http,
                "GET",
                HOT_URL.format(subreddit=subreddit),
                headers=headers,
                params={"limit": LIMIT},
            )
            data = response.json()
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                if post.get("stickied"):
                    continue
                items.append(_to_item(post, subreddit))
        return items

    def _get_token(self) -> str:
        api_keys = self.settings["api_keys"]
        response = get_with_retry(
            self.http,
            "POST",
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(api_keys["reddit_client_id"], api_keys["reddit_client_secret"]),
        )
        return response.json()["access_token"]
