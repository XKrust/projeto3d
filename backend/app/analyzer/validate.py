"""Checagem da resposta da IA (spec 3a §5). Funções puras.

A IA recebe regras de honestidade no prompt, mas o app confere o que dá para conferir:
crítica sem local ou sem correção sai; confiança baixa vira "vale conferir"; bajulação ou
exagero fica marcado; a nota geral é a média das notas (a IA não dá a nota geral).
"""

import re
from statistics import mean

from app.topics.normalize import normalize

CRITERIA: dict[str, str] = {
    "anatomia": "Anatomia e proporção",
    "silhueta": "Silhueta e forma",
    "detalhe": "Detalhe e escultura",
    "pose": "Pose e apelo",
    "materiais": "Materiais e textura",
    "render": "Iluminação e render",
    "apresentacao": "Apresentação (capa)",
    "topologia": "Topologia",
    "imprimibilidade": "Imprimibilidade",
}

FORBIDDEN_WORDS: frozenset[str] = frozenset(
    normalize(w)
    for w in [
        "incrível", "perfeito", "perfeita", "impecável", "obra-prima", "maravilhoso", "fantástico",
        "espetacular", "péssimo", "horrível", "amador", "amadora", "lixo",
        "amazing", "perfect", "flawless", "masterpiece", "stunning", "terrible", "awful",
    ]
)

# Fotos que o app tira do arquivo 3D (tela Analisar): a luz, o fundo e os ângulos são do app, e
# em "argila" o material também. Esses critérios não medem o trabalho do modelador.
AUTO_RENDER_KINDS = ("clay", "materials")
AUTO_RENDER_WHY = "Fotos tiradas pelo app a partir do arquivo 3D: não dá para avaliar. Envie seus renders para avaliar isto."


def auto_render_skipped(auto_renders: str) -> frozenset[str]:
    if auto_renders not in AUTO_RENDER_KINDS:
        return frozenset()
    return frozenset({"render", "apresentacao", "materiais"} if auto_renders == "clay" else {"render", "apresentacao"})


MAX_STRENGTHS = 5
MAX_IMPROVEMENTS = 5
MAX_ACTIONS = 3
LOW_CONFIDENCE = "baixa"

_WORD = re.compile(r"\w+(?:-\w+)*")


def _flagged(*texts: object) -> bool:
    words = {w for t in texts if isinstance(t, str) for w in _WORD.findall(normalize(t))}
    return bool(words & FORBIDDEN_WORDS)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _dicts(value: object) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _valid_image(value: object, n_images: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= n_images


def _criteria(raw: object, *, has_wireframe: bool, market: str, skipped: frozenset[str]) -> dict[str, dict]:
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for slug in CRITERIA:
        if slug in skipped:
            result[slug] = {"score": None, "why": AUTO_RENDER_WHY}
            continue
        item = raw.get(slug) if isinstance(raw.get(slug), dict) else {}
        score = item.get("score")
        valid = isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 10
        if (slug == "topologia" and not has_wireframe) or (slug == "imprimibilidade" and market != "print"):
            valid = False
        result[slug] = {"score": score if valid else None, "why": _text(item.get("why"))}
    return result


def validate_result(raw: dict, *, n_images: int, n_references: int, has_wireframe: bool, market: str,
                    auto_renders: str = "") -> dict:
    """Resposta crua da IA → `{criteria, strengths, improvements, to_check,
    reference_comparison, top_actions, overall}` (spec 3a §5)."""
    raw = raw if isinstance(raw, dict) else {}
    skipped = auto_render_skipped(auto_renders)
    criteria = _criteria(raw.get("criteria"), has_wireframe=has_wireframe, market=market, skipped=skipped)

    strengths = []
    for s in _dicts(raw.get("strengths")):
        text, area = _text(s.get("text")), _text(s.get("area"))
        if text and area:
            image = s.get("image") if _valid_image(s.get("image"), n_images) else None
            strengths.append({"text": text, "image": image, "area": area, "flagged": _flagged(text)})

    improvements, to_check = [], []
    for i in _dicts(raw.get("improvements")):
        area, fix, problem = _text(i.get("area")), _text(i.get("fix")), _text(i.get("problem"))
        if not (area and fix and problem and _valid_image(i.get("image"), n_images)):
            continue
        criterion = i.get("criterion") if i.get("criterion") in CRITERIA else None
        if criterion in skipped:
            continue  # "melhore a luz" das fotos que o app tirou não é trabalho do modelador
        item = {
            "image": i["image"], "area": area, "problem": problem, "fix": fix, "gain": _text(i.get("gain")),
            "confidence": i.get("confidence") if i.get("confidence") in ("alta", "media", "baixa") else "media",
            "criterion": criterion, "flagged": _flagged(problem, fix, i.get("gain")),
        }
        (to_check if item["confidence"] == LOW_CONFIDENCE else improvements).append(item)

    def criterion_score(item: dict) -> float:
        score = criteria[item["criterion"]]["score"] if item["criterion"] else None
        return 11 if score is None else score

    improvements.sort(key=criterion_score)  # sort estável: empate mantém a ordem da IA
    improvements = improvements[:MAX_IMPROVEMENTS]

    comparison = []
    for c in _dicts(raw.get("reference_comparison")):
        ref, text = c.get("reference"), _text(c.get("text"))
        if text and _valid_image(ref, n_references):
            comparison.append({"reference": ref, "text": text, "flagged": _flagged(text)})

    actions = [a.strip() for a in raw.get("top_actions") or [] if isinstance(a, str) and a.strip()] \
        if isinstance(raw.get("top_actions"), list) else []
    if not actions:
        actions = [i["fix"] for i in improvements]
    scores = [c["score"] for c in criteria.values() if c["score"] is not None]

    return {
        "criteria": criteria,
        "strengths": strengths[:MAX_STRENGTHS],
        "improvements": improvements,
        "to_check": to_check,
        "reference_comparison": comparison,
        "top_actions": actions[:MAX_ACTIONS],
        "overall": round(mean(scores), 1) if scores else None,
    }
