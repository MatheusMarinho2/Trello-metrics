from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


HIGHLIGHT_LIMIT = 25
QUESTIONABLE_RETURN_LIMIT = 20
MOTIVE_SAMPLE_LIMIT = 12
TEXT_LIMIT = 160

WEAK_MOTIVE_MARKERS = (
    "ajuste",
    "correcao",
    "corrigir",
    "refazer",
    "pequeno",
    "detalhe",
    "descreva",
    "informe",
    "teste",
)

NOT_DEV_FAULT_MARKERS = (
    "comportamento esperado",
    "nao era bug",
    "não era bug",
    "nao e bug",
    "não é bug",
    "ambiente",
    "homolog",
    "configuracao",
    "configuração",
    "dados incorretos",
    "usuario",
    "usuário",
    "solicitante",
    "infra",
    "credencial",
    "acesso",
    "massa de teste",
)

SCOPE_CREEP_MARKERS = (
    "deveria",
    "esperava",
    "faltou",
    "nao tinha",
    "não tinha",
    "precisava",
    "diferente do",
    "diferente da",
    "alem do",
    "além do",
    "extra",
    "novo requisito",
    "nao estava no escopo",
    "não estava no escopo",
    "fora do escopo",
    "mudou o escopo",
    "nao era isso",
    "não era isso",
)

TESTER_WANTED_DIFFERENT_MARKERS = (
    "nao sabia testar",
    "não sabia testar",
    "nao soube testar",
    "não soube testar",
    "nao entendeu",
    "não entendeu",
    "queria outra",
    "queria que",
    "deveria ser assim",
    "nao funciona como",
    "não funciona como",
    "preferia",
    "na minha opiniao",
    "na minha opinião",
)

PLACEHOLDER_MARKERS = (
    "descreva o",
    "informe",
    "adicione",
    "registre",
    "ex.:",
    "ex:",
)


def build_returns_pauses_insights(
    *,
    card_dossier: dict[str, Any] | None,
    team_summary: dict[str, Any] | None,
    quality_gates: dict[str, Any] | None,
) -> dict[str, Any]:
    cards = _unique_dossier_cards(card_dossier or {})
    if not cards:
        return {
            "cards_evaluated": 0,
            "note": "Sem dossie de cards no periodo — analise retornos/pausas com team_summary se existir.",
            "team_totals": _team_return_totals(team_summary),
        }

    return_motives: Counter[str] = Counter()
    return_subtypes: Counter[str] = Counter()
    return_types: Counter[str] = Counter()
    pause_motives: Counter[str] = Counter()
    attribution: Counter[str] = Counter()
    solution_patterns: Counter[str] = Counter()
    motive_subtype_pairs: Counter[str] = Counter()
    fairness_categories: Counter[str] = Counter()
    questionable_returns: list[dict[str, Any]] = []
    highlights: list[dict[str, Any]] = []
    analysis_cards: list[dict[str, Any]] = []
    by_person: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    cards_with_returns = 0
    cards_with_pauses = 0
    total_return_events = 0
    total_pause_events = 0

    for card in cards:
        retornos = card.get("retornos") or []
        pausas = card.get("pausas") or []
        return_dev = int(card.get("return_dev_count") or 0)
        pause_count = int(card.get("pause_count") or 0)

        if retornos or return_dev:
            cards_with_returns += 1
        if pausas or pause_count:
            cards_with_pauses += 1
        total_return_events += max(len(retornos), return_dev)
        total_pause_events += max(len(pausas), pause_count)

        for item in retornos:
            motive = _normalize_text(item.get("motivo"))
            if motive:
                return_motives[motive] += 1
            subtype = _normalize_text(item.get("subtipo"))
            if subtype:
                return_subtypes[subtype] += 1
            tipo = _normalize_text(item.get("tipo"))
            if tipo:
                return_types[tipo] += 1
            assigned = _normalize_text(item.get("atribuido_a"))
            if assigned:
                attribution[assigned] += 1
            if subtype and motive:
                motive_subtype_pairs[f"{subtype} | {motive[:80]}"] += 1

            solution = _normalize_text(item.get("solucao"))
            if solution:
                solution_patterns[solution[:100]] += 1

            assessment = _assess_retorno_fairness(item, card)
            for flag in assessment["fairness_flags"]:
                fairness_categories[flag] += 1
            if assessment["fairness_score"] > 0:
                questionable_returns.append(
                    {
                        "card_id": card.get("card_id"),
                        "card_name": card.get("card_name"),
                        "sistema": card.get("sistema"),
                        "desenvolvedor": card.get("desenvolvedor"),
                        "tester": card.get("tester"),
                        "revisor_par": card.get("revisor_par"),
                        "revisor": card.get("revisor"),
                        **assessment,
                    }
                )

        for item in pausas:
            motive = _normalize_text(item.get("motivo"))
            if motive:
                pause_motives[motive] += 1

        flags, score = _card_flags(card)
        if score > 0:
            entry = _highlight_card(card, flags, score)
            highlights.append(entry)
            for person in _card_people(card):
                by_person[person]["highlight_cards"] += 1
                by_person[person]["severity_score"] += score

        if card.get("kind") == "analysis":
            analysis_cards.append(_analysis_card_summary(card, flags))

    highlights.sort(key=lambda item: item.get("severity_score", 0), reverse=True)
    questionable_returns.sort(key=lambda item: item.get("fairness_score", 0), reverse=True)

    return {
        "cards_evaluated": len(cards),
        "cards_with_returns": cards_with_returns,
        "cards_with_pauses": cards_with_pauses,
        "total_return_events": total_return_events,
        "total_pause_events": total_pause_events,
        "team_totals": _team_return_totals(team_summary),
        "quality_gates": _compact_quality_gates(quality_gates),
        "top_return_motives": _counter_rows(return_motives, MOTIVE_SAMPLE_LIMIT),
        "top_return_subtypes": _counter_rows(return_subtypes, MOTIVE_SAMPLE_LIMIT),
        "return_types": _counter_rows(return_types, 6),
        "return_attribution": _counter_rows(attribution, 8),
        "top_return_solutions": _counter_rows(solution_patterns, MOTIVE_SAMPLE_LIMIT),
        "common_motive_subtype_pairs": _counter_rows(motive_subtype_pairs, 10),
        "return_fairness_summary": {
            "questionable_returns_count": len(questionable_returns),
            "by_category": _counter_rows(fairness_categories, 12),
            "note": (
                "Use questionable_returns para diferenciar retrabalho legitimo de movimento/registro "
                "indevido que distorce metricas de fluxo e qualidade do desenvolvedor."
            ),
        },
        "questionable_returns": questionable_returns[:QUESTIONABLE_RETURN_LIMIT],
        "top_pause_motives": _counter_rows(pause_motives, MOTIVE_SAMPLE_LIMIT),
        "highlight_cards": highlights[:HIGHLIGHT_LIMIT],
        "analysis_cards": sorted(
            analysis_cards,
            key=lambda item: item.get("severity_score", 0),
            reverse=True,
        )[:HIGHLIGHT_LIMIT],
        "by_person": dict(by_person),
    }


def highlights_for_people(
    insights: dict[str, Any],
    names: list[str],
) -> list[dict[str, Any]]:
    name_set = set(names)
    return [
        card
        for card in insights.get("highlight_cards") or []
        if any(person in name_set for person in (card.get("people") or []))
    ]


def _unique_dossier_cards(dossier: dict[str, Any]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for _dev, groups in (dossier.get("by_developer") or {}).items():
        if not isinstance(groups, dict):
            continue
        for bucket in ("tarefas_normais", "cards_analise"):
            for card in groups.get(bucket) or []:
                card_id = str(card.get("card_id") or card.get("card_name") or "")
                if card_id:
                    by_id[card_id] = card
    for bucket in ("by_solicitante", "by_tester"):
        for _person, rows in (dossier.get(bucket) or {}).items():
            for card in rows or []:
                card_id = str(card.get("card_id") or card.get("card_name") or "")
                if card_id and card_id not in by_id:
                    by_id[card_id] = card
    return list(by_id.values())


def _team_return_totals(team_summary: dict[str, Any] | None) -> dict[str, Any]:
    if not team_summary:
        return {}
    return {
        "cards_delivered": team_summary.get("cards_delivered"),
        "rework_rate_pct": team_summary.get("rework_rate_pct"),
        "quality_rate_pct": team_summary.get("quality_rate_pct"),
        "total_return_dev_events": team_summary.get("total_return_dev_events"),
        "cards_with_rework_count": team_summary.get("cards_with_rework_count"),
        "test_returns_missing_reason_count": team_summary.get("test_returns_missing_reason_count"),
        "double_review_mandatory_violations": team_summary.get("double_review_mandatory_violations"),
    }


def _compact_quality_gates(quality_gates: dict[str, Any] | None) -> dict[str, Any]:
    if not quality_gates:
        return {}
    return {
        "mandatory_violations_count": quality_gates.get("mandatory_violations_count"),
        "mandatory_compliance_pct": quality_gates.get("mandatory_compliance_pct"),
        "mandatory_violations_sample": (quality_gates.get("mandatory_violations") or [])[:8],
    }


def _card_flags(card: dict[str, Any]) -> tuple[list[str], int]:
    flags: list[str] = []
    score = 0

    return_dev = int(card.get("return_dev_count") or 0)
    pause_count = int(card.get("pause_count") or 0)
    retornos = card.get("retornos") or []
    pausas = card.get("pausas") or []

    if return_dev >= 3 or len(retornos) >= 3:
        flags.append(f"retornos elevados ({max(return_dev, len(retornos))})")
        score += 8
    elif return_dev >= 2 or len(retornos) >= 2:
        flags.append(f"multiplos retornos ({max(return_dev, len(retornos))})")
        score += 5
    elif return_dev >= 1 or retornos:
        score += 2

    if pause_count >= 3 or len(pausas) >= 3:
        flags.append(f"pausas frequentes ({max(pause_count, len(pausas))})")
        score += 6
    elif pause_count >= 2 or len(pausas) >= 2:
        flags.append(f"multiplas pausas ({max(pause_count, len(pausas))})")
        score += 4
    elif pause_count >= 1 or pausas:
        score += 1

    if int(card.get("retest_cycles") or 0) >= 2:
        flags.append(f"retestes ({card.get('retest_cycles')})")
        score += 4

    if card.get("double_review_violation"):
        flags.append("violacao dupla revisao obrigatoria")
        score += 7

    if int(card.get("test_return_missing_reason_count") or 0) > 0:
        flags.append("retorno de teste sem motivo registrado")
        score += 6

    if card.get("peer_review_sent_back") and card.get("return_dev_by_teste_count"):
        flags.append("retorno apos revisao em par com escape para teste")
        score += 5

    descricao = card.get("descricao") or {}
    if card.get("kind") == "analysis":
        if not _normalize_text(descricao.get("analise_realizada")):
            flags.append("card de analise sem analise_realizada preenchida")
            score += 6
        if return_dev or retornos:
            flags.append("card de analise com retorno para desenvolvimento")
            score += 4
        if not _normalize_text(descricao.get("recomendacao")):
            flags.append("card de analise sem recomendacao")
            score += 3

    for item in retornos:
        assessment = _assess_retorno_fairness(item, card)
        if assessment["fairness_score"] >= 4:
            flags.append(assessment["headline"])
            score += min(8, assessment["fairness_score"])

    return flags, score


def _assess_retorno_fairness(item: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    motive_raw = str(item.get("motivo") or "").strip()
    solution_raw = str(item.get("solucao") or "").strip()
    motive = _normalize_text(motive_raw)
    solution = _normalize_text(solution_raw)
    subtype = _normalize_text(item.get("subtipo"))
    assigned = _normalize_text(item.get("atribuido_a"))
    tipo = _normalize_text(item.get("tipo"))

    flags: list[str] = []
    score = 0
    responsible_party: str | None = None

    if not motive or _is_placeholder_text(motive):
        flags.append("retorno_sem_motivo_valido")
        score += 5
    elif len(motive) < 18 or any(marker in motive for marker in WEAK_MOTIVE_MARKERS if marker not in ("teste",)):
        flags.append("motivo_vago_ou_generico")
        score += 3

    if motive and not solution:
        flags.append("retorno_sem_solucao_registrada")
        score += 3
    elif solution and _suggests_not_dev_fault(solution):
        flags.append("solucao_indica_causa_fora_do_codigo")
        score += 4
        responsible_party = _infer_responsible_party(subtype, assigned, card, external_cause=True)

    if subtype and assigned and _looks_misattributed(subtype, assigned):
        flags.append("subtipo_conflita_com_atribuicao_do_movimento")
        score += 6
        responsible_party = _party_from_assigned(assigned)

    movement_party = _movement_attribution_mismatch(card, subtype, assigned)
    if movement_party:
        flags.append("movimento_para_retorno_possivelmente_indevido")
        score += 7
        responsible_party = movement_party

    if assigned == "tester" and int(card.get("test_return_missing_reason_count") or 0) > 0:
        flags.append("retorno_de_teste_sem_motivo_no_registro")
        score += 6
        responsible_party = "tester"

    if assigned == "tester" and subtype and "revis" in subtype:
        flags.append("subtipo_revisao_mas_movimento_atribuido_a_tester")
        score += 5
        responsible_party = "tester"

    if assigned == "revisor" and subtype and "teste" in subtype:
        flags.append("subtipo_teste_mas_movimento_atribuido_a_revisor")
        score += 5
        responsible_party = "revisor"

    dev_returns = int(card.get("return_dev_by_teste_count") or 0) + int(
        card.get("return_dev_by_revisao_count") or 0
    )
    if tipo == "dev" and dev_returns == 0 and len(card.get("retornos") or []) > 0:
        flags.append("registro_texto_de_retorno_sem_movimento_mapeado")
        score += 2

    headline = _fairness_headline(flags, responsible_party)
    impact = _metric_impact_note(flags, responsible_party)
    injustice_reasons = _infer_injustice_reasons(motive, solution, flags, card)

    return {
        "retorno_numero": item.get("numero"),
        "tipo": item.get("tipo"),
        "subtipo": item.get("subtipo"),
        "motivo": _clip(motive_raw),
        "solucao": _clip(solution_raw),
        "atribuido_a": item.get("atribuido_a"),
        "fairness_flags": flags,
        "fairness_score": score,
        "possibly_unfair_to_developer": score >= 4,
        "responsible_party_suspected": responsible_party,
        "headline": headline,
        "metric_impact_note": impact,
        "injustice_reasons": injustice_reasons,
        "should_review_dev_metrics": score >= 4,
    }


def _movement_attribution_mismatch(
    card: dict[str, Any],
    subtype: str,
    assigned: str,
) -> str | None:
    tester_returns = int(card.get("return_dev_by_teste_count") or 0)
    reviewer_returns = int(card.get("return_dev_by_revisao_count") or 0)

    if assigned == "tester" and subtype and "revis" in subtype and tester_returns > 0:
        return "tester"
    if assigned == "revisor" and subtype and "teste" in subtype and reviewer_returns > 0:
        return "revisor"
    if assigned == "tester" and reviewer_returns > 0 and tester_returns == 0:
        return "revisor"
    if assigned == "revisor" and tester_returns > 0 and reviewer_returns == 0:
        return "tester"
    if assigned == "desconhecido" and (tester_returns or reviewer_returns):
        if tester_returns >= reviewer_returns and subtype and "teste" in subtype:
            return "tester"
        if reviewer_returns > tester_returns and subtype and "revis" in subtype:
            return "revisor"
    return None


def _infer_responsible_party(
    subtype: str,
    assigned: str,
    card: dict[str, Any],
    *,
    external_cause: bool,
) -> str | None:
    if external_cause:
        return "processo/ambiente"
    return _party_from_assigned(assigned) or _party_from_subtype(subtype) or _party_from_card(card)


def _party_from_assigned(assigned: str) -> str | None:
    if assigned in {"tester", "revisor", "desconhecido"}:
        return assigned if assigned != "desconhecido" else None
    return None


def _party_from_subtype(subtype: str) -> str | None:
    if "teste" in subtype:
        return "tester"
    if "revis" in subtype:
        return "revisor"
    if "dev" in subtype:
        return "desenvolvedor"
    return None


def _party_from_card(card: dict[str, Any]) -> str | None:
    if int(card.get("return_dev_by_teste_count") or 0) > 0:
        return "tester"
    if int(card.get("return_dev_by_revisao_count") or 0) > 0:
        return "revisor"
    return None


def _fairness_headline(flags: list[str], responsible_party: str | None) -> str:
    if "movimento_para_retorno_possivelmente_indevido" in flags and responsible_party:
        return f"possivel retorno indevido por {responsible_party}"
    if "solucao_indica_causa_fora_do_codigo" in flags:
        return "retorno pode penalizar dev injustamente (causa externa na solucao)"
    if "subtipo_conflita_com_atribuicao_do_movimento" in flags:
        return "subtipo do retorno conflita com quem moveu o card"
    if "retorno_sem_motivo_valido" in flags:
        return "retorno sem motivo valido — metrica de qualidade comprometida"
    if flags:
        return flags[0].replace("_", " ")
    return ""


def _metric_impact_note(flags: list[str], responsible_party: str | None) -> str:
    if not flags:
        return ""
    if responsible_party in {"tester", "revisor"}:
        return (
            f"Pode inflar retrabalho/rework_rate do desenvolvedor e distorcer conformidade "
            f"de fluxo se o retorno foi movido indevidamente por {responsible_party}."
        )
    if "solucao_indica_causa_fora_do_codigo" in flags:
        return "Revisar se o card deveria contabilizar penalidade de qualidade ao desenvolvedor."
    if "retorno_sem_motivo_valido" in flags:
        return "Sem motivo/solucao confiaveis, a IA e as metricas nao conseguem atribuir causa justa."
    return "Pode afetar leitura justa de qualidade individual e do time."


def _is_placeholder_text(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _suggests_not_dev_fault(solution: str) -> bool:
    return any(marker in solution for marker in NOT_DEV_FAULT_MARKERS)


def _looks_misattributed(subtype: str, assigned: str) -> bool:
    if "teste" in subtype and assigned != "tester":
        return True
    if "revis" in subtype and assigned != "revisor":
        return True
    if assigned == "desconhecido" and subtype:
        return True
    return False


def _infer_injustice_reasons(
    motive: str,
    solution: str,
    flags: list[str],
    card: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    descricao = card.get("descricao") or {}
    solicitacao = _normalize_text(descricao.get("solicitacao") or descricao.get("solicitacao_analise"))

    if "solucao_indica_causa_fora_do_codigo" in flags:
        reasons.append(
            "A solucao registrada aponta causa externa (ambiente, dados, comportamento esperado) — "
            "nao parece falha de implementacao do desenvolvedor."
        )
    if "retorno_sem_motivo_valido" in flags:
        reasons.append("Retorno sem motivo valido — nao da para sustentar penalidade de qualidade ao dev.")
    if "motivo_vago_ou_generico" in flags:
        reasons.append("Motivo vago ou generico — tester/revisor pode nao ter documentado a causa real.")
    if "movimento_para_retorno_possivelmente_indevido" in flags:
        reasons.append("Quem moveu o card pode nao ser o responsavel pelo problema apontado no retorno.")
    if motive and any(marker in motive for marker in SCOPE_CREEP_MARKERS):
        reasons.append(
            "Motivo sugere expectativa fora do escopo original da solicitacao — possivel mudanca de requisito "
            "na fase de teste/revisao."
        )
    if motive and any(marker in motive for marker in TESTER_WANTED_DIFFERENT_MARKERS):
        reasons.append(
            "Motivo sugere que tester/revisor queria comportamento ou entrega diferente da tarefa acordada."
        )
    if solution and _suggests_not_dev_fault(solution):
        reasons.append(
            "Solucao contradiz o retorno: indica que o codigo/entrega estava correto ou que a causa nao era do dev."
        )
    if solicitacao and motive and len(motive) > 24:
        reasons.append(
            "Compare motivo com descricao.solicitacao do card — verifique se o retorno exige algo que nao estava "
            "no pedido original."
        )
    return reasons[:5]


def _highlight_card(card: dict[str, Any], flags: list[str], score: int) -> dict[str, Any]:
    retornos = card.get("retornos") or []
    pausas = card.get("pausas") or []
    descricao = card.get("descricao") or {}
    return {
        "card_id": card.get("card_id"),
        "card_name": card.get("card_name"),
        "sistema": card.get("sistema"),
        "kind": card.get("kind"),
        "desenvolvedor": card.get("desenvolvedor"),
        "tester": card.get("tester"),
        "solicitante": card.get("solicitante"),
        "severity_score": score,
        "flags": flags,
        "people": _card_people(card),
        "return_dev_count": card.get("return_dev_count"),
        "pause_count": card.get("pause_count"),
        "retornos": [
            {
                "numero": item.get("numero"),
                "tipo": item.get("tipo"),
                "subtipo": item.get("subtipo"),
                "motivo": _clip(item.get("motivo")),
                "solucao": _clip(item.get("solucao")),
                "atribuido_a": item.get("atribuido_a"),
                "fairness": _assess_retorno_fairness(item, card),
            }
            for item in retornos[:4]
        ],
        "pausas": [{"motivo": _clip(item.get("motivo"))} for item in pausas[:4]],
        "analise": {
            key: _clip(descricao.get(key))
            for key in (
                "solicitacao_analise",
                "analise_realizada",
                "recomendacao",
                "analise_origem",
            )
            if _normalize_text(descricao.get(key))
        },
    }


def _analysis_card_summary(card: dict[str, Any], flags: list[str]) -> dict[str, Any]:
    descricao = card.get("descricao") or {}
    _, score = _card_flags(card)
    return {
        "card_id": card.get("card_id"),
        "card_name": card.get("card_name"),
        "sistema": card.get("sistema"),
        "desenvolvedor": card.get("desenvolvedor"),
        "severity_score": score,
        "flags": flags,
        "return_dev_count": card.get("return_dev_count"),
        "solicitacao_analise": _clip(descricao.get("solicitacao_analise")),
        "analise_realizada": _clip(descricao.get("analise_realizada")),
        "recomendacao": _clip(descricao.get("recomendacao")),
        "retornos": len(card.get("retornos") or []),
        "pausas": len(card.get("pausas") or []),
    }


def _card_people(card: dict[str, Any]) -> list[str]:
    people = []
    for key in ("desenvolvedor", "tester", "solicitante", "revisor_par", "revisor"):
        value = _normalize_text(card.get(key))
        if value and value not in {"nao informado", "-"}:
            people.append(str(card.get(key)))
    return people


def _counter_rows(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def _clip(value: Any, limit: int = TEXT_LIMIT) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
