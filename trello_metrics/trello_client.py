from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_ACTION_FILTER = (
    "createCard,updateCard:idList,updateCard:closed,updateCard:due,"
    "copyCard,deleteCard,updateCustomFieldItem,"
    "addMemberToCard,removeMemberFromCard,"
    "convertToCardFromCheckItem,moveCardToBoard,moveCardFromBoard"
)


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
        action_filter: str = DEFAULT_ACTION_FILTER,
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
        delays = (0.5, 1.5, 3.0)
        last_error: Exception | None = None
        for attempt, delay in enumerate((*delays, None)):
            try:
                with urlopen(request, timeout=60) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return json.loads(response.read().decode(charset))
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504} or delay is None:
                    raise
                time.sleep(delay)
            except Exception as exc:  # noqa: BLE001 — retry de rede transitória
                last_error = exc
                if delay is None:
                    raise
                time.sleep(delay)
        if last_error:
            raise last_error
        raise RuntimeError(f"Falha ao chamar Trello: {path}")
