# Guia de nivelamento de tarefas (INTGEST)

Este guia é para **desenvolvedores** definirem o **Nível** (Fibonacci) de cards de problema e o **Nível (Análise)** de cards de análise, em projetos Django com regras de negócio críticas.

Política de SLA e medição: [sla_medicacao_e_niveis.md](sla_medicacao_e_niveis.md).

---

## Resumo executivo

| Campo Trello | Tipo de card | Quando preencher | O que controla |
|--------------|--------------|------------------|----------------|
| **Nível** | Problema (`PM CLIENTE`, `PROBLEMA`) | **Antes** de mover para **EM ANDAMENTO** | SLA de desenvolvimento + pontos Fibonacci + dupla revisão |
| **Nível (Análise)** | Análise (`ANALISE`, `ANALISES`) | **Depois** da análise, **antes** de mover para **ANALISES PARA PLANEJAMENTO** | SLA da fila de planejamento |
| **Prioridade** | Ambos | Sempre que houver urgência | SLA de **RETORNO (DEV/SUP)** — **não** substitui Nível |

**Regra de ouro:** use o **menor** nível Fibonacci que ainda descreve o **risco real**. Inflacionar nível é considerado **distorção de métrica**, não “margem de segurança”.

---

## Como o nível vira métrica (o que o sistema faz)

O relatório mensal lê o Trello automaticamente. O nível informado **não é opinião da gestão** — alimenta cálculos objetivos.

### Cards de problema — campo **Nível**

| Nível | SLA em **EM ANDAMENTO** | Pontos Fibonacci (na entrega) | Dupla revisão |
|-------|-------------------------|-------------------------------|---------------|
| 1 | 1 h útil | 1 | Opcional |
| 2 | 2 h úteis | 2 | Opcional |
| 3 | 4 h úteis | 3 | Opcional |
| 5 | 12 h úteis | 5 | **Recomendada** (par + formal) |
| 8 | 27 h úteis | 8 | **Obrigatória** — violação aparece no relatório |
| 13 | 44 h úteis | 13 | **Obrigatória** — violação aparece no relatório |

- **Horas úteis:** seg–sex, 08:00–18:00 (qui/sex até 17:30), almoço 12:00–13:00 **não conta**. Fim de semana e noite **não contam**.
- O cronômetro de SLA **só corre enquanto o card está na coluna** (ex.: sai de Em andamento → para).
- **Sem Nível preenchido:** card entra na lista de **disciplina de processo** (campo obrigatório ausente) e **não gera** check de SLA de desenvolvimento.
- **Pontos Fibonacci:** creditados **somente ao desenvolvedor** (prefixo `D-`) **na entrega**. Revisor, tester e solicitante **não** acumulam pontos.
- Cards com label **NAO METRICAR** / **CONTROLE** são ignorados.

### Cards de análise — campo **Nível (Análise)**

| Nível (Análise) | SLA em **ANALISES PARA PLANEJAMENTO** | Pontos (na entrega) |
|-----------------|---------------------------------------|---------------------|
| 1 | 30 min úteis | 1 |
| 2 | 1 h útil | 2 |
| 3 | 2 h úteis | 3 |

- Mede quanto tempo a análise **fica aguardando absorção pelo planejamento** — **não** o tempo que você levou escrevendo a análise.
- **Sem Nível (Análise):** coluna **não gera** check de SLA.

### O que inflacionar nível **realmente** muda

| Efeito | Inflacionar (ex.: 3 → 8) | Nivelar certo (3) |
|--------|--------------------------|-------------------|
| Tempo permitido em Em andamento | **Aumenta** (4 h → 27 h) | Adequado ao risco |
| Pontos na entrega | **Aumenta** (3 → 8) | Reflete esforço real |
| Ranking / produtividade do time | **Distorce** a favor de quem inflaciona | Comparável entre devs |
| Dupla revisão | Pode **obrigar** par + formal (≥ 8) | Só o processo necessário |
| Previsão de capacidade do time | **Superestima** complexidade | Planejamento confiável |

**Conclusão:** subir nível “para ter tempo” ou “para pontuar mais” **prejudica o time inteiro** e é rastreável no relatório (pontos altos com entregas simples, violações de revisão, outliers por desenvolvedor).

**Prioridade** (`Crítica`, `Urgente`, `Alta`) afeta **apenas retornos** — use para urgência, **nunca** como substituto de Nível.

---

## Protocolo anti-inflação (obrigatório)

Siga **nesta ordem** antes de salvar o nível no card.

### Passo 1 — Teste dos 4 “nãos”

Se **3 ou mais** forem verdade, **proibido** usar nível **5+** sem bloco de justificativa (Passo 3):

1. Consigo descrever a mudança em **≤ 2 frases** objetivas?
2. Afeta **≤ 1** tela / view / queryset?
3. Teste manual em homolog leva **< 30 min**?
4. **Não** mexe em fluxo crítico nem altera dado já persistido em produção?

### Passo 2 — Teste de equivalência

Pergunte: *“Se outro dev honesto nivelasse este card, qual seria o nível **mínimo**?”*

- Se a resposta for **2 níveis abaixo** do que você ia colocar → **use o mínimo**.
- **Proibido pular degraus:** 1 → 2 → 3 → 5 → 8 → 13. Não vá direto a 8 ou 13 “por precaução”.

### Passo 3 — Justificativa escrita (nível ≥ 5)

Cole **no corpo do card** antes de mover para Em andamento:

```text
## Nivelamento
- Nivel escolhido: X
- Criterios atendidos (marcar 2+ para 5/8, todos para 13):
  - [ ] ...
- Por que NAO cabe no nivel anterior:
  - ...
- Escopo fechado (o que NAO entra):
  - ...
```

Gestão e revisores usam este bloco em caso de dúvida. Card nível 5+ **sem** este bloco = nivelamento incompleto.

### Passo 4 — Separar urgência de complexidade

| Situação | Campo correto | Campo errado |
|----------|---------------|--------------|
| Cliente pressionando prazo | **Prioridade** ↑ | Nível ↑ |
| Card voltou de retorno | **Prioridade** + correção | Nível ↑ retroativo |
| “Vai demorar porque estou ocupado” | WIP / fila | Nível ↑ |
| Migration simples nullable | Nível **3** | Nível **8** “porque tem migration” |

---

## Princípios

1. **Nível = esforço + risco + impacto**, não tempo de codar, fila cheia nem folga de prazo.
2. **Regra de ouro:** menor Fibonacci que descreve o risco **real**.
3. Na dúvida entre dois níveis → **comece pelo menor**; suba **só** se marcar critério **obrigatório** do nível superior.
4. Migration, permissão, signal ou integração **não sobem o nível automaticamente** — avalie escopo e impacto.
5. Nivelar errado penaliza quem acerta: SLA injusto, ranking distorcido, revisão desproporcional.

---

## Árvore de decisão (cards problema)

```
Comece sempre avaliando se cabe em 1 ou 2.

┌─ Typo, copy, label, config isolada, 1 linha sem efeito colateral?
│  ──► Nível 1
│
├─ Bug com causa conhecida, 1 arquivo, sem migration?
│  ──► Nível 2
│
├─ Regra local (form/view/service), 1 app, migration aditiva simples?
│  ──► Nível 3
│
├─ Feature nova completa OU módulo novo OU impacto diário em 1 sistema?
│  (precisa 2+ critérios obrigatórios do 5)
│  ──► Nível 5
│
├─ 3+ apps OU integração/celery com efeito em cascata OU API breaking?
│  (precisa 2+ critérios obrigatórios do 8)
│  ──► Nível 8
│
└─ Fluxo core institucional (votação, pauta, auth, publicação oficial)
   — parada = operação comprometida?
   (precisa TODOS os critérios do 13)
   ──► Nível 13
```

---

## Critérios obrigatórios por nível alto

Use o nível **somente se** atender. Caso contrário, **desça**.

### Nível 5 — exige **≥ 2** destes

- [ ] Feature **nova** (não é correção nem refatoração cosmética)
- [ ] Migration com **lógica de negócio** (não só `AddField` nullable)
- [ ] 3+ arquivos em camadas diferentes (model + view + template/serializer)
- [ ] Novo endpoint ou fluxo de tela **visível ao usuário final**
- [ ] Teste de homologação exige **2+ perfis** de usuário

**Não justifica 5:** padronizar componente, refatorar service, CRUD simples, relatório só leitura, ajuste de admin, “muitos arquivos” sem risco cruzado.

### Nível 8 — exige **≥ 2** destes

- [ ] Alteração em **3+ apps Django** ou domínios distintos
- [ ] Signal/task Celery com **efeito em cascata** difícil de reverter
- [ ] Breaking change em API consumida pelo front ou integração externa
- [ ] Refatoração de fluxo **já em produção** com histórico de retorno
- [ ] Plano de rollback documentado no card **e** validado em homolog

**Não justifica 8:** testes automatizados sozinhos, “integração pequena”, migration + admin, tuning de performance, módulo isolado sem dependências cruzadas.

### Nível 13 — exige **TODOS** estes

- [ ] Toca **model ou fluxo core** usado continuamente (sessão, plenário, votação, publicação)
- [ ] Falha impede operação institucional (não é “incomoda usuário”)
- [ ] Dupla revisão (par + formal) **acordada antes** de iniciar
- [ ] Plano de rollback + janela de deploy alinhada com gestão
- [ ] Justificativa escrita: por que **não** cabe em 8

**Não justifica 13:** refatoração grande em módulo secundário, “muitas linhas”, medo genérico de regressão.

---

## Definição de cada nível (barra alta)

### Nível 1 — até 1 h útil

- Copy, label, `verbose_name`, filtro trivial, config de ambiente
- Zero migration, zero permissão, zero impacto em dado existente
- **Ex.:** corrigir texto de botão

### Nível 2 — até 2 h úteis

- Bug localizado, **1 causa raiz**, patch em 1–2 arquivos
- Sem migration; teste manual ≤ 15 min
- **Ex.:** `.filter()` errado em listagem secundária

### Nível 3 — até 4 h úteis

- Regra contida em **1 app** (form + view ou service)
- Migration aditiva simples (nullable, índice) **sem** backfill complexo
- **Ex.:** validação em `clean()` + template; `select_related` em **1** tela

### Nível 5 — até 12 h úteis

- Feature **end-to-end** em módulo isolado (model → API/tela → permissão)
- Novo app ou módulo funcional com contrato claro
- **Ex.:** endpoint DRF + serializer + testes + tela

### Nível 8 — até 27 h úteis

- **Múltiplos** apps/sistemas ou integração externa **com contrato**
- Fluxo transacional (aprovação, status em cascata, fila assíncrona)
- **Ex.:** signal `post_save` entre 2 domínios + Celery + admin action

### Nível 13 — até 44 h úteis

- Núcleo operacional; indisponibilidade = **parada**
- **Ex.:** alterar model de sessão/plenário usado em votação e pauta

---

## Níveis de análise (1, 2, 3)

Usados **somente** em cards de análise. Fluxo:

1. Executar a análise técnica (Em andamento ou equivalente)
2. Preencher **Nível (Análise)** conforme **complexidade da decisão**, não do código
3. Mover para **ANALISES PARA PLANEJAMENTO** → **aí** inicia o SLA da fila

| Nível | SLA na fila | Quando usar (todos verdadeiros) |
|-------|-------------|----------------------------------|
| 1 | 30 min | 1 sistema, 1 decisão, sem integração; implementação estimada ≤ 5 |
| 2 | 1 h | 2 sistemas **ou** dependência clara entre apps; estimativa ~ 8 |
| 3 | 2 h | 3+ sistemas **ou** risco arquitetural **ou** fluxo crítico; estimativa ≥ 8 |

**Anti-inflação em análise:** documentar bug simples de 1 tela → análise **1**, não **3** “porque o sistema é grande”.

---

## Sinais de super-nivelar (leia antes de salvar)

| Você pensou… | Nível real provável |
|--------------|---------------------|
| “Vou colocar 5 para ter tempo” | **Abuso** — nível técnico correto + Prioridade se urgente |
| “Tem migration, então é 8” | Aditiva simples → **3**; com lógica → **5** |
| “Mexe em permissão, então é 8” | 1 permission class em 1 view → **3** |
| “É integração” | Webhook read-only isolado → **5**; contrato quebrando → **8** |
| “São muitas linhas / arquivos” | Linhas ≠ risco → reavalie **impacto** |
| “Já levou dias” | Tempo gasto **não retroage** nível — nivelar no **início** |
| “Cliente pediu urgente” | **Prioridade**, não Nível |
| “Todo mundo coloca 5” | Padrão do time ≠ critério — use a árvore de decisão |

## Sinais de sub-nivelar (aí sim suba)

- Permissão de **fluxo core** ou queryset global de produção
- Migration com backfill ou alteração de dado existente
- Card voltou de **RETORNO (DEV)** 2+ vezes no mesmo assunto → **+1 degrau** Fibonacci
- Integração externa ou Celery com efeito colateral não documentado

---

## Checklist antes de mover o card

### Problema → **EM ANDAMENTO**

- [ ] **Nível** preenchido (menor compatível com risco)
- [ ] Se ≥ 5: bloco **Nivelamento** no corpo + **2+ critérios** marcados
- [ ] Se ≥ 8: dupla revisão acordada + rollback descrito
- [ ] Se 13: gestão ciente + “por que não é 8”
- [ ] **Desenvolvedor** (`D-`), **Sistema**, **Solicitante** preenchidos
- [ ] **Prioridade** separada de **Nível**

### Análise → **ANALISES PARA PLANEJAMENTO**

- [ ] Análise concluída (escopo, riscos, estimativa de implementação)
- [ ] **Nível (Análise)** preenchido
- [ ] Campos obrigatórios do card de análise completos

---

## Exemplos Django / INTGEST

| Situação | Nível | Por quê |
|----------|-------|---------|
| Corrigir `PermissionDenied` em view secundária | **2** | 1 arquivo, sem migration |
| Campo nullable + admin + listagem | **3** | 1 app, migration aditiva |
| CRUD novo isolado (API + tela) | **5** | Feature end-to-end, 1 domínio |
| Signal entre 2 apps + Celery | **8** | Multi-app + efeito colateral |
| Auth / sessão plenária / quorum | **13** | Core operacional |
| `select_related` em 1 queryset | **2–3** | Performance local |
| Breaking change em serializer DRF | **8** | Contrato externo |
| Padronizar 10 templates | **3** | Repetição, baixo risco |
| Novo app sem integração cruzada | **5** | Módulo isolado |
| Análise de bug em 1 tela | Análise **1** | Decisão local |

---

## Dupla revisão

| Nível problema | Revisão par + formal |
|----------------|----------------------|
| ≥ 8 | **Obrigatória** — card listado como violação se entregue sem cumprir |
| 5–7 | Recomendada (informativo) |
| ≤ 3 | Conforme fluxo do time |

Revisão em par que devolve para Em andamento é **pente-fino de qualidade**, não retrabalho. Retrabalho conta via **RETORNO (DEV/SUP)**.

---

## Quando renivelar (durante o trabalho)

| Situação | Ação |
|----------|------|
| Escopo **cresceu de verdade** (novo requisito acordado) | Subir **1 degrau**, documentar no card **antes** de continuar |
| Escopo **diminuiu** (corte acordado) | **Descer** o nível |
| Card demorou porque você estava em outras tarefas | **Não** muda nível |
| Retorno crítico em produção | **Prioridade Crítica**, não inflacionar Fibonacci retroativamente |
| Dúvida persistente | Pedir **segundo par de olhos** antes de Em andamento — mais barato que estourar SLA ou distorcer métrica |

Nivelar com barra alta mantém SLA justo, comparação entre devs honesta e prazo alinhado ao risco **real**.
