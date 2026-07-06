from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.card_dossier import _card_entry
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.dates import human_hours
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import clean_spaces, normalize_key


ROLE_ORDER = ("solicitante", "desenvolvedor", "revisor_par", "revisor", "tester")

ROLE_CONFIGS: dict[str, dict[str, Any]] = {
    "solicitante": {
        "label": "Solicitante",
        "attr": "solicitante",
        "groups": ("analysis_planning", "planning", "approval"),
    },
    "desenvolvedor": {
        "label": "Desenvolvedor",
        "attr": "desenvolvedor",
        "groups": ("development", "return_developer"),
    },
    "revisor_par": {
        "label": "Revisor em Par",
        "attr": "revisor_par",
        "groups": ("peer_review",),
    },
    "revisor": {
        "label": "Revisor",
        "attr": "revisor",
        "groups": ("review",),
    },
    "tester": {
        "label": "Tester",
        "attr": "tester",
        "groups": ("waiting_test", "testing", "return_support"),
    },
}

_ROLE_PREFIX_RE = re.compile(
    r"^\s*(?:REVISOR\s+EM\s+PAR|REVISOR/PAR|DESENVOLVEDOR|SOLICITANTE|TESTER|REV|DEV|RP|R|D|T|S)\s*[-:/]\s*",
    re.IGNORECASE,
)

_IGNORED_NAMES = {"", "-", "--", "NAO INFORMADO", "NÃO INFORMADO", "SEM RESPONSAVEL"}


@dataclass
class ProcessAccumulator:
    group: str
    title: str
    total_hours: float = 0.0
    visits: int = 0
    cards: set[str] = field(default_factory=set)

    def add(self, card_id: str, hours: float) -> None:
        self.total_hours += hours
        self.visits += 1
        self.cards.add(card_id)

    def to_dict(self) -> dict[str, Any]:
        avg = self.total_hours / self.visits if self.visits else 0.0
        return {
            "group": self.group,
            "title": self.title,
            "total_hours": round(self.total_hours, 4),
            "total_human": human_hours(self.total_hours),
            "avg_hours": round(avg, 4),
            "avg_human": human_hours(avg),
            "visits": self.visits,
            "cards": len(self.cards),
        }


@dataclass
class RoleAccumulator:
    role_key: str
    role_label: str
    cards_active: int = 0
    cards_created: int = 0
    cards_delivered: int = 0
    fibonacci_normal: int = 0
    fibonacci_analysis: int = 0
    time_hours: float = 0.0
    visits: int = 0
    process_times: dict[str, ProcessAccumulator] = field(default_factory=dict)
    extra: dict[str, float | int] = field(default_factory=lambda: defaultdict(float))

    def add_process(
        self,
        timeline: CardTimeline,
        stage: StageTimelineEntry,
        workflow: WorkflowConfig,
    ) -> None:
        if stage.group not in self.process_times:
            self.process_times[stage.group] = ProcessAccumulator(
                group=stage.group,
                title=workflow.title_for_group(stage.group),
            )
        self.process_times[stage.group].add(timeline.card_id, stage.hours)
        self.time_hours += stage.hours
        self.visits += 1

    def add_points(self, timeline: CardTimeline) -> None:
        points = timeline.fibonacci_level or 0
        if timeline.kind == "analysis":
            self.fibonacci_analysis += points
        elif timeline.kind == "problem":
            self.fibonacci_normal += points

    def to_dict(self) -> dict[str, Any]:
        total_points = self.fibonacci_normal + self.fibonacci_analysis
        avg = self.time_hours / self.visits if self.visits else 0.0
        output: dict[str, Any] = {
            "role_key": self.role_key,
            "role_label": self.role_label,
            "cards_active": self.cards_active,
            "cards_created": self.cards_created,
            "cards_delivered": self.cards_delivered,
            "fibonacci_normal": self.fibonacci_normal,
            "fibonacci_analysis": self.fibonacci_analysis,
            "fibonacci_total": total_points,
            "time_hours": round(self.time_hours, 2),
            "time_human": human_hours(self.time_hours),
            "avg_time_hours": round(avg, 2),
            "avg_time_human": human_hours(avg),
            "visits": self.visits,
            "process_times": _process_rows(self.process_times),
        }
        output.update(_extra_to_dict(self.role_key, self.extra, self.cards_delivered))
        return output


@dataclass
class CollaboratorAccumulator:
    key: str
    id: str
    name: str
    aliases: set[str] = field(default_factory=set)
    role_keys: set[str] = field(default_factory=set)
    active_cards: set[str] = field(default_factory=set)
    created_cards: set[str] = field(default_factory=set)
    delivered_cards: set[str] = field(default_factory=set)
    delivered_points: dict[str, tuple[int, int]] = field(default_factory=dict)
    process_times: dict[str, ProcessAccumulator] = field(default_factory=dict)
    roles: dict[str, RoleAccumulator] = field(default_factory=dict)
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)

    def role(self, role_key: str) -> RoleAccumulator:
        if role_key not in self.roles:
            self.roles[role_key] = RoleAccumulator(
                role_key=role_key,
                role_label=ROLE_CONFIGS[role_key]["label"],
            )
        return self.roles[role_key]

    def add_process(
        self,
        timeline: CardTimeline,
        role_acc: RoleAccumulator,
        stage: StageTimelineEntry,
        workflow: WorkflowConfig,
    ) -> None:
        if stage.group not in self.process_times:
            self.process_times[stage.group] = ProcessAccumulator(
                group=stage.group,
                title=workflow.title_for_group(stage.group),
            )
        self.process_times[stage.group].add(timeline.card_id, stage.hours)
        role_acc.add_process(timeline, stage, workflow)

    def to_dict(self) -> dict[str, Any]:
        dev_role = self.roles.get("desenvolvedor")
        if dev_role:
            fibonacci_normal = dev_role.fibonacci_normal
            fibonacci_analysis = dev_role.fibonacci_analysis
        else:
            fibonacci_normal = 0
            fibonacci_analysis = 0
        process_rows = _process_rows(self.process_times)
        total_hours = sum(row["total_hours"] for row in process_rows)
        role_rows = [
            self.roles[role_key].to_dict()
            for role_key in ROLE_ORDER
            if role_key in self.roles
        ]
        cards = sorted(
            self.cards.values(),
            key=lambda item: (
                item.get("delivered_at") or "",
                item.get("card_name") or "",
            ),
            reverse=True,
        )
        return {
            "id": self.id,
            "name": self.name,
            "key": self.key,
            "aliases": sorted(self.aliases),
            "roles": [
                ROLE_CONFIGS[role_key]["label"]
                for role_key in ROLE_ORDER
                if role_key in self.role_keys
            ],
            "summary": {
                "cards_active": len(self.active_cards),
                "cards_created": len(self.created_cards),
                "cards_delivered": len(self.delivered_cards),
                "fibonacci_normal": fibonacci_normal,
                "fibonacci_analysis": fibonacci_analysis,
                "fibonacci_total": fibonacci_normal + fibonacci_analysis,
                "has_developer_points": dev_role is not None and (fibonacci_normal + fibonacci_analysis) > 0,
                "time_hours": round(total_hours, 2),
                "time_human": human_hours(total_hours),
            },
            "process_times": process_rows,
            "role_metrics": role_rows,
            "cards": cards,
        }


def aggregate_collaborators(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig,
) -> list[dict[str, Any]]:
    """Agrega metricas individuais por pessoa, independente do papel exercido.

    A identidade do colaborador e o nome base: prefixos de papel como D-, RP-,
    R-, T- e S- sao removidos antes de comparar os nomes.
    """
    collaborators: dict[str, CollaboratorAccumulator] = {}

    for timeline in timelines:
        active = timeline.is_active_in(period)
        delivered = timeline.is_delivered_in(period)
        created = timeline.is_created_in(period)

        for role_key in ROLE_ORDER:
            config = ROLE_CONFIGS[role_key]
            raw_name = getattr(timeline, config["attr"])
            identity = collaborator_identity(raw_name)
            if identity is None:
                continue

            key, display_name = identity
            if key not in collaborators:
                collaborators[key] = CollaboratorAccumulator(
                    key=key,
                    id=_slugify(key),
                    name=display_name,
                )

            collab = collaborators[key]
            collab.aliases.add(raw_name)
            collab.role_keys.add(role_key)
            role_acc = collab.role(role_key)

            if active:
                collab.active_cards.add(timeline.card_id)
                role_acc.cards_active += 1
                _add_card_involvement(collab, timeline, role_key, raw_name, workflow)

                for stage in _role_stages(timeline, role_key):
                    collab.add_process(timeline, role_acc, stage, workflow)

            if created:
                collab.created_cards.add(timeline.card_id)
                if role_key == "solicitante":
                    role_acc.cards_created += 1

            if delivered:
                collab.delivered_cards.add(timeline.card_id)
                role_acc.cards_delivered += 1
                if role_key == "desenvolvedor":
                    collab.delivered_points[timeline.card_id] = _timeline_points(timeline)
                    role_acc.add_points(timeline)
                _add_role_specific_metrics(role_acc, timeline, role_key)

    rows = [collab.to_dict() for collab in collaborators.values()]
    rows.sort(
        key=lambda row: (
            row["summary"]["has_developer_points"],
            row["summary"]["fibonacci_total"],
            row["summary"]["cards_delivered"],
            row["summary"]["cards_active"],
            row["name"],
        ),
        reverse=True,
    )
    return rows


def collaborator_identity(value: str) -> tuple[str, str] | None:
    base = _base_name(value)
    normalized = normalize_key(base)
    if normalized in _IGNORED_NAMES:
        return None
    return normalized, base


def _base_name(value: str) -> str:
    text = clean_spaces(value)
    text = _ROLE_PREFIX_RE.sub("", text, count=1)
    return clean_spaces(text)


def _slugify(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-") or "colaborador"


def _timeline_points(timeline: CardTimeline) -> tuple[int, int]:
    points = timeline.fibonacci_level or 0
    if timeline.kind == "analysis":
        return 0, points
    if timeline.kind == "problem":
        return points, 0
    return 0, 0


def _role_stages(timeline: CardTimeline, role_key: str) -> list[StageTimelineEntry]:
    groups = set(ROLE_CONFIGS[role_key]["groups"])
    return [stage for stage in timeline.stage_timeline if stage.group in groups]


def _add_card_involvement(
    collab: CollaboratorAccumulator,
    timeline: CardTimeline,
    role_key: str,
    raw_name: str,
    workflow: WorkflowConfig,
) -> None:
    if timeline.card_id not in collab.cards:
        entry = _card_entry(timeline)
        entry["collaborator_roles"] = []
        entry["collaborator_involvements"] = []
        entry["collaborator_time_hours"] = 0.0
        entry["collaborator_time_human"] = human_hours(0)
        collab.cards[timeline.card_id] = entry

    entry = collab.cards[timeline.card_id]
    role_label = ROLE_CONFIGS[role_key]["label"]
    if role_label not in entry["collaborator_roles"]:
        entry["collaborator_roles"].append(role_label)

    stages = _role_stages(timeline, role_key)
    total_hours = sum(stage.hours for stage in stages)
    entry["collaborator_time_hours"] = round(
        float(entry["collaborator_time_hours"]) + total_hours,
        2,
    )
    entry["collaborator_time_human"] = human_hours(float(entry["collaborator_time_hours"]))
    entry["collaborator_involvements"].append(
        {
            "role_key": role_key,
            "role_label": role_label,
            "alias": raw_name,
            "time_hours": round(total_hours, 2),
            "time_human": human_hours(total_hours),
            "stages": [
                {
                    **stage.to_dict(),
                    "title": workflow.title_for_group(stage.group),
                }
                for stage in stages
            ],
        }
    )


def _add_role_specific_metrics(
    role_acc: RoleAccumulator,
    timeline: CardTimeline,
    role_key: str,
) -> None:
    extra = role_acc.extra
    if role_key == "desenvolvedor":
        extra["return_dev_count"] += timeline.developer_penalty_return_count
        extra["tester_quality_returns"] += timeline.return_dev_by_teste_count
        extra["peer_review_returns"] += timeline.peer_review_returns
        if timeline.developer_penalty_return_count > 0:
            extra["cards_with_rework"] += 1
        if timeline.accepted_without_dev_return:
            extra["accepted_count"] += 1
        if timeline.double_review_required:
            extra["double_review_mandatory_total"] += 1
            if timeline.double_review_violation:
                extra["double_review_mandatory_violations"] += 1

    elif role_key == "revisor_par":
        extra["reviews_done"] += 1
        if timeline.peer_review_sent_back:
            extra["sent_back"] += 1
        elif timeline.return_dev_by_teste_count > 0:
            extra["escaped_to_test"] += 1
        else:
            extra["approved"] += 1

    elif role_key == "revisor":
        extra["formal_reviews_done"] += 1
        extra["review_return_events"] += timeline.return_dev_by_revisao_count
        if timeline.return_dev_by_teste_count > 0:
            extra["escaped_to_test"] += 1
        elif timeline.passed_formal_review:
            extra["formal_review_passed"] += 1

    elif role_key == "tester" and timeline.kind == "problem" and timeline.passed_test_phase:
        extra["cards_tested"] += 1
        extra["approved_first_pass"] += 1 if not timeline.tester_returned_dev else 0
        extra["prevented_problems"] += timeline.return_dev_by_teste_count
        extra["returned_dev_for_quality"] += timeline.return_dev_by_teste_count
        extra["returns_missing_reason"] += timeline.test_return_missing_reason_count
        extra["retest_cycles_total"] += timeline.retest_cycles
        if timeline.tester_returned_dev:
            extra["cards_with_tester_return"] += 1

    elif role_key == "solicitante":
        extra["requester_delivered"] += 1
        if timeline.gestor_premature_approval:
            extra["gestor_premature_approvals"] += 1
        if timeline.return_sup_count == 0 and not timeline.gestor_premature_approval:
            extra["without_sup_return"] += 1
        if timeline.group_hours.get("production", 0) > 0 or timeline.kind == "problem":
            extra["in_production"] += 1


def _extra_to_dict(
    role_key: str,
    extra: dict[str, float | int],
    delivered: int,
) -> dict[str, Any]:
    if role_key == "desenvolvedor":
        cards_with_rework = int(extra.get("cards_with_rework", 0))
        accepted = int(extra.get("accepted_count", 0))
        rework_rate = round(100 * cards_with_rework / delivered, 1) if delivered else 0.0
        return {
            "return_dev_count": int(extra.get("return_dev_count", 0)),
            "tester_quality_returns": int(extra.get("tester_quality_returns", 0)),
            "peer_review_returns": int(extra.get("peer_review_returns", 0)),
            "cards_with_rework": cards_with_rework,
            "rework_rate_pct": rework_rate,
            "quality_rate_pct": round(100 - rework_rate, 1) if delivered else 0.0,
            "acceptance_rate_pct": round(100 * accepted / delivered, 1) if delivered else 0.0,
            "double_review_mandatory_total": int(extra.get("double_review_mandatory_total", 0)),
            "double_review_mandatory_violations": int(extra.get("double_review_mandatory_violations", 0)),
        }

    if role_key == "revisor_par":
        reviews = int(extra.get("reviews_done", 0))
        approved = int(extra.get("approved", 0))
        return {
            "reviews_done": reviews,
            "approved": approved,
            "sent_back": int(extra.get("sent_back", 0)),
            "escaped_to_test": int(extra.get("escaped_to_test", 0)),
            "approval_rate_pct": round(100 * approved / reviews, 1) if reviews else 0.0,
        }

    if role_key == "revisor":
        reviews = int(extra.get("formal_reviews_done", 0))
        passed = int(extra.get("formal_review_passed", 0))
        return {
            "formal_reviews_done": reviews,
            "formal_review_passed": passed,
            "review_return_events": int(extra.get("review_return_events", 0)),
            "escaped_to_test": int(extra.get("escaped_to_test", 0)),
            "approval_rate_pct": round(100 * passed / reviews, 1) if reviews else 0.0,
        }

    if role_key == "tester":
        tested = int(extra.get("cards_tested", 0))
        first_pass = int(extra.get("approved_first_pass", 0))
        returned_cards = int(extra.get("cards_with_tester_return", 0))
        return {
            "cards_tested": tested,
            "approved_first_pass": first_pass,
            "prevented_problems": int(extra.get("prevented_problems", 0)),
            "returned_dev_for_quality": int(extra.get("returned_dev_for_quality", 0)),
            "returns_missing_reason": int(extra.get("returns_missing_reason", 0)),
            "retest_cycles_total": int(extra.get("retest_cycles_total", 0)),
            "tester_return_rate_pct": round(100 * returned_cards / tested, 1) if tested else 0.0,
        }

    if role_key == "solicitante":
        delivered_count = int(extra.get("requester_delivered", 0))
        without_return = int(extra.get("without_sup_return", 0))
        gestor_premature = int(extra.get("gestor_premature_approvals", 0))
        return {
            "requester_delivered": delivered_count,
            "in_production": int(extra.get("in_production", 0)),
            "gestor_premature_approvals": gestor_premature,
            "gestor_approval_quality_pct": (
                round(100 * (delivered_count - gestor_premature) / delivered_count, 1)
                if delivered_count
                else 0.0
            ),
            "planning_ok_rate_pct": (
                round(100 * without_return / delivered_count, 1) if delivered_count else 0.0
            ),
        }

    return {}


def _process_rows(processes: dict[str, ProcessAccumulator]) -> list[dict[str, Any]]:
    rows = [process.to_dict() for process in processes.values()]
    rows.sort(key=lambda row: row["total_hours"], reverse=True)
    return rows
