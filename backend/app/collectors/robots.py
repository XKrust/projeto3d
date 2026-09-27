"""Checagem de robots.txt para os coletores de scraping (ex.: Printables)."""

from urllib.robotparser import RobotFileParser


def is_allowed(robots_txt: str, url: str, user_agent: str) -> bool:
    """Diz se `user_agent` pode acessar `url`, segundo o conteudo de `robots_txt`."""
    parser = RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(user_agent, url)
