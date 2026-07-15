# Baseline de impacto — Metricas Trello

Como medir o efeito das correções e novas métricas (mesmo board + mesmo mês).

## 1. Antes de deploy (baseline)

```bash
python -m trello_metrics metrics --input data/trello_board_export.json --month YYYY-MM --output data/baseline_before.json
```

Guardar: `flow.team.lead_time`, `sla.team.compliance_pct`, `developers[].acceptance_rate_pct`, reteste, `data_quality.unknown_lists`.

## 2. Depois de P0 (fórmulas + calendário)

| Indicador | Esperado |
|-----------|----------|
| Lead/SLA com arquivados | Horas caem (C2) |
| Aceitação pós-retorno terminal | Sobe (C1) |
| Reteste com 1 ciclo | ~0 |
| Feriado / HE cadastrado | `calendar_applied` no payload |
| Listas renomeadas | `data_quality.unknown_lists` |

## 3. Depois de P1

- `flow.aging_baseline`, `first_time_right`, `rework_ratio`, `net_flow`, `flow_efficiency_distribution`, `blocked_time`
- Aparecem no preview gestão, HTML e PDF

## 4. Depois de P2

- `member_assignment`, `due_predictability`, `board_moves`
- Cards `moved_out` encerram span (não congelam WIP)

## 5. Guardrails

- `pytest tests/`
- Sync das 3 cópias de `metric_definitions.json` no CI
- `python manage.py migrate` (0004 calendário)
