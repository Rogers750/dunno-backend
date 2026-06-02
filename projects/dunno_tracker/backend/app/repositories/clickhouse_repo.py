"""
ClickHouse hybrid repository.

Architecture:
  Events + Messages  →  ClickHouse  (append-only, analytics)
  Everything else    →  Postgres    (relational, transactional)
"""
from __future__ import annotations
import json
import uuid
from collections import defaultdict

import clickhouse_connect

from app.repositories.postgres_repo import PostgresRepository


class ClickHouseRepository(PostgresRepository):
    """
    Extends PostgresRepository and overrides only events + messages
    to write/read from ClickHouse instead.
    """

    def __init__(self, postgres_dsn: str, ch_host: str, ch_port: int, ch_user: str, ch_password: str, ch_database: str) -> None:
        super().__init__(postgres_dsn)
        self._ch = clickhouse_connect.get_client(
            host=ch_host,
            port=ch_port,
            username=ch_user,
            password=ch_password,
            database=ch_database,
        )

    # --- Events (ClickHouse) ---

    def insert_event(self, data: dict) -> dict:
        event_id = str(uuid.uuid4())
        props = data.get("properties", {})
        if not isinstance(props, str):
            props = json.dumps(props)

        self._ch.insert("events", [[
            event_id,
            data.get("project_id") or "",
            data.get("session_id") or "",
            data.get("agent_id") or "",
            data.get("agent_version_id") or "",
            data.get("person_id") or "",
            data.get("fingerprint_id") or "",
            data.get("event_name", ""),
            props,
            data.get("model") or "",
            data.get("input_tokens") or 0,
            data.get("output_tokens") or 0,
            data.get("latency_ms") or 0,
        ]], column_names=[
            "id", "project_id", "session_id", "agent_id", "agent_version_id",
            "person_id", "fingerprint_id", "event_name", "properties",
            "model", "input_tokens", "output_tokens", "latency_ms",
        ])

        return {
            "id": event_id,
            "event_name": data.get("event_name"),
            "model": data.get("model"),
            "input_tokens": data.get("input_tokens"),
            "output_tokens": data.get("output_tokens"),
            "latency_ms": data.get("latency_ms"),
            "properties": props,
            "created_at": None,
        }

    def list_events(self, project_id: str, session_db_id: str | None, limit: int) -> list[dict]:
        if session_db_id:
            result = self._ch.query(
                "SELECT * FROM events WHERE project_id = {p:String} AND session_id = {s:String} ORDER BY created_at DESC LIMIT {l:Int32}",
                parameters={"p": project_id, "s": session_db_id, "l": limit},
            )
        else:
            result = self._ch.query(
                "SELECT * FROM events WHERE project_id = {p:String} ORDER BY created_at DESC LIMIT {l:Int32}",
                parameters={"p": project_id, "l": limit},
            )
        return result.named_results()

    def get_event(self, project_id: str, event_id: str) -> dict | None:
        result = self._ch.query(
            "SELECT * FROM events WHERE project_id = {p:String} AND id = {id:String} LIMIT 1",
            parameters={"p": project_id, "id": event_id},
        )
        rows = result.named_results()
        return rows[0] if rows else None

    def get_session_events_with_messages(self, session_db_id: str) -> list[dict]:
        events_result = self._ch.query(
            "SELECT * FROM events WHERE session_id = {s:String} ORDER BY created_at",
            parameters={"s": session_db_id},
        )
        events = events_result.named_results()
        if not events:
            return []

        event_ids = [str(e["id"]) for e in events]
        messages = self.get_messages_for_events(event_ids)
        msg_by_event: dict[str, list] = defaultdict(list)
        for m in messages:
            msg_by_event[str(m["event_id"])].append(m)
        for e in events:
            e["messages"] = msg_by_event.get(str(e["id"]), [])
            e["agent_versions"] = None
        return events

    def list_events_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]:
        if agent_id:
            result = self._ch.query(
                "SELECT id, created_at, input_tokens, output_tokens, latency_ms FROM events WHERE project_id = {p:String} AND agent_id = {a:String} AND created_at >= {s:String}",
                parameters={"p": project_id, "a": agent_id, "s": since},
            )
        else:
            result = self._ch.query(
                "SELECT id, created_at, input_tokens, output_tokens, latency_ms FROM events WHERE project_id = {p:String} AND created_at >= {s:String}",
                parameters={"p": project_id, "s": since},
            )
        return result.named_results()

    # --- Messages (ClickHouse) ---

    def insert_messages(self, messages: list[dict]) -> None:
        if not messages:
            return
        rows = [[
            str(uuid.uuid4()),
            m["event_id"],
            m["role"],
            m.get("content") or "",
            json.dumps(m["tool_calls"]) if m.get("tool_calls") else "",
            m.get("tool_call_id") or "",
        ] for m in messages]
        self._ch.insert("messages", rows, column_names=["id", "event_id", "role", "content", "tool_calls", "tool_call_id"])

    def get_messages_for_events(self, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []
        ids_str = ", ".join(f"'{eid}'" for eid in event_ids)
        result = self._ch.query(f"SELECT * FROM messages WHERE event_id IN ({ids_str}) ORDER BY created_at")
        return result.named_results()
