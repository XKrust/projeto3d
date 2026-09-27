"""Normalizacao e casamento de texto usados na extracao de topicos.

`normalize`/`tokens` preparam titulo+tags de um `RawItem` para casamento contra
nome/aliases de topicos; `matches_phrase` e o casamento em si (usado tambem por
`app.topics.category`).
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml

_SEED_DIR = Path(__file__).resolve().parent.parent / "seed"

# Unicode: CJK Unified Ideographs, Hiragana, Katakana, Hangul Syllables.
_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x4E00, 0x9FFF),
    (0x3040, 0x309F),
    (0x30A0, 0x30FF),
    (0xAC00, 0xD7A3),
)

_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)
_MIN_LATIN_TOKEN_LEN = 3


def _is_cjk_char(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def is_cjk(text: str) -> bool:
    """True se `text` contem algum caractere Han, Hiragana, Katakana ou Hangul."""
    return any(_is_cjk_char(ch) for ch in text)


def normalize(text: str) -> str:
    """NFKC, minusculas, remove acentos so de caracteres latinos, colapsa espacos.

    Caracteres CJK ficam intactos (nao ha acento latino a remover neles).
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    chars: list[str] = []
    for ch in text:
        if _is_cjk_char(ch):
            chars.append(ch)
            continue
        decomposed = unicodedata.normalize("NFKD", ch)
        chars.append("".join(c for c in decomposed if not unicodedata.combining(c)))
    text = "".join(chars)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    with open(_SEED_DIR / "stopwords.yaml", encoding="utf-8") as f:
        words = yaml.safe_load(f) or []
    return frozenset(normalize(w) for w in words)


def tokens(text: str) -> list[str]:
    """Tokeniza `text`: separa por espaco/pontuacao, remove stopwords e descarta
    tokens latinos com menos de 3 caracteres (tokens com algum caractere CJK nao
    tem tamanho minimo)."""
    normalized = normalize(text)
    stop = _stopwords()
    result: list[str] = []
    for tok in _SPLIT_RE.split(normalized):
        if not tok or tok in stop:
            continue
        if not is_cjk(tok) and len(tok) < _MIN_LATIN_TOKEN_LEN:
            continue
        result.append(tok)
    return result


def matches_phrase(haystack: str, phrase: str) -> bool:
    """True se `phrase` (ja normalizada) aparece em `haystack` (ja normalizado).

    Frases com algum caractere CJK casam por substring; frases latinas casam em
    limite de palavra do texto normalizado.
    """
    if not phrase:
        return False
    if is_cjk(phrase):
        return phrase in haystack
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, haystack) is not None
