from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from trello_metrics.config import load_env_file, load_workflow_config
from trello_metrics.metrics.engine import MetricsEngine
from trello_metrics.parsers.export_loader import load_board_export, parse_board_export
from trello_metrics.reports.html_report import write_html_from_json_file, write_html_report
from trello_metrics.reports.pdf_report import write_pdf_report
from trello_metrics.trello_client import TrelloClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trello_metrics",
        description="Gera metricas e relatorio PDF do fluxo Trello.",
    )
    parser.add_argument("--env", default=".env", help="Arquivo .env opcional.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report_parser = subparsers.add_parser("report", help="Gera metricas/PDF a partir de JSON.")
    report_parser.add_argument("--source", required=True, help="Export JSON do Trello.")
    report_parser.add_argument("--output", default="reports/relatorio_metricas_trello.pdf")
    report_parser.add_argument("--html-output", default=None, help="Relatorio HTML interativo (padrao: mesmo nome do PDF com .html).")
    report_parser.add_argument("--metrics-json", default="reports/metricas_trello.json")
    report_parser.add_argument("--workflow", default=None, help="Config JSON de fluxo opcional.")
    report_parser.add_argument("--include-templates", action="store_true")
    report_parser.add_argument("--month", default=None, help="Mes do relatorio YYYY-MM.")
    report_parser.add_argument("--history-months", type=int, default=6)
    report_parser.add_argument("--timezone", default="America/Sao_Paulo")

    monthly_parser = subparsers.add_parser(
        "monthly",
        help="Baixa o board e gera relatorio mensal.",
    )
    monthly_parser.add_argument("--month", required=True, help="Mes do relatorio YYYY-MM.")
    monthly_parser.add_argument("--board", default=None)
    monthly_parser.add_argument("--history-months", type=int, default=6)
    monthly_parser.add_argument("--timezone", default="America/Sao_Paulo")
    monthly_parser.add_argument("--output", default=None)
    monthly_parser.add_argument("--metrics-json", default=None)
    monthly_parser.add_argument("--export-cache", default="data/trello_board_export.json")
    monthly_parser.add_argument("--workflow", default=None)

    fetch_parser = subparsers.add_parser("fetch", help="Baixa o quadro pela API do Trello.")
    fetch_parser.add_argument("--board", default=None, help="ID ou shortLink do board.")
    fetch_parser.add_argument("--output", default="data/trello_board_export.json")
    fetch_parser.add_argument(
        "--action-filter",
        default="createCard,updateCard:idList,updateCard:closed,copyCard,deleteCard,updateCustomFieldItem",
        help="Filtro de actions da API do Trello.",
    )

    subparsers.add_parser("me", help="Valida key/token com /members/me.")

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Gera relatorio HTML interativo a partir do JSON de metricas.",
    )
    dashboard_parser.add_argument("--metrics-json", required=True, help="JSON de metricas gerado pelo report.")
    dashboard_parser.add_argument("--output", default=None, help="Saida HTML (padrao: relatorio_<mes>.html).")

    args = parser.parse_args(argv)
    load_env_file(args.env)

    if args.command == "report":
        return _run_report(args)
    if args.command == "monthly":
        return _run_monthly(args)
    if args.command == "fetch":
        return _run_fetch(args)
    if args.command == "me":
        return _run_me()
    if args.command == "dashboard":
        return _run_dashboard(args)
    return 2


def _run_report(args: argparse.Namespace) -> int:
    workflow = load_workflow_config(args.workflow)
    board = load_board_export(args.source)
    metrics = MetricsEngine(
        workflow,
        include_templates=args.include_templates,
        month=args.month,
        history_months=args.history_months,
        timezone_name=args.timezone,
    ).calculate(board)

    metrics_path = Path(args.metrics_json)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    output = write_pdf_report(metrics.to_dict(), args.output)
    print(f"Relatorio gerado: {output}")
    print(f"Metricas JSON: {metrics_path}")

    html_output = getattr(args, "html_output", None) or str(Path(args.output).with_suffix(".html"))
    html_path = write_html_report(metrics.to_dict(), html_output)
    print(f"Dashboard HTML: {html_path}")
    return 0


def _run_dashboard(args: argparse.Namespace) -> int:
    metrics_path = Path(args.metrics_json)
    if not metrics_path.is_file():
        raise SystemExit(f"Arquivo nao encontrado: {metrics_path}")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    month = (metrics.get("period") or {}).get("month", "metricas")
    output = args.output or str(Path("reports") / f"relatorio_{month}.html")
    html_path = write_html_from_json_file(metrics_path, output)
    print(f"Dashboard HTML: {html_path}")
    return 0


def _run_monthly(args: argparse.Namespace) -> int:
    board_id = args.board or os.getenv("TRELLO_BOARD_ID")
    if not board_id:
        raise SystemExit("Informe --board ou TRELLO_BOARD_ID.")

    client = TrelloClient()
    payload = client.fetch_board_export(board_id)
    parse_board_export(payload)

    export_path = Path(args.export_cache)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    month_label = args.month
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    output = args.output or str(reports_dir / f"relatorio_{month_label}.pdf")
    metrics_json = args.metrics_json or str(reports_dir / f"metricas_{month_label}.json")

    report_args = argparse.Namespace(
        source=str(export_path),
        output=output,
        html_output=None,
        metrics_json=metrics_json,
        workflow=args.workflow,
        include_templates=False,
        month=month_label,
        history_months=args.history_months,
        timezone=args.timezone,
    )
    return _run_report(report_args)


def _run_fetch(args: argparse.Namespace) -> int:
    board_id = args.board or os.getenv("TRELLO_BOARD_ID")
    if not board_id:
        raise SystemExit("Informe --board ou TRELLO_BOARD_ID.")

    client = TrelloClient()
    payload = client.fetch_board_export(board_id, action_filter=args.action_filter)
    parse_board_export(payload)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Export salvo: {output}")
    return 0


def _run_me() -> int:
    client = TrelloClient()
    payload: dict[str, Any] = client.member_me()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
