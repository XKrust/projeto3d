"""Chamada 2 da análise: a crítica, com rubrica ancorada e regras de honestidade
(spec 3a §4.3). O app ainda confere a resposta em `validate.py`."""

from app.ai.provider import ImageInput, TextProvider
from app.analyzer.errors import ask_json
from app.analyzer.validate import AUTO_RENDER_KINDS, CRITERIA

RUBRIC = """Rubrica de 0 a 10 para cada critério (use as âncoras, não a sua simpatia):
- 0–3: erro que qualquer comprador nota;
- 4–6: ok, amador bem feito;
- 7–8: nível de loja, vende;
- 9–10: no nível das referências."""

RULES = """Regras de honestidade (obrigatórias):
1. Toda crítica diz ONDE: "image" (número da imagem do usuário) e "area" (parte do modelo).
2. Toda crítica traz "confidence": "alta", "media" ou "baixa". Se não dá para ver direito,
   use "baixa". Se um critério não se aplica ou não dá para avaliar pelas imagens, dê
   "score": null e diga no "why" que não dá para avaliar.
3. Ponto forte é específico (o quê + onde), nunca genérico como "ficou muito bom".
4. Comparação com as referências é concreta e cita a referência pelo número.
5. Proibido bajular ou exagerar ("incrível", "perfeito", "péssimo", "amador"). Tom de um
   profissional revisando o trabalho de um colega: direto, respeitoso, útil.
6. Não invente defeito nem qualidade para completar lista: menos itens é melhor que item falso.
7. Cada "fix" é um passo concreto de correção (ferramenta/técnica no Blender, ZBrush etc.)."""

OUTPUT = """Responda só com JSON neste formato:
{"criteria": {"<critério>": {"score": 0-10 ou null, "why": "uma frase"}},
 "strengths": [{"text": "...", "image": 1, "area": "..."}],
 "improvements": [{"image": 1, "area": "...", "problem": "...", "fix": "...", "gain": "...",
                   "confidence": "alta|media|baixa", "criterion": "<critério>"}],
 "reference_comparison": [{"reference": 1, "text": "o que a referência faz que o usuário ainda não faz"}],
 "top_actions": ["as 3 ações que mais sobem a nota"]}"""


def _criteria_text(market: str, has_wireframe: bool) -> str:
    lines = []
    for slug, label in CRITERIA.items():
        note = ""
        if slug == "topologia":
            note = " (só se houver wireframe; senão null)"
        if slug == "imprimibilidade":
            note = " (partes finas, apoios, encaixes; só para impressão; senão null)"
        lines.append(f"- {slug}: {label}{note}")
    extra = f"Mercado: {'impressão 3D' if market == 'print' else 'digital'}. "
    extra += "Há wireframe (é a última imagem do usuário)." if has_wireframe else "Não há wireframe."
    return "Critérios:\n" + "\n".join(lines) + "\n" + extra


def _auto_render_text(auto_renders: str) -> str:
    if auto_renders not in AUTO_RENDER_KINDS:
        return ""
    text = ("As imagens do usuário foram tiradas automaticamente pelo app a partir do arquivo 3D (luz, "
            "fundo e ângulos padrão do app, não do usuário): dê score null para render e apresentacao e "
            "não sugira melhorias de luz, fundo, ângulo ou capa.")
    if auto_renders == "clay":
        text += " O modelo aparece em argila cinza, sem os materiais do arquivo: materiais também null."
    return text


def build_prompt(*, identified: dict, market: str, authorship: str, has_wireframe: bool, n_images: int,
                 n_references: int, auto_renders: str = "") -> str:
    who = "fan-art de " + identified["character"] if authorship == "fanart" and identified.get("character") else authorship
    if n_references:
        refs = (f"As imagens 1 a {n_images} são do usuário. As seguintes são as referências 1 a "
                f"{n_references}, nesta ordem: modelos de grandes artistas do mesmo tema. Compare com "
                "elas; referência 1 é a primeira depois das imagens do usuário.")
    else:
        refs = (f"As imagens 1 a {n_images} são do usuário. Não há referências desta vez: compare com o "
                "padrão profissional do tema e diga isso na comparação.")
    parts = [
        "Você é um artista 3D profissional revisando o trabalho de um colega que quer vender o modelo.",
        f"Modelo: {identified['theme']} ({identified.get('style') or 'estilo não identificado'}; {who}).",
        refs, _auto_render_text(auto_renders), RUBRIC, _criteria_text(market, has_wireframe), RULES, OUTPUT,
    ]
    return "\n\n".join(part for part in parts if part)


def critique(provider: TextProvider, images: list[ImageInput], references: list[ImageInput], *,
             identified: dict, market: str, authorship: str, has_wireframe: bool, auto_renders: str = "") -> dict:
    prompt = build_prompt(identified=identified, market=market, authorship=authorship,
                          has_wireframe=has_wireframe, n_images=len(images), n_references=len(references),
                          auto_renders=auto_renders)
    return ask_json(provider, prompt, [*images, *references], required="criteria")
