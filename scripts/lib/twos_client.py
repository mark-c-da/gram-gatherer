"""Minimal Twos REST client (https://www.twosapp.com/api/v1).

Auth: Authorization: Bearer $TWOS_API_KEY (create at Settings → Advanced → API Keys).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE = "https://www.twosapp.com/api/v1"


class TwosError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class TwosList:
    id: str
    title: str
    emoji: str | None = None
    things: list[dict[str, Any]] | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> TwosList:
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            emoji=data.get("emoji"),
            things=list(data.get("things") or []) if "things" in data else None,
        )


class TwosClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE,
    ) -> None:
        key = (api_key or os.environ.get("TWOS_API_KEY") or "").strip()
        if not key:
            raise TwosError(
                "TWOS_API_KEY is not set. Create a key at "
                "https://www.twosapp.com/settings/api-keys and export it."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url = f"{url}?{urllib.parse.urlencode(filtered)}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise TwosError(
                f"Twos API {method} {path} failed ({exc.code}): {err_body[:500]}",
                status=exc.code,
                body=err_body,
            ) from exc
        except urllib.error.URLError as exc:
            raise TwosError(f"Twos API network error: {exc}") from exc

    def list_lists(self, *, page: int = 0) -> dict[str, Any]:
        return self._request("GET", "/lists", query={"page": page})

    def iter_lists(self) -> list[TwosList]:
        out: list[TwosList] = []
        page = 0
        while True:
            payload = self.list_lists(page=page)
            items = payload.get("lists") or payload.get("data") or []
            if isinstance(payload, list):
                items = payload
            for item in items:
                if isinstance(item, dict) and item.get("id"):
                    out.append(TwosList.from_api(item))
            has_more = bool(payload.get("has_more")) if isinstance(payload, dict) else False
            if not has_more or not items:
                break
            page += 1
            if page > 50:
                break
        return out

    def find_list(self, name_or_id: str) -> TwosList:
        needle = (name_or_id or "").strip()
        if not needle:
            raise TwosError("List name or id is empty")
        # Prefer exact id fetch when it looks like a Twos id.
        if _looks_like_id(needle):
            return self.get_list(needle)
        lists = self.iter_lists()
        matches = [lst for lst in lists if lst.title.strip().lower() == needle.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(m.id for m in matches)
            raise TwosError(
                f"Multiple Twos lists titled {needle!r} ({ids}). Pass the list id instead."
            )
        # Soft prefix match as a convenience.
        prefix = [
            lst for lst in lists if lst.title.strip().lower().startswith(needle.lower())
        ]
        if len(prefix) == 1:
            return prefix[0]
        raise TwosError(f"No Twos list found for {needle!r}")

    def get_list(self, list_id: str) -> TwosList:
        data = self._request("GET", f"/lists/{list_id}")
        # Some responses wrap under "list".
        if isinstance(data, dict) and "list" in data and isinstance(data["list"], dict):
            wrapped = dict(data["list"])
            if "things" not in wrapped and "things" in data:
                wrapped["things"] = data["things"]
            return TwosList.from_api(wrapped)
        if not isinstance(data, dict):
            raise TwosError(f"Unexpected get_list response: {type(data)}")
        return TwosList.from_api(data)

    def create_list(
        self,
        title: str,
        *,
        emoji: str | None = None,
        things: list[dict[str, Any]] | None = None,
    ) -> TwosList:
        body: dict[str, Any] = {"title": title}
        if emoji:
            body["emoji"] = emoji
        if things:
            body["things"] = things
        data = self._request("POST", "/lists", body=body)
        if isinstance(data, dict) and "list" in data and isinstance(data["list"], dict):
            return TwosList.from_api(data["list"])
        return TwosList.from_api(data if isinstance(data, dict) else {})

    def create_thing(
        self,
        *,
        text: str,
        list_id: str | None = None,
        list_name: str | None = None,
        type: str = "note",
        url: str | None = None,
        note: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"text": text, "type": type}
        if list_id:
            body["list_id"] = list_id
        elif list_name:
            body["list"] = list_name
        else:
            raise TwosError("create_thing requires list_id or list_name")
        if url:
            body["url"] = url
        if note is not None:
            body["note"] = note
        if tags:
            body["tags"] = tags
        return self._request("POST", "/things", body=body)

    def append_markdown(
        self,
        markdown: str,
        *,
        list_id: str | None = None,
        list_name: str | None = None,
        skip_duplicates: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "markdown": markdown,
            "skip_duplicates": skip_duplicates,
        }
        if list_id:
            body["list_id"] = list_id
        elif list_name:
            body["list"] = list_name
        else:
            raise TwosError("append_markdown requires list_id or list_name")
        return self._request("POST", "/things/markdown", body=body)


def _looks_like_id(value: str) -> bool:
    # Twos ids are typically 24-char hex Mongo-style, but accept longer opaque ids too.
    if len(value) < 16:
        return False
    return all(c.isalnum() for c in value)
