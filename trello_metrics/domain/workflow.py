from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from trello_metrics.utils.text import normalize_key


@dataclass(frozen=True)
class TemplateRule:
    kind: str
    title: str
    prefixes: tuple[str, ...]
    level_field: str
    done_groups: tuple[str, ...]


class WorkflowConfig:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.list_groups = {
            group: {normalize_key(name) for name in names}
            for group, names in payload.get("list_groups", {}).items()
        }
        self.group_titles = payload.get("group_titles", {})
        self.attribution_rules = payload.get("attribution_rules", {})
        self.templates = [
            TemplateRule(
                kind=item["kind"],
                title=item.get("title", item["kind"]),
                prefixes=tuple(item.get("prefixes", [])),
                level_field=item.get("level_field", ""),
                done_groups=tuple(item.get("done_groups", [])),
            )
            for item in payload.get("templates", [])
        ]

    def group_for_list(self, list_name: str | None) -> str:
        normalized = normalize_key(list_name)
        for group, names in self.list_groups.items():
            if normalized in names:
                return group
        return "unknown"

    def title_for_group(self, group: str) -> str:
        return self.group_titles.get(group, group)

    def attribution_field_for_group(self, group: str) -> str | None:
        rule = self.attribution_rules.get(group)
        if isinstance(rule, str):
            return rule
        if isinstance(rule, dict):
            return rule.get("field")
        return None

    def role_for_group(self, group: str) -> str:
        rule = self.attribution_rules.get(group)
        if isinstance(rule, dict):
            return rule.get("role", group)
        return group

    def classify_card(self, card_name: str, custom_fields: dict[str, str], labels: list[str]) -> str:
        normalized_name = normalize_key(card_name)
        normalized_labels = {normalize_key(label) for label in labels}

        if _custom_field_value(custom_fields, "Nivel (Analise)", "Nível (Analise)"):
            return "analysis"
        if _custom_field_value(custom_fields, "Nivel", "Nível"):
            return "problem"

        for template in self.templates:
            for prefix in template.prefixes:
                if normalized_name.startswith(normalize_key(prefix)):
                    return template.kind

        if "ADMIN SCRIPT ANALISE" in normalized_labels:
            return "analysis"
        return "unknown"

    def should_ignore_card(
        self,
        card_name: str,
        custom_fields: dict[str, str],
        labels: list[str],
    ) -> bool:
        ignored_labels = {
            normalize_key(label)
            for label in self.payload.get("ignore_card_labels", [])
        }
        normalized_labels = {normalize_key(label) for label in labels}
        if ignored_labels.intersection(normalized_labels):
            return True

        if self._card_has_ignored_person(custom_fields):
            return True

        placeholder_titles = {
            normalize_key(title)
            for title in self.payload.get("placeholder_card_titles", [])
        }
        if normalize_key(card_name) not in placeholder_titles:
            return False

        level_fields = ("Nível", "Nivel", "Nível (Analise)", "Nivel (Analise)")
        return not any(custom_fields.get(field) for field in level_fields)

    def _card_has_ignored_person(self, custom_fields: dict[str, str]) -> bool:
        ignored = self.payload.get("ignore_card_people", [])
        if not ignored:
            return False
        ignored_keys = {_person_key(name) for name in ignored}
        ignored_keys.discard("")
        if not ignored_keys:
            return False
        for value in custom_fields.values():
            if _person_key(value) in ignored_keys:
                return True
        return False

    def template_for_kind(self, kind: str) -> TemplateRule | None:
        for template in self.templates:
            if template.kind == kind:
                return template
        return None

    def done_groups_for_kind(self, kind: str) -> tuple[str, ...]:
        template = self.template_for_kind(kind)
        if template:
            return template.done_groups
        return tuple(self.payload.get("default_done_groups", []))

    def delivery_groups_for_kind(self, kind: str) -> tuple[str, ...]:
        delivery = self.payload.get("delivery_groups", {})
        groups = delivery.get(kind)
        if groups:
            return tuple(groups)
        if kind == "analysis":
            return ("analysis_done",)
        return ("waiting_production",)

    def bottleneck_groups(self) -> tuple[str, ...]:
        return tuple(self.payload.get("bottleneck_groups", []))

    def required_fields_for_kind(self, kind: str) -> tuple[str, ...]:
        required = self.payload.get("required_custom_fields", {})
        fields = required.get(kind, [])
        return tuple(fields)

    def peer_review_groups(self) -> tuple[str, ...]:
        rule = self.payload.get("double_review_rule", {})
        return tuple(rule.get("peer_review_groups", ["waiting_peer_review", "peer_review"]))

    def formal_review_groups(self) -> tuple[str, ...]:
        rule = self.payload.get("double_review_rule", {})
        return tuple(rule.get("formal_review_groups", ["waiting_review", "review"]))

    def double_review_mandatory_min_level(self) -> int:
        rule = self.payload.get("double_review_rule", {})
        return int(rule.get("mandatory_min_level", 8))

    def double_review_recommended_min_level(self) -> int:
        rule = self.payload.get("double_review_rule", {})
        return int(rule.get("recommended_min_level", 5))

    def management_only_lists(self) -> dict[str, tuple[str, ...]]:
        groups = self.payload.get("management_only_groups", {})
        return {group: tuple(names) for group, names in groups.items()}

    def quality_seal_thresholds(self) -> dict[str, float]:
        thresholds = self.payload.get("quality_seal_thresholds", {})
        return {
            "gold_min_pct": float(thresholds.get("gold_min_pct", 90)),
            "silver_min_pct": float(thresholds.get("silver_min_pct", 75)),
        }

    def quality_seal(self, quality_rate_pct: float) -> str:
        thresholds = self.quality_seal_thresholds()
        if quality_rate_pct >= thresholds["gold_min_pct"]:
            return "Ouro"
        if quality_rate_pct >= thresholds["silver_min_pct"]:
            return "Prata"
        return "Atencao"

    def tester_source_groups(self) -> tuple[str, ...]:
        rule = self.payload.get("return_attribution", {})
        return tuple(rule.get("tester_source_groups", ["testing"]))

    def reviewer_source_groups(self) -> tuple[str, ...]:
        rule = self.payload.get("return_attribution", {})
        return tuple(
            rule.get(
                "reviewer_source_groups",
                ["review", "waiting_review", "peer_review", "waiting_peer_review"],
            )
        )

    def developer_work_groups(self) -> tuple[str, ...]:
        return tuple(
            self.payload.get("developer_work_groups", ["development", "return_developer"])
        )

    def pre_flow_groups(self) -> tuple[str, ...]:
        return tuple(
            self.payload.get("pre_flow_groups", ["planning", "analysis_planning"])
        )

    def pipeline_wait_groups(self) -> tuple[str, ...]:
        return tuple(
            self.payload.get(
                "pipeline_wait_groups",
                [
                    "approval",
                    "backlog",
                    "waiting_peer_review",
                    "peer_review",
                    "waiting_review",
                    "review",
                    "waiting_deploy",
                    "waiting_test",
                    "testing",
                    "waiting_production",
                    "paused",
                ],
            )
        )

    def excluded_flow_groups(self) -> tuple[str, ...]:
        return tuple(self.payload.get("excluded_flow_groups", self.pre_flow_groups()))

    def sla_rules(self) -> dict[str, Any]:
        rules = self.payload.get("sla_rules", {})
        return rules if isinstance(rules, dict) else {}


_ROLE_PREFIX_RE = re.compile(
    r"^(?:REVISOR EM PAR|DESENVOLVEDOR|SOLICITANTE|TESTER|REV|DEV|RP|R|D|T|S)\s+",
)


def _person_key(value: object) -> str:
    key = normalize_key(value)
    return _ROLE_PREFIX_RE.sub("", key, count=1).strip()


def _custom_field_value(custom_fields: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = custom_fields.get(name)
        if value:
            return value
    normalized = {normalize_key(key): value for key, value in custom_fields.items()}
    for name in names:
        value = normalized.get(normalize_key(name))
        if value:
            return value
    return None
