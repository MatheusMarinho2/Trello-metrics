from __future__ import annotations

from typing import Any

from reports.dataclasses.report_config import TrelloSourceConfig
from trello_metrics.trello_client import TrelloClient


class TrelloApiClient:
    def fetch_board_export(self, config: TrelloSourceConfig) -> dict[str, Any]:
        if config.source_json and not config.use_live_api:
            return config.source_json

        client = TrelloClient(
            api_key=config.api_key or None,
            token=config.token or None,
        )
        return client.fetch_board_export(config.board_id)
