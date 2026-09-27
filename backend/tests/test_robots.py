from pathlib import Path

from app.collectors.robots import is_allowed
from app.http import USER_AGENT

FIXTURES = Path(__file__).parent / "fixtures" / "printables"
ROBOTS_TXT = (FIXTURES / "robots.txt").read_text(encoding="utf-8")


def test_allowed_url_returns_true():
    assert is_allowed(ROBOTS_TXT, "https://www.printables.com/model", USER_AGENT) is True


def test_disallowed_url_returns_false():
    # Robots.txt generico (nao o real do Printables): `urllib.robotparser` decide pela
    # PRIMEIRA regra que casa, na ordem do arquivo (sem "regra mais especifica primeiro"
    # do padrao do Google). No robots.txt real do Printables, `Allow: /` vem antes de
    # `Disallow: /world/` e casa com qualquer caminho primeiro — na pratica, nenhuma URL e
    # bloqueada por esse parser, nem as de `/world/` (ver nota em docs/coletores.md). Por
    # isso este teste usa um robots.txt onde o `Disallow` e a unica regra, para exercitar o
    # caminho "bloqueado" de `is_allowed`.
    robots_txt = "User-agent: *\nDisallow: /private/\n"
    assert is_allowed(robots_txt, "https://www.printables.com/private/x", USER_AGENT) is False


def test_real_printables_robots_allows_everything_due_to_rule_order():
    # Achado documentado: com o robots.txt real (Allow: / antes de Disallow: /world/),
    # `urllib.robotparser` permite ate mesmo `/world/...`, porque a primeira regra que casa
    # (`Allow: /`) ja decide. Caracterizamos esse comportamento aqui para nao ser
    # redescoberto por engano depois.
    assert is_allowed(ROBOTS_TXT, "https://www.printables.com/world/something", USER_AGENT) is True
