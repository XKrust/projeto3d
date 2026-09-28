import json
from pathlib import Path

import httpx
import pytest
import respx

import app.collectors.reddit as reddit_module
from app.collectors.base import CollectorError
from app.collectors.reddit import RedditCollector
from app.constants import GLOBAL
from app.http import make_client

FIXTURES = Path(__file__).parent / "fixtures" / "reddit"
TOKEN_JSON = json.loads((FIXTURES / "token.json").read_text(encoding="utf-8"))
HOT_JSON = json.loads((FIXTURES / "hot.json").read_text(encoding="utf-8"))

SETTINGS = {
    "countries": ["BR"],
    "api_keys": {"reddit_client_id": "cid", "reddit_client_secret": "secret"},
}

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


@pytest.fixture(autouse=True)
def single_subreddit(monkeypatch):
    """Restringe a um unico subreddit para as assercoes ficarem deterministicas."""
    monkeypatch.setattr(reddit_module, "load_subreddits", lambda: ["3Dprinting"])


def _mock_token_and_hot():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=TOKEN_JSON))
    respx.get("https://oauth.reddit.com/r/3Dprinting/hot").mock(
        return_value=httpx.Response(200, json=HOT_JSON)
    )


@respx.mock
def test_metric_is_score_plus_twice_comments():
    _mock_token_and_hot()

    with make_client() as http:
        items = RedditCollector(SETTINGS, http).collect()

    by_id = {item.external_id: item for item in items}
    assert by_id["abc123"].metric == 120 + 2 * 10
    assert by_id["abc123"].likes == 120
    assert by_id["abc123"].comments == 10
    assert by_id["def456"].metric == 50 + 2 * 3


@respx.mock
def test_stickied_posts_are_ignored():
    _mock_token_and_hot()

    with make_client() as http:
        items = RedditCollector(SETTINGS, http).collect()

    assert "pin1" not in {item.external_id for item in items}
    assert len(items) == 2


@respx.mock
def test_all_items_have_global_country():
    _mock_token_and_hot()

    with make_client() as http:
        items = RedditCollector(SETTINGS, http).collect()

    assert items
    assert all(item.country == GLOBAL for item in items)


@respx.mock
def test_tags_are_subreddit_and_flair_without_empty_entries():
    _mock_token_and_hot()

    with make_client() as http:
        items = RedditCollector(SETTINGS, http).collect()

    by_id = {item.external_id: item for item in items}
    assert by_id["abc123"].tags == ["3Dprinting", "Print"]
    # link_flair_text vazio ("") nao vira uma tag vazia.
    assert by_id["def456"].tags == ["3Dprinting"]


@respx.mock
def test_token_401_raises_collector_error():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401))

    with make_client() as http:
        with pytest.raises(CollectorError, match=r"Chave inválida ou sem permissão \(401\)"):
            RedditCollector(SETTINGS, http).collect()
