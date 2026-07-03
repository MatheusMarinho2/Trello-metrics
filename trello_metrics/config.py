from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig


DEFAULT_WORKFLOW_PATH = Path(__file__).with_name("resources") / "workflow.json"


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def load_workflow_config(path: str | Path | None = None) -> WorkflowConfig:
    return WorkflowConfig(load_json(path or DEFAULT_WORKFLOW_PATH))


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
