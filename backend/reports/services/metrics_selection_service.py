from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from reports.dataclasses.report_config import ReportGenerationConfig
from reports.services.trello_snapshot_service import inactive_collaborator_names
from reports.utils.text import normalize_name


COMMON_KEYS = ("board", "period", "overview", "data_quality")
ROLE_PREFIX_RE = re.compile(
    r"^\s*(?:REVISOR\s+EM\s+PAR|REVISOR/PAR|DESENVOLVEDOR|SOLICITANTE|TESTER|REV|DEV|RP|R|D|T|S)\s*[-:/]\s*",
    re.IGNORECASE,
)


class MetricsSelectionService:
    def build_payload(
        self,
        metrics: dict[str, Any],
        config: ReportGenerationConfig,
    ) -> dict[str, Any]:
        metrics = self._without_inactive_collaborators(metrics)
        payload = self._base_payload(metrics)
        report_type = config.report_type

        if report_type == "general":
            return self._with_card_metadata(deepcopy(metrics), metrics)
        if report_type == "individual":
            return self._with_card_metadata(
                self._individual_payload(payload, metrics, config.collaborator_name),
                metrics,
            )
        if report_type == "developers":
            payload = self._pick(
                payload,
                metrics,
                "developers",
                "developer_profiles",
                "flow",
                "sla",
                "quality_gates",
                "card_dossier",
                "fibonacci_points",
            )
            payload["role_summary"] = _developers_summary(metrics)
            return self._with_card_metadata(payload, metrics)
        if report_type == "requesters":
            payload = self._requesters_payload(payload, metrics)
            payload["role_summary"] = _requesters_summary(metrics)
            return self._with_card_metadata(payload, metrics)
        if report_type == "testers":
            payload = self._testers_payload(payload, metrics)
            payload["role_summary"] = _testers_summary(metrics)
            return self._with_card_metadata(payload, metrics)
        if report_type == "management":
            return self._with_card_metadata(self._pick(
                payload,
                metrics,
                "team_summary",
                "flow",
                "priority",
                "dora",
                "projects",
                "bottlenecks",
                "sla",
                "quality_gates",
                "process_discipline",
                "risk_board",
                "trends_6m",
            ), metrics)
        if report_type == "by_system":
            return self._with_card_metadata(
                self._by_system_payload(payload, metrics, config.sistema_name),
                metrics,
            )
        if report_type == "specific_metrics":
            keys = list(config.metric_keys)
            if "projects" in keys:
                for extra in ("project_profiles", "systems"):
                    if extra not in keys:
                        keys.append(extra)
            payload = self._pick(payload, metrics, *keys)
            payload["role_summary"] = _specific_summary(payload, config.metric_keys)
            return self._with_card_metadata(payload, metrics)
        return self._with_card_metadata(payload, metrics)

    def _without_inactive_collaborators(self, metrics: dict[str, Any]) -> dict[str, Any]:
        inactive = inactive_collaborator_names()
        if not inactive:
            return deepcopy(metrics)

        cleaned = deepcopy(metrics)
        for key in ("developers", "developer_profiles", "reviewers", "formal_reviewers", "testers", "requesters", "collaborators"):
            rows = cleaned.get(key)
            if isinstance(rows, list):
                cleaned[key] = [
                    row for row in rows if not _row_mentions_inactive(row, inactive)
                ]

        dossier = cleaned.get("card_dossier") or {}
        for bucket_key in ("by_developer", "by_solicitante", "by_tester"):
            bucket = dossier.get(bucket_key)
            if isinstance(bucket, dict):
                dossier[bucket_key] = {
                    name: value
                    for name, value in bucket.items()
                    if normalize_name(name) not in inactive
                }
        return cleaned

    def _base_payload(self, metrics: dict[str, Any]) -> dict[str, Any]:
        return {key: deepcopy(metrics[key]) for key in COMMON_KEYS if key in metrics}

    def _pick(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
        *keys: str,
    ) -> dict[str, Any]:
        for key in keys:
            if key in metrics:
                payload[key] = deepcopy(metrics[key])
        return payload

    def _with_card_metadata(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        card_metadata = _card_metadata_by_id(metrics)
        if card_metadata:
            _enrich_card_entries(payload, card_metadata)
        return payload

    def with_card_metadata(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        return self._with_card_metadata(deepcopy(payload), metrics)

    def _individual_payload(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
        collaborator_name: str,
    ) -> dict[str, Any]:
        target = normalize_name(collaborator_name)
        collaborators = metrics.get("collaborators") or []
        matched = [
            row
            for row in collaborators
            if normalize_name(row.get("name")) == target
            or target in [normalize_name(alias) for alias in row.get("aliases", [])]
        ]
        payload["collaborators"] = deepcopy(matched)
        if matched:
            payload["individual_summary"] = _individual_summary(matched[0])
            payload["role_metrics"] = deepcopy(matched[0].get("role_metrics") or [])
        else:
            payload["individual_summary"] = {}
            payload["role_metrics"] = []

        target_names = _target_name_variants(collaborator_name)
        for collaborator in matched:
            target_names.update(_target_name_variants(collaborator.get("name")))
            for alias in collaborator.get("aliases") or []:
                target_names.update(_target_name_variants(alias))

        dossier = metrics.get("card_dossier") or {}
        payload["card_dossier"] = {
            "by_developer": _filter_named_bucket(dossier.get("by_developer"), target_names),
            "by_solicitante": _filter_named_bucket(dossier.get("by_solicitante"), target_names),
            "by_tester": _filter_named_bucket(dossier.get("by_tester"), target_names),
        }
        payload["individual_target"] = collaborator_name
        return payload

    def _requesters_payload(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._pick(payload, metrics, "requesters", "projects")
        dossier = metrics.get("card_dossier") or {}
        payload["card_dossier"] = {"by_solicitante": deepcopy(dossier.get("by_solicitante", {}))}
        return payload

    def _testers_payload(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._pick(payload, metrics, "testers", "quality_gates")
        dossier = metrics.get("card_dossier") or {}
        payload["card_dossier"] = {"by_tester": deepcopy(dossier.get("by_tester", {}))}
        return payload

    def _by_system_payload(
        self,
        payload: dict[str, Any],
        metrics: dict[str, Any],
        sistema_name: str,
    ) -> dict[str, Any]:
        payload = self._pick(
            payload,
            metrics,
            "project_summary",
            "team_summary",
            "flow",
            "priority",
            "dora",
            "projects",
            "bottlenecks",
            "sla",
            "quality_gates",
            "process_discipline",
            "risk_board",
            "trends_6m",
            "collaborators",
            "developers",
            "developer_profiles",
            "requesters",
            "testers",
            "reviewers",
            "formal_reviewers",
            "card_dossier",
            "analysis_workflow",
            "antifraud",
            "fibonacci_points",
            "systems",
            "sistema_filter",
        )
        summary = deepcopy(metrics.get("project_summary") or {})
        if not summary.get("name"):
            summary["name"] = sistema_name
        payload["project_summary"] = summary
        payload["sistema_filter"] = sistema_name or metrics.get("sistema_filter") or ""
        payload["systems"] = deepcopy(metrics.get("systems") or [])
        payload["role_summary"] = {
            "scope": "by_system",
            "sistema": summary.get("name") or sistema_name,
            "cards_delivered": summary.get("cards_delivered", 0),
            "wip_total": summary.get("wip_total", 0),
            "cards_archived": summary.get("cards_archived", 0),
            "fibonacci_total": summary.get("fibonacci_total", 0),
            "rework_rate_pct": summary.get("rework_rate_pct", 0),
            "quality_rate_pct": summary.get("quality_rate_pct", 0),
        }
        return payload


def _filter_named_bucket(bucket: dict[str, Any] | None, targets: set[str]) -> dict[str, Any]:
    if not bucket:
        return {}
    return {
        name: deepcopy(value)
        for name, value in bucket.items()
        if _target_name_variants(name) & targets
    }


def _target_name_variants(value: str | None) -> set[str]:
    text = (value or "").strip()
    base = ROLE_PREFIX_RE.sub("", text, count=1).strip()
    return {item for item in (normalize_name(text), normalize_name(base)) if item}


def _card_metadata_by_id(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for item in metrics.get("cards") or []:
        if not isinstance(item, dict):
            continue
        card_id = item.get("id") or item.get("card_id")
        if not card_id:
            continue
        metadata[str(card_id)] = {
            key: item.get(key)
            for key in ("id_short", "url", "current_list", "current_group")
            if item.get(key) not in (None, "")
        }
    return metadata


def _enrich_card_entries(value: Any, metadata: dict[str, dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _enrich_card_entries(item, metadata)
        return

    if not isinstance(value, dict):
        return

    card_id = value.get("card_id") or value.get("id")
    if card_id:
        for key, item in metadata.get(str(card_id), {}).items():
            value.setdefault(key, item)

    for item in value.values():
        _enrich_card_entries(item, metadata)


def _row_mentions_inactive(row: dict[str, Any], inactive: set[str]) -> bool:
    candidate_keys = (
        "name",
        "desenvolvedor",
        "developer",
        "tester",
        "solicitante",
        "requester",
        "revisor",
        "revisor_par",
    )
    for key in candidate_keys:
        value = row.get(key)
        if isinstance(value, str) and normalize_name(value) in inactive:
            return True
    aliases = row.get("aliases")
    if isinstance(aliases, list):
        return any(normalize_name(alias) in inactive for alias in aliases)
    return False


def _individual_summary(collaborator: dict[str, Any]) -> dict[str, Any]:
    summary = collaborator.get("summary") or {}
    return {
        "name": collaborator.get("name", ""),
        "roles": collaborator.get("roles") or [],
        "aliases": collaborator.get("aliases") or [],
        "cards_active": summary.get("cards_active", 0),
        "cards_created": summary.get("cards_created", 0),
        "cards_delivered": summary.get("cards_delivered", 0),
        "fibonacci_normal": summary.get("fibonacci_normal", 0),
        "fibonacci_analysis": summary.get("fibonacci_analysis", 0),
        "fibonacci_total": summary.get("fibonacci_total", 0),
        "time_human": summary.get("time_human", "-"),
    }


def _developers_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    developers = metrics.get("developers") or []
    team = metrics.get("team_summary") or {}
    return {
        "scope": "developers",
        "people_count": len(developers),
        "cards_delivered": sum(row.get("cards_delivered", 0) for row in developers),
        "fibonacci_normal": sum(row.get("fibonacci_normal", 0) for row in developers),
        "fibonacci_analysis": sum(row.get("fibonacci_analysis", 0) for row in developers),
        "quality_rate_pct": team.get("quality_rate_pct", 0),
        "rework_rate_pct": team.get("rework_rate_pct", 0),
        "acceptance_rate_pct": team.get("acceptance_rate_pct", 0),
    }


def _requesters_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    requesters = metrics.get("requesters") or []
    return {
        "scope": "requesters",
        "people_count": len(requesters),
        "cards_created": sum(row.get("cards_created", 0) for row in requesters),
        "cards_delivered": sum(row.get("cards_delivered", 0) for row in requesters),
        "in_production": sum(row.get("in_production", 0) for row in requesters),
        "avg_planning_ok_pct": _avg_pct(requesters, "planning_ok_rate_pct"),
    }


def _testers_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    testers = metrics.get("testers") or []
    return {
        "scope": "testers",
        "people_count": len(testers),
        "cards_tested": sum(row.get("cards_tested", 0) for row in testers),
        "approved_first_pass": sum(row.get("approved_first_pass", 0) for row in testers),
        "prevented_problems": sum(
            row.get("prevented_problems", row.get("returned_dev_for_quality", 0)) for row in testers
        ),
        "retest_cycles_total": sum(row.get("retest_cycles_total", 0) for row in testers),
    }


def _specific_summary(payload: dict[str, Any], metric_keys: list[str]) -> dict[str, Any]:
    return {
        "scope": "specific_metrics",
        "selected_metrics": list(metric_keys),
        "sections_included": [key for key in metric_keys if key in payload],
    }


def _avg_pct(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row.get(key, 0)) for row in rows if row.get(key) is not None]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)
