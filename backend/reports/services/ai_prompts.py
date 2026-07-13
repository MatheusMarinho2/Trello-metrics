from __future__ import annotations

from typing import Literal

FIVE_CORE_QUESTIONS = [
    "O que melhorou neste mes em relacao a tendencia recente (qualidade, entrega, fluxo)?",
    "Onde estamos perdendo qualidade, tempo ou previsibilidade?",
    "Quem se destacou positivamente e quem precisa de apoio objetivo?",
    "Quais riscos, gargalos ou violacoes de processo ameacam o proximo ciclo?",
    "O que fazer nas proximas 2 semanas para elevar qualidade e previsibilidade?",
]

SYSTEM_PROMPT = """Voce e analista senior de engenharia e operacoes da INTGEST.
Regras obrigatorias:
- Escreva em portugues do Brasil, tom profissional, direto e justo.
- Use SOMENTE evidencias do JSON fornecido; se faltar dado, diga explicitamente.
- Nunca invente numeros, nomes ou eventos.
- Cite metricas concretas (percentuais, quantidades, prazos) quando existirem.
- Separe fato de interpretacao; seja acionavel para gestao.
- Ao analisar retornos e pausas, seja justo: diferencie falha de processo, registro incompleto e responsabilidade individual.
- Leia motivo E solucao de cada retorno em returns_pauses_insights.questionable_returns.
- Para retorno possivelmente indevido, cite o motivo literal, explique por que nao faz sentido (escopo, tester queria outra coisa, solucao contradiz motivo, ambiente/dados) e informe card_id do Trello.
- Use injustice_reasons do JSON como pistas, mas redija a analise em linguagem clara para gestao.
- Em highlight_cards e questionable_returns, SEMPRE inclua ID Trello (card_id) nos cards que merecem atencao.
- Se should_review_dev_metrics=true, diga explicitamente que o rework/retrabalho do desenvolvedor pode ser revisado.
- Se houver evidencia de retorno indevido (tester/revisor moveu errado, motivo vazio, solucao aponta causa externa), diga explicitamente e explique o impacto nas metricas do desenvolvedor.
- Nao culpe o desenvolvedor quando questionable_returns ou metric_impact_note indicarem distorcao.
- Use returns_pauses_insights para padroes (motivos comuns) e highlight_cards para exemplos concretos.
- Use flow_column_insights para apontar colunas/etapas com maior inconsistencia (SLA, retrocesso, WIP, gargalo).
- Use antifraud / antifraud_insights para apontar possiveis fraudes por copia de cards (reset de metricas).
- Ignore copias de template (whitelist) e copias de outro board para este (cross_board_copies_count / import legitimo).
- So trate como suspeita copia em que a fonte ja existia neste mesmo board e foi reiniciada (ex.: copiada para planejamento e/ou excluida/arquivada).
- Nao acuse fraude sem evidencia no JSON.
- Se source_status for missing_history, deleted* ou archived*, diga que o historico da fonte esta incompleto/excluido/arquivado — nao invente listas visitadas.
- Em alertas antifraude, SEMPRE cite card_id do card novo e, se houver, source_card_id.
- Nao exponha dados sensiveis alem do necessario.
- Siga EXATAMENTE a estrutura markdown solicitada no prompt do usuario."""

REPORT_INSTRUCTIONS: dict[str, str] = {
    "general": (
        "Relatorio GERAL do time. Analise entrega, qualidade, fluxo, SLA, DORA, disciplina "
        "de processo, antifraude (copias suspeitas) e TODAS as pessoas em collaborators_names."
    ),
    "management": (
        "Relatorio de GESTAO. Foque em indicadores estrategicos: fluxo, SLA, gargalos, "
        "DORA, risco, tendencia 6 meses, qualidade de processo e antifraude/copias suspeitas. "
        "Resuma colaboradores apenas se houver sinal forte (top 5 positivos e top 5 atencao)."
    ),
    "individual": (
        "Relatorio INDIVIDUAL de um colaborador. Aprofunde apenas a pessoa alvo. "
        "Use role_metrics e indicadores consolidados. Minimo 5 positivos e 5 negativos/lacunas."
    ),
    "developers": (
        "Relatorio de DESENVOLVEDORES. Foque entregas, pontos, retrabalho, SLA e qualidade. "
        "Bloco por desenvolvedor com positivos e negativos."
    ),
    "testers": (
        "Relatorio de TESTERS. Foque testes, 1a passagem, problemas evitados, retestes. "
        "Bloco por tester com positivos e negativos."
    ),
    "requesters": (
        "Relatorio de SOLICITANTES. Foque criacao, entrega, planejamento e demanda. "
        "Bloco por solicitante com positivos e negativos."
    ),
    "specific_metrics": (
        "Relatorio de METRICAS ESPECIFICAS. Responda as 5 perguntas apenas sobre "
        "as secoes presentes no JSON."
    ),
}

COLLABORATOR_REPORT_TYPES = frozenset({"general", "developers", "testers", "requesters"})

TWO_PART_REPORT_TYPES = frozenset(
    {"general", "individual", "management", "developers", "testers", "requesters"}
)

PromptPart = Literal["full", "first", "second"]


def build_user_prompt(
    *,
    report_type: str,
    month: str,
    collaborator_name: str,
    metrics_json: str,
    include_collaborators_section: bool = True,
    collaborators_total: int = 0,
    part: PromptPart = "full",
    first_part_text: str = "",
) -> str:
    if part == "first":
        return _build_first_part_prompt(
            report_type=report_type,
            month=month,
            collaborator_name=collaborator_name,
            metrics_json=metrics_json,
            collaborators_total=collaborators_total,
        )
    if part == "second":
        return _build_second_part_prompt(
            report_type=report_type,
            month=month,
            collaborator_name=collaborator_name,
            metrics_json=metrics_json,
            include_collaborators_section=include_collaborators_section,
            collaborators_total=collaborators_total,
            first_part_text=first_part_text,
        )
    scope = REPORT_INSTRUCTIONS.get(report_type, REPORT_INSTRUCTIONS["general"])
    questions = "\n".join(f"{index}. {question}" for index, question in enumerate(FIVE_CORE_QUESTIONS, start=1))
    collaborator_block = _collaborators_section_instructions(collaborators_total) if include_collaborators_section else (
        "\n## Colaboradores\n"
        "(Esta secao sera gerada em etapa separada — NAO inclua ## Colaboradores nesta resposta.)\n"
    )

    return f"""Gere a analise INTGEST seguindo o padrao abaixo.

## Escopo
- Tipo: {report_type}
- Mes: {month}
- Colaborador alvo: {collaborator_name or "nao se aplica"}
- Colaboradores no JSON: {collaborators_total or "ver collaborators_total"}
- Instrucao: {scope}

## As 5 perguntas-chave (responda todas com evidencias detalhadas)
{questions}

## Estrutura OBRIGATORIA da resposta (markdown)

# Analise INTGEST — {month}

## Resumo executivo
(4 a 6 frases: situacao do mes, evolucao vs tendencia, principal ganho, principal risco e leitura de capacidade)

## Respostas as 5 perguntas-chave
### 1. O que melhorou?
(minimo 4 bullets com numeros)
### 2. Onde perdemos qualidade ou tempo?
(minimo 4 bullets com numeros)
### 3. Quem destacou e quem precisa de apoio?
(nomeie pessoas e cite metricas)
### 4. Quais riscos ameacam o proximo ciclo?
(gargalos, SLA, DORA, violacoes de fluxo)
### 5. Plano para as proximas 2 semanas
(acoes priorizadas, donos sugeridos quando possivel)

## Time — visao consolidada
### Pontos positivos
- (minimo 5 bullets com metrica)
### Pontos de atencao
- (minimo 5 bullets com metrica)
### Evolucao vs meses anteriores
- (use trends_6m; compare entregas, qualidade e gargalo)

## Leitura operacional aprofundada
### Fluxo e previsibilidade
- lead time, cycle time, WIP, gargalo principal
- use flow_column_insights: colunas com maior inconsistencia, sinais e principal_flow_problems

## Problemas do fluxo por coluna
(Obrigatorio se flow_column_insights existir)
### Mapa de inconsistencias
- ranqueie as colunas/etapas de columns_ranked_by_inconsistency (nome da coluna, score, sinais)
- cite principal_flow_problems e top_bottleneck
### O que esta acontecendo em cada coluna critica
- para as 3 a 5 piores: WIP, SLA, retrocesso, etapa pulada, campos faltantes, cards parados (stuck_cards_sample)
### Leitura justa e acionavel
- separe gargalo real vs. registro vs. violacao de processo
- proponha 3 acoes para as colunas mais problematicas

### Qualidade e processo
- retrabalho, dupla revisao, conformidade de fluxo, SLA
### Entrega e valor
- cards entregues, pontos Fibonacci, DORA (se existir)

## Antifraude / copias suspeitas
(Obrigatorio se antifraud ou antifraud_insights existir no JSON)
### Panorama
- copies_in_period, whitelisted_copies_count, high_count, medium_count
### Alertas relevantes
- liste alertas high e medium com **card_id**, nome, fonte, score, flags e motivo
- diga se a fonte passou por terminal, foi excluida/arquivada ou esta com missing_history
- separe copia de template (whitelist, nao e fraude) de clone suspeito de reset de metricas
### Impacto e acao
- explique como a copia pode distorcer entregas/SLA/qualidade do periodo
- proponha 2-3 acoes de auditoria (revisar card, validar exclusao da fonte, alinhar processo)

## Retornos, pausas e cards de analise
(Obrigatorio se returns_pauses_insights existir no JSON)
### Panorama do mes
- cards com retorno, cards com pausa, eventos totais, taxa de retrabalho do time
### Motivos, solucoes e padroes
- principais motivos (top_return_motives), subtipos e pares motivo+subtipo
- solucoes registradas (top_return_solutions) — verifique se confirmam ou contradizem o motivo
### Justica na analise de retornos
- use return_fairness_summary e questionable_returns
- OBRIGATORIO: para cada retorno com possibly_unfair_to_developer=true, gere bloco em blockquote (>) com:
  - **Card:** nome · **ID Trello:** `card_id`
  - **Motivo registrado:** (texto literal)
  - **Solucao registrada:** (texto literal)
  - **Quem moveu:** atribuido_a / responsible_party_suspected
  - **Por que provavelmente nao faz sentido:** 2-4 frases (escopo, tester queria funcionalidade diferente, motivo vago, solucao contradiz, ambiente/dados)
  - **Impacto na metrica do dev:** rework/retrabalho/qualidade — use metric_impact_note
  - **Acao sugerida:** revisar se deve abater penalidade do desenvolvedor
- para cada caso relevante: motivo, solucao, quem moveu (atribuido_a), se parece indevido e impacto nas metricas
- exemplo permitido: "tester voltou card indevidamente — motivo vago, solucao indica ambiente; penaliza rework do dev"
- nao atribua culpa ao desenvolvedor sem evidencia no motivo/solucao/movimento
### Cards de analise (kind=analysis)
- qualidade do preenchimento (analise_realizada, recomendacao), retornos indevidos, lacunas
### Cards que merecem atencao
- cite ate 8 cards de highlight_cards com **nome**, **ID Trello (`card_id`)**, flags e evidencia em 1-2 frases
- inclua casos de possivel retorno mal atribuido, reteste, dupla revisao violada ou analise incompleta
### Recomendacoes objetivas
- 3 a 5 acoes para reduzir retornos evitaveis e pausas recorrentes

## Revisao de qualidade e conformidade
- dupla revisao, campos obrigatorios, violacoes de fluxo (process_discipline / quality_gates)
- impacto na previsibilidade e no custo de retrabalho

{collaborator_block}

## Qualidade da entrega
- Selo, retrabalho, dupla revisao, SLA, DORA — somente o que existir no JSON

## Conclusao para gestao
(3 a 4 frases objetivas sobre ganhos do mes, upgrade da equipe e proximo foco)

---
JSON de metricas (fonte unica de verdade):
{metrics_json}
"""


def _build_first_part_prompt(
    *,
    report_type: str,
    month: str,
    collaborator_name: str,
    metrics_json: str,
    collaborators_total: int,
) -> str:
    scope = REPORT_INSTRUCTIONS.get(report_type, REPORT_INSTRUCTIONS["general"])
    questions = "\n".join(f"{index}. {question}" for index, question in enumerate(FIVE_CORE_QUESTIONS, start=1))
    return f"""Gere a PARTE 1 da analise INTGEST (continuacao virá em etapa separada).

## Escopo
- Tipo: {report_type}
- Mes: {month}
- Colaborador alvo: {collaborator_name or "nao se aplica"}
- Colaboradores no JSON: {collaborators_total or "ver collaborators_total"}
- Instrucao: {scope}

## As 5 perguntas-chave (responda todas com evidencias detalhadas)
{questions}

## Estrutura OBRIGATORIA desta PARTE 1 (markdown)
NAO inclua retornos/pausas, colaboradores individuais nem conclusao — isso vem na Parte 2.

# Analise INTGEST — {month}

## Resumo executivo
(4 a 6 frases completas)

## Respostas as 5 perguntas-chave
### 1. O que melhorou?
(minimo 4 bullets com numeros)
### 2. Onde perdemos qualidade ou tempo?
(minimo 4 bullets com numeros)
### 3. Quem destacou e quem precisa de apoio?
(nomeie pessoas e cite metricas)
### 4. Quais riscos ameacam o proximo ciclo?
(gargalos, SLA, DORA, violacoes de fluxo)
### 5. Plano para as proximas 2 semanas
(acoes priorizadas, donos sugeridos quando possivel)

## Time — visao consolidada
### Pontos positivos
- (minimo 5 bullets com metrica)
### Pontos de atencao
- (minimo 5 bullets com metrica)
### Evolucao vs meses anteriores
- (use trends_6m)

## Leitura operacional aprofundada
### Fluxo e previsibilidade
- lead time, cycle time, WIP, gargalo principal
- use flow_column_insights

## Problemas do fluxo por coluna
(Obrigatorio se flow_column_insights existir)
### Mapa de inconsistencias
### O que esta acontecendo em cada coluna critica
### Leitura justa e acionavel

### Qualidade e processo
- retrabalho, dupla revisao, conformidade de fluxo, SLA
### Entrega e valor
- cards entregues, pontos Fibonacci, DORA (se existir)

---
JSON de metricas:
{metrics_json}
"""


def _build_second_part_prompt(
    *,
    report_type: str,
    month: str,
    collaborator_name: str,
    metrics_json: str,
    include_collaborators_section: bool,
    collaborators_total: int,
    first_part_text: str,
) -> str:
    scope = REPORT_INSTRUCTIONS.get(report_type, REPORT_INSTRUCTIONS["general"])
    tail = (first_part_text or "").strip()
    if len(tail) > 1200:
        tail = tail[-1200:]
    individual_note = ""
    collaborator_block = ""
    if report_type == "individual" and collaborator_name:
        individual_note = f"""
## Resumo individual — {collaborator_name}
(Obrigatorio: bloco dedicado a {collaborator_name} com minimo 5 positivos e 5 negativos/lacunas, retornos/pausas e recomendacao pratica)
"""
    elif include_collaborators_section:
        collaborator_block = _collaborators_section_instructions(collaborators_total)
    else:
        collaborator_block = (
            "\n## Colaboradores\n"
            "(Ja gerado em etapa separada — NAO inclua ## Colaboradores.)\n"
        )

    return f"""Continue a analise INTGEST — PARTE 2 de 2.
A Parte 1 ja foi gerada; mantenha coerencia e NAO repita secoes da Parte 1.

## Escopo
- Tipo: {report_type}
- Mes: {month}
- Colaborador alvo: {collaborator_name or "nao se aplica"}
- Instrucao: {scope}

## Final da Parte 1 (contexto)
...
{tail}

## Estrutura OBRIGATORIA desta PARTE 2 (markdown)
Comece direto em ## Retornos, pausas e cards de analise (sem repetir titulo # Analise).

## Retornos, pausas e cards de analise
(Obrigatorio se returns_pauses_insights existir no JSON)
### Panorama do mes
### Motivos, solucoes e padroes
### Justica na analise de retornos
(Obrigatorio se questionable_returns existir — use blockquote `>` por retorno indevido)
### Cards de analise (kind=analysis)
### Cards que merecem atencao
(cada card com ID Trello em backticks)
### Recomendacoes objetivas

## Antifraude / copias suspeitas
(Obrigatorio se antifraud ou antifraud_insights existir no JSON)
### Panorama
### Alertas high/medium com card_id e source_status
### Impacto em metricas e acoes de auditoria

## Revisao de qualidade e conformidade
- dupla revisao, campos obrigatorios, violacoes de fluxo

{individual_note}
{collaborator_block}

## Qualidade da entrega
- Selo, retrabalho, dupla revisao, SLA, DORA

## Conclusao para gestao
(3 a 4 frases objetivas — OBRIGATORIO encerrar esta secao)

---
JSON de metricas:
{metrics_json}
"""


def build_collaborator_batch_prompt(
    *,
    report_type: str,
    month: str,
    metrics_json: str,
    batch_names: list[str],
    batch_index: int,
    batch_total: int,
    collaborators_total: int,
) -> str:
    names_list = "\n".join(f"- {name}" for name in batch_names)
    return f"""Gere SOMENTE os blocos de colaboradores deste lote para o relatorio INTGEST.

## Contexto
- Tipo: {report_type}
- Mes: {month}
- Lote: {batch_index}/{batch_total}
- Total de colaboradores no relatorio: {collaborators_total}

## Nomes OBRIGATORIOS neste lote (gere um bloco para CADA um, nesta ordem)
{names_list}

## Formato OBRIGATORIO por pessoa (markdown)

### Nome exato do colaborador
- **Papeis:** (lista)
- **Numeros-chave:** cards entregues/criados/ativos, pontos, qualidade, retrabalho, violacoes de fluxo
- **Positivos:** (minimo 4 bullets com evidencia numerica)
- **Negativos / lacunas:** (minimo 4 bullets com evidencia numerica)
- **Retornos e pausas:** (returns_pauses_highlights + questionable_returns do lote; cite motivo/solucao e se houve injustica)
- **Comparacao com o time:** (1-2 frases usando team_summary ou medias)
- **Recomendacao pratica:** (1 acao clara e mensuravel)

Regras:
- Nao pule nenhum nome do lote.
- Nao invente dados ausentes — declare a lacuna.
- Use role_metrics e summary de cada colaborador no JSON.

---
JSON do lote:
{metrics_json}
"""


def _collaborators_section_instructions(collaborators_total: int) -> str:
    if collaborators_total <= 0:
        return """
## Colaboradores
(Gere bloco para cada pessoa em collaborators_names do JSON)
"""
    return f"""
## Colaboradores
OBRIGATORIO: o JSON traz collaborators_total={collaborators_total}.
Gere EXATAMENTE {collaborators_total} subsecoes ### (uma por nome em collaborators_names).
Nao resuma apenas um colaborador — inclua TODOS.
Para cada pessoa:
### Nome
- **Papeis:**
- **Numeros-chave:**
- **Positivos:** (minimo 4 bullets)
- **Negativos / lacunas:** (minimo 4 bullets)
- **Retornos e pausas:** (se houver cards ou metricas da pessoa)
- **Comparacao com o time:**
- **Recomendacao pratica:**
"""


def build_management_user_prompt(
    *,
    month: str,
    metrics_json: str,
    part: PromptPart = "full",
    first_part_text: str = "",
) -> str:
    if part == "first":
        return f"""Gere a PARTE 1 da analise de GESTAO INTGEST.

## Escopo
- Relatorio estrategico para lideranca — sem blocos individuais de colaboradores.

## Estrutura OBRIGATORIA PARTE 1

# Analise de Gestao INTGEST — {month}

## Resumo executivo
(5-7 frases: situacao, tendencia trends_6m, principal ganho, principal risco, capacidade)

## Indicadores estrategicos
### Entrega e qualidade (team_summary)
### Fluxo e capacidade (flow, bottlenecks, WIP, Little)
### SLA e risco (sla, risk_board)
### DORA (deployment_frequency.by_path, change_failure_rate + cfr_note — explique que CFR e proxy)
### Disciplina de processo (process_discipline, post_terminal_returns)
### Cards de analise (analysis_workflow)
### Prioridade e demanda (priority, projects)

## Regras de negocio observadas no periodo
- Diretamente na producao: hotfix para master; pode sair de Em andamento, Revisao em par ou Em revisao; sem teste/homolog; retorno apos terminal e violacao.
- Analise: dev -> Analises para planejamento -> solicitante -> finalizado ou novo card.
- Retorno pos-producao/analise finalizada: deve abrir novo card.

## Decisoes sugeridas para gestao
(minimo 5 acoes priorizadas com dono sugerido)

---
JSON:
{metrics_json}
"""

    if part == "second":
        tail = (first_part_text or "").strip()[-1200:]
        return f"""Gere a PARTE 2 da analise de GESTAO INTGEST.

## Final da Parte 1
...
{tail}

## Estrutura OBRIGATORIA PARTE 2
Comece em ## Retornos, pausas e justica operacional

## Retornos, pausas e justica operacional
(questionable_returns, post_terminal_returns, highlight_cards com card_id)

## Problemas do fluxo por coluna
(flow_column_insights)

## Evolucao vs meses anteriores
(trends_6m — compare entregas, qualidade, SLA, CFR)

## Top 5 sinais positivos e Top 5 alertas
(pessoas ou areas — max 1 linha cada, sem blocos longos por colaborador)

## Conclusao para gestao
(4 frases objetivas)

---
JSON:
{metrics_json}
"""

    return f"""Gere analise de GESTAO INTGEST completa (1 chamada).

Relatorio estrategico para lideranca — sem blocos individuais de colaboradores.

# Analise de Gestao INTGEST — {month}

Inclua: resumo executivo, indicadores (team_summary, flow, SLA, DORA com by_path e cfr_note, process_discipline, analysis_workflow, priority), regras de negocio (direct_production, terminal irreversivel), decisoes sugeridas, retornos/pausas, fluxo por coluna, trends_6m, top 5 positivos/alertas, conclusao.

---
JSON:
{metrics_json}
"""
