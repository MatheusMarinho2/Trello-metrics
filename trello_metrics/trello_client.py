from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TrelloClient:
    base_url = "https://api.trello.com/1"

    def __init__(self, api_key: str | None = None, token: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TRELLO_API_KEY")
        self.token = token or os.getenv("TRELLO_TOKEN")
        if not self.api_key or not self.token:
            raise ValueError("Defina TRELLO_API_KEY e TRELLO_TOKEN no ambiente ou no .env.")

    def member_me(self) -> dict[str, Any]:
        return self._get("/members/me")

    def fetch_board_export(
        self,
        board_id: str,
        action_filter: str = "createCard,updateCard:idList,updateCard:closed,copyCard,deleteCard,updateCustomFieldItem",
    ) -> dict[str, Any]:
        board = self._get(
            f"/boards/{board_id}",
            {
                "fields": "all",
                "lists": "all",
                "cards": "all",
                "card_fields": "all",
                "card_customFieldItems": "true",
                "customFields": "true",
                "labels": "all",
                "members": "all",
                "checklists": "all",
            },
        )
        board["actions"] = self.fetch_board_actions(board_id, action_filter=action_filter)
        return board

    def fetch_board_actions(
        self,
        board_id: str,
        action_filter: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        before: str | None = None
        while True:
            params: dict[str, Any] = {
                "filter": action_filter,
                "limit": limit,
            }
            if before:
                params["before"] = before
            page = self._get(f"/boards/{board_id}/actions", params)
            if not page:
                break
            actions.extend(page)
            if len(page) < limit:
                break
            before = page[-1]["id"]
        return actions

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = {
            "key": self.api_key,
            "token": self.token,
        }
        if params:
            query.update(params)
        url = f"{self.base_url}{path}?{urlencode(query)}"
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=60) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
