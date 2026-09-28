"""O que conta como tema de verdade no radar.

Palavra solta comum de dicionário ("Game", "Night", "germany") não é tema de modelo 3D:
aparece em qualquer título e, por ser comum, sempre subia para o topo do radar. Nome
próprio raro ("Gojo", "Frieren") e expressão de 2+ palavras ("Articulated Dragon")
continuam valendo. Temas curados e de estreias (entidades) valem sempre; quem chama
decide isso (ver `extract_topics` e `compute_scores`).

A frequência vem do `wordfreq` (escala Zipf: 3 = uma vez por milhão de palavras). Vale a
maior frequência entre EN, PT, ES, FR e DE; termo em japonês usa a tabela do japonês.
"""

import math
import re
from functools import cache

from wordfreq import get_frequency_dict, zipf_frequency

from app.topics.normalize import is_cjk, normalize

# Acima disto, a palavra é comum demais para ser tema sozinha. Calibrado com os dados
# reais: lixo ("dungeon" 3.57, "dummy" 3.64, "game" 5.72) fica acima; nomes próprios
# ("gojo" 1.69, "frieren" 3.32, "pikachu" 3.18) ficam abaixo.
COMMON_WORD_ZIPF = 3.4
LATIN_LANGUAGES = ("en", "pt", "es", "fr", "de")


@cache
def _japanese() -> dict[str, float]:
    # Consulta direta na tabela: `zipf_frequency(..., "ja")` exigiria o MeCab instalado.
    return get_frequency_dict("ja")


def _zipf(key: str) -> float:
    if is_cjk(key):
        freq = _japanese().get(key, 0.0)
        return math.log10(freq) + 9 if freq > 0 else 0.0
    return max(zipf_frequency(key, lang) for lang in LATIN_LANGUAGES)


def is_generic(name: str) -> bool:
    """True se `name` é uma palavra só (ou um termo CJK só) e comum de dicionário."""
    words = [w for w in re.split(r"[^\w]+", normalize(name)) if w]
    if not words:
        return True
    if len(words) > 1:  # "Spider-Man", "Dungeon Meshi", "Articulated Dragon"
        return False
    return _zipf(words[0]) >= COMMON_WORD_ZIPF


def words_of(names: set[str]) -> set[str]:
    """Todas as palavras (normalizadas) dos nomes e aliases de temas conhecidos."""
    return {w for name in names for w in re.split(r"[^\w]+", normalize(name)) if w}


def is_fragment(name: str, known_words: set[str]) -> bool:
    """True se `name` é uma palavra só que faz parte de um tema conhecido ("Meshi" de
    "Dungeon Meshi", "Cyberpunk" de "Cyberpunk: Edgerunners"): o tema inteiro já cobre."""
    words = [w for w in re.split(r"[^\w]+", normalize(name)) if w]
    return len(words) == 1 and words[0] in known_words
