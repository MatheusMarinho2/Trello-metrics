"""Renderização HTML de blocos de card (dossiê)."""
from __future__ import annotations

from typing import Any

from . import helpers as H
from .helpers import badge, esc, md

_DESCRICAO_LABELS: dict[str, str] = {
    "cliente": "Cliente",
    "solicitacao": "Solicitacao",
    "solucao_dev": "Solucao do desenvolvedor",
    "obs_revisor_par": "Observacoes do revisor em par",
    "obs_revisor": "Observacoes do revisor",
    "obs_tester": "Observacoes do tester",
    "observacoes": "Observacoes gerais",
    "observacoes_gerais": "Observacoes gerais",
    "solicitacao_analise": "Solicitacao da analise",
    "analise_realizada": "Analise realizada",
    "recomendacao": "Recomendacao",
    "analise_origem": "Analise que originou",
}

_DESC_ORDER = list(_DESCRICAO_LABELS.keys())


def _kind_meta(kind: str) -> tuple[str, str]:
    return {"problem": ("Problema", "#C62828"), "analysis": ("Analise", "#428BA5")}.get(
        kind, ("Tarefa", "#133968")
    )


def _meta_field(label: str, val) -> str:
    if val and val != "Nao informado":
        shown = H.dev_name(val)
    elif val == "Nao informado":
        shown = "Nao informado"
    else:
        shown = "—"
    return f'<div class="rt-mf"><span class="rt-mf-k">{label}</span><span class="rt-mf-v">{esc(shown)}</span></div>'


def render_card_block(card: dict[str, Any]) -> str:
    kl, kc = _kind_meta(card.get("kind", ""))
    meta = (
        '<div class="rt-cd-meta">'
        + _meta_field("Solicitante", card.get("solicitante"))
        + _meta_field("Dev", card.get("desenvolvedor"))
        + _meta_field("Revisor em par", card.get("revisor_par"))
        + _meta_field("Revisor", card.get("revisor"))
        + _meta_field("Tester", card.get("tester"))
        + "</div>"
    )
    chip_data = [
        ("Lead time", card.get("lead_time_human")),
        ("Tempo de entrega", card.get("cycle_time_human")),
        ("Trabalho DEV", card.get("dev_work_human")),
        ("Retornos DEV", str(card.get("return_dev_count", card.get("return_dev_by_teste_count", 0)))),
        ("Retestes", str(card.get("retest_cycles", 0))),
        ("Pausas", str(card.get("pause_count", 0))),
    ]
    chips = "".join(
        f'<div class="rt-chip"><span class="rt-chip-v">{esc(v or "—")}</span>'
        f'<span class="rt-chip-k">{k}</span></div>'
        for k, v in chip_data
    )
    desc = ""
    dd = card.get("descricao") or {}
    for key in _DESC_ORDER:
        v = dd.get(key)
        if not v or not str(v).strip():
            continue
        if key == "analise_origem" and str(v).lower().startswith("link do card"):
            continue
        desc += (
            f'<div class="rt-descblock"><div class="rt-desc-lab">{_DESCRICAO_LABELS.get(key, key)}</div>'
            f'<div class="rt-desc-body">{md(str(v).strip())}</div></div>'
        )
    etapas = "".join(
        f'<div class="rt-etapa"><span class="rt-etapa-n">{i + 1}</span>'
        f'<span class="rt-etapa-t">{esc(e.get("title", "-"))}</span>'
        f'<span class="rt-etapa-h">{esc(e.get("hours_human", "-"))}</span></div>'
        for i, e in enumerate(card.get("etapas") or [])
    )
    level = card.get("fibonacci_level")
    tags = (
        badge(kl, kc)
        + badge(esc(card.get("sistema")), H.NAVY)
        + badge(f"Nivel {level if level is not None else '—'}", "#275362")
    )
    extra = ""
    if card.get("collaborator_roles"):
        roles = "".join(H.role_chip(r) for r in card["collaborator_roles"])
        extra += f'<div class="rt-card-rolewrap">{roles}</div>'
    involvements = card.get("collaborator_involvements") or []
    if involvements:
        inv_html = ""
        for item in involvements:
            stages = item.get("stages") or []
            stage_text = "; ".join(
                f"{esc(s.get('title', '-'))}: {esc(s.get('hours_human', '-'))}" for s in stages
            ) or "Sem tempo registrado"
            inv_html += (
                f'<div class="rt-involve"><div class="rt-involve-role">{esc(item.get("role_label", "-"))} '
                f'<span class="rt-involve-alias">({esc(item.get("alias", "-"))})</span></div>'
                f'<div class="rt-involve-time">{esc(item.get("time_human", "-"))}</div>'
                f'<div class="rt-involve-stages">{stage_text}</div></div>'
            )
        total = esc(card.get("collaborator_time_human", "-"))
        extra += f'<div class="rt-involve-wrap"><div class="rt-subttl">Atuacao do colaborador ({total})</div>{inv_html}</div>'
    if card.get("double_review_required"):
        status = "com dupla revisao" if card.get("double_review_done") else "SEM dupla revisao (violacao)"
        extra += f'<div class="rt-review-flag">Dupla revisao obrigatoria (nivel 8/13): {esc(status)}.</div>'
    elif card.get("double_review_recommended"):
        status = "com dupla revisao" if card.get("double_review_done") else "sem dupla revisao"
        extra += f'<div class="rt-review-flag">Dupla revisao recomendada (nivel 5): {esc(status)}.</div>'
    events = ""
    for retorno in card.get("retornos") or []:
        tipo = "Desenvolvimento" if retorno.get("tipo") == "dev" else "Suporte/Teste"
        subtipo = f" ({retorno['subtipo']})" if retorno.get("subtipo") else ""
        motivo = retorno.get("motivo") or "motivo nao registrado"
        solucao = retorno.get("solucao") or "solucao nao registrada"
        atribuido = retorno.get("atribuido_a") or "desconhecido"
        events += (
            f'<div class="rt-retorno">Retorno {retorno.get("numero", "?")} ({esc(tipo)}{esc(subtipo)}): '
            f'{esc(motivo)} — Solucao: {esc(solucao)} — Atribuido a: {esc(atribuido)}</div>'
        )
    for pausa in card.get("pausas") or []:
        motivo = pausa.get("motivo") or "motivo nao registrado"
        events += f'<div class="rt-pausa">Pausa {pausa.get("numero", "?")}: {esc(motivo)}</div>'
    events_html = f'<div class="rt-events-wrap">{events}</div>' if events else ""
    desc_html = f'<div class="rt-descs">{desc}</div>' if desc else ""
    etapas_html = (
        f'<div class="rt-etapas-wrap"><div class="rt-desc-lab">Etapas do fluxo</div><div class="rt-etapas">{etapas}</div></div>'
        if etapas else ""
    )
    card_id = card.get("id_short", "")
    id_html = f'<div class="rt-card-id">#{esc(card_id)}</div>' if card_id else ""
    return (
        f'<div class="rt-card"><div class="rt-card-head">{id_html}'
        f'<div class="rt-card-ttl">{esc(card.get("card_name"))}</div></div>'
        f'<div class="rt-card-tags">{tags}</div>{extra}{meta}'
        f'<div class="rt-chips">{chips}</div>{desc_html}{etapas_html}{events_html}</div>'
    )
