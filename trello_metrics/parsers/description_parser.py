from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from trello_metrics.domain.models import CardDescriptionData, PausaDetail, RetornoDetail
from trello_metrics.utils.text import clean_spaces, strip_accents

_SECTION_PATTERN = re.compile(
    r"###\s*\d+(?:\.\d+)?\s*-\s*(?P<title>[^\n]+)\n(?P<body>.*?)(?=\n###\s*\d|\Z)",
    re.DOTALL,
)

# "[Retorno 1 (dev) (Revisão)]:" / "[Retorno 2 (sup)]:" ... captures until the
# matching "[Solucao N ...]:" block or the next "[Retorno" / "---" marker.
_RETORNO_PATTERN = re.compile(
    r"\[\s*Retorno\s*(?P<numero>\d+)\s*\(\s*(?P<tipo>dev|sup)\s*\)\s*"
    r"(?:\(\s*(?P<subtipo>[^)]+?)\s*\))?\s*\]\s*:\s*"
    r"(?P<motivo>.*?)"
    r"(?=\[\s*Solu[cç][aã]o\s*\d|\[\s*Retorno\s*\d|\n---|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_SOLUCAO_PATTERN = re.compile(
    r"\[\s*Solu[cç][aã]o\s*(?P<numero>\d+)\s*\(\s*(?P<tipo>dev|sup)\s*\)\s*"
    r"(?:\(\s*(?P<subtipo>[^)]+?)\s*\))?\s*\]\s*:\s*"
    r"(?P<solucao>.*?)"
    r"(?=\[\s*Retorno\s*\d|\[\s*Solu[cç][aã]o\s*\d|\n---|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_PAUSA_PATTERN = re.compile(
    r"\[\s*Motivo\s*Pause\s*(?P<numero>\d+)\s*\]\s*"
    r"(?P<data>\d{2}/\d{2}/\d{4})\s*-\s*(?P<hora>\d{2}:\d{2})\s*:\s*"
    r"(?P<motivo>.*?)"
    r"(?=\[\s*Motivo\s*Pause\s*\d|\n###|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_PLACEHOLDER_MARKERS = (
    "descreva o",
    "informe",
    "adicione",
    "registre",
    "ex.:",
    "ex:",
)


def _clean_block(text: str | None) -> str:
    value = clean_spaces(text)
    value = value.strip(" -\u200c")
    return value


def _is_placeholder(text: str) -> bool:
    if not text:
        return True
    lowered = text.lower()
    return any(lowered.startswith(marker) for marker in _PLACEHOLDER_MARKERS)


def _norm(text: str) -> str:
    return strip_accents(clean_spaces(text)).lower()


def _section_bodies(desc: str) -> dict[str, str]:
    bodies: dict[str, str] = {}
    for match in _SECTION_PATTERN.finditer(desc or ""):
        title = _norm(match.group("title"))
        bodies[title] = match.group("body")
    return bodies


def _find_body(bodies: dict[str, str], *keywords: str, exclude: tuple[str, ...] = ()) -> str:
    for title, body in bodies.items():
        if all(keyword in title for keyword in keywords) and not any(
            keyword in title for keyword in exclude
        ):
            return body
    return ""


def _parse_retornos(desc: str) -> list[RetornoDetail]:
    solucoes: dict[tuple[str, int], str] = {}
    for match in _SOLUCAO_PATTERN.finditer(desc or ""):
        key = (match.group("tipo").lower(), int(match.group("numero")))
        solucoes[key] = _clean_block(match.group("solucao"))

    retornos: list[RetornoDetail] = []
    for match in _RETORNO_PATTERN.finditer(desc or ""):
        tipo = match.group("tipo").lower()
        numero = int(match.group("numero"))
        motivo = _clean_block(match.group("motivo"))
        if _is_placeholder(motivo):
            motivo = ""
        subtipo = clean_spaces(match.group("subtipo")) or None
        if subtipo and " ou " in subtipo.lower():
            subtipo = None
        solucao = solucoes.get((tipo, numero), "")
        if _is_placeholder(solucao):
            solucao = ""
        if not motivo and not solucao:
            continue
        retornos.append(
            RetornoDetail(
                numero=numero,
                tipo=tipo,
                subtipo=subtipo,
                motivo=motivo,
                solucao=solucao,
            )
        )
    retornos.sort(key=lambda item: (item.tipo, item.numero))
    return retornos


def _parse_pausas(desc: str, timezone_name: str = "America/Sao_Paulo") -> list[PausaDetail]:
    tz = ZoneInfo(timezone_name)
    pausas: list[PausaDetail] = []
    for match in _PAUSA_PATTERN.finditer(desc or ""):
        motivo = _clean_block(match.group("motivo"))
        if _is_placeholder(motivo):
            motivo = ""
        momento = None
        try:
            momento = datetime.strptime(
                f"{match.group('data')} {match.group('hora')}", "%d/%m/%Y %H:%M"
            ).replace(tzinfo=tz)
        except ValueError:
            momento = None
        if not motivo:
            continue
        pausas.append(
            PausaDetail(numero=int(match.group("numero")), momento=momento, motivo=motivo)
        )
    pausas.sort(key=lambda item: item.numero)
    return pausas


def parse_card_description(desc: str | None) -> CardDescriptionData:
    """Extract the structured sections from the standard card description template.

    Works for both the "problem" (PM CLIENTE / PROBLEMA) and "analysis" templates;
    the fields that don't apply to a given template simply stay empty.
    """
    text = desc or ""
    bodies = _section_bodies(text)

    def section(*keywords: str, exclude: tuple[str, ...] = ()) -> str:
        value = _clean_block(_find_body(bodies, *keywords, exclude=exclude))
        return "" if _is_placeholder(value) else value

    data = CardDescriptionData(
        cliente=section("cliente"),
        solicitacao=section("solicita", exclude=("analise",)),
        solucao_dev=section("solu", "desenvolvedor"),
        obs_revisor_par=section("observa", "revisor", "par"),
        obs_revisor=section("observa", "revisor", exclude=("par",)),
        obs_tester=section("observa", "tester"),
        observacoes_gerais=section("observa", "gerais"),
        analise_origem=section("analise que originou"),
        solicitacao_analise=section("solicita", "analise"),
        analise_realizada=section("analise", "realizada"),
        recomendacao=section("recomenda"),
        retornos=_parse_retornos(text),
        pausas=_parse_pausas(text),
    )
    return data
