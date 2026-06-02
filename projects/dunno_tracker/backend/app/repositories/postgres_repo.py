"""PostgreSQL implementation using psycopg2."""
from __future__ import annotations
import json
from collections import defaultdict
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from app.repositories.base import BaseRepository


class PostgresRepository(BaseRepository):

    def __init__(self, dsn: str) -> None:
        self._pool = ThreadedConnectionPool(1, 10, dsn=dsn)

    @contextmanager
    def _conn(self):
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def _q(self, sql: str, params=None) -> list[dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def _q1(self, sql: str, params=None) -> dict | None:
        rows = self._q(sql, params)
        return rows[0] if rows else None

    def _exec(self, sql: str, params=None) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def _exec_returning(self, sql: str, params=None) -> dict:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return dict(cur.fetchone())

    # --- Projects / Auth ---

    def get_api_key(self, key_hash: str) -> dict | None:
        return self._q1("SELECT id, project_id, revoked_at FROM api_keys WHERE key_hash = %s", (key_hash,))

    def touch_api_key(self, key_id: str) -> None:
        self._exec("UPDATE api_keys SET last_used_at = NOW() WHERE id = %s", (key_id,))

    def get_project_count(self) -> int:
        row = self._q1("SELECT COUNT(*) AS cnt FROM projects")
        return row["cnt"] if row else 0

    def create_project(self, name: str, slug: str) -> dict:
        return self._exec_returning("INSERT INTO projects (name, slug) VALUES (%s, %s) RETURNING *", (name, slug))

    def insert_api_key(self, project_id: str, name: str, prefix: str, key_hash: str) -> None:
        self._exec("INSERT INTO api_keys (project_id, name, key_prefix, key_hash) VALUES (%s, %s, %s, %s)", (project_id, name, prefix, key_hash))

    def list_api_keys(self, project_id: str) -> list[dict]:
        return self._q("SELECT id, name, key_prefix, created_at, last_used_at, revoked_at FROM api_keys WHERE project_id = %s AND revoked_at IS NULL ORDER BY created_at DESC", (project_id,))

    def revoke_api_key(self, project_id: str, key_id: str) -> None:
        self._exec("UPDATE api_keys SET revoked_at = NOW() WHERE id = %s AND project_id = %s", (key_id, project_id))

    # --- Agents ---

    def upsert_agent(self, project_id: str, agent_name: str, description: str | None = None, agent_number: int | None = None) -> dict:
        return self._exec_returning("""
            INSERT INTO agents (project_id, agent_name, description, agent_number)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (project_id, agent_name) DO UPDATE
            SET description = COALESCE(EXCLUDED.description, agents.description)
            RETURNING *
        """, (project_id, agent_name, description, agent_number))

    def get_agent(self, project_id: str, agent_name: str) -> dict | None:
        return self._q1("SELECT * FROM agents WHERE project_id = %s AND agent_name = %s", (project_id, agent_name))

    def list_agents(self, project_id: str) -> list[dict]:
        return self._q("SELECT * FROM agents WHERE project_id = %s ORDER BY created_at DESC", (project_id,))

    def count_agents(self, project_id: str) -> int:
        row = self._q1("SELECT COUNT(*) AS cnt FROM agents WHERE project_id = %s", (project_id,))
        return row["cnt"] if row else 0

    def upsert_agent_version(self, agent_id: str, name: str, description: str | None, model: str | None, system_prompt: str | None, number: int) -> dict:
        return self._exec_returning("""
            INSERT INTO agent_versions (agent_id, agent_version_name, description, model, system_prompt, agent_version_number)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (agent_id, agent_version_name) DO UPDATE
            SET description = COALESCE(EXCLUDED.description, agent_versions.description),
                model = COALESCE(EXCLUDED.model, agent_versions.model)
            RETURNING *
        """, (agent_id, name, description, model, system_prompt, number))

    def get_agent_version(self, agent_id: str, name: str) -> dict | None:
        return self._q1("SELECT * FROM agent_versions WHERE agent_id = %s AND agent_version_name = %s", (agent_id, name))

    def list_agent_versions(self, agent_id: str) -> list[dict]:
        return self._q("SELECT * FROM agent_versions WHERE agent_id = %s ORDER BY created_at DESC", (agent_id,))

    def count_agent_versions(self, agent_id: str) -> int:
        row = self._q1("SELECT COUNT(*) AS cnt FROM agent_versions WHERE agent_id = %s", (agent_id,))
        return row["cnt"] if row else 0

    # --- People ---

    def upsert_person(self, project_id: str, person_id: str, properties: dict | None = None) -> dict:
        return self._exec_returning("""
            INSERT INTO people (project_id, person_id, properties)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, person_id) DO UPDATE
            SET updated_at = NOW()
            RETURNING *
        """, (project_id, person_id, json.dumps(properties or {})))

    def get_person(self, project_id: str, person_id: str) -> dict | None:
        return self._q1("SELECT * FROM people WHERE project_id = %s AND person_id = %s", (project_id, person_id))

    def update_person(self, db_id: str, properties: dict) -> dict:
        return self._exec_returning("UPDATE people SET properties = %s, updated_at = NOW() WHERE id = %s RETURNING *", (json.dumps(properties), db_id))

    def list_people(self, project_id: str) -> list[dict]:
        return self._q("SELECT * FROM people WHERE project_id = %s ORDER BY created_at DESC", (project_id,))

    def count_people(self, project_id: str) -> int:
        row = self._q1("SELECT COUNT(*) AS cnt FROM people WHERE project_id = %s", (project_id,))
        return row["cnt"] if row else 0

    # --- Fingerprints ---

    def insert_fingerprint(self, project_id: str, fingerprint_id: str, data: dict) -> dict:
        return self._exec_returning("""
            INSERT INTO fingerprints (project_id, fingerprint_id, language, language_version, sdk_version, system, git_commit, git_branch, git_tag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (project_id, fingerprint_id, data.get("language"), data.get("language_version"), data.get("sdk_version"), data.get("system"), data.get("git_commit"), data.get("git_branch"), data.get("git_tag")))

    def get_fingerprint_db_id(self, project_id: str, fingerprint_id: str) -> str | None:
        row = self._q1("SELECT id FROM fingerprints WHERE project_id = %s AND fingerprint_id = %s", (project_id, fingerprint_id))
        return str(row["id"]) if row else None

    # --- Sessions ---

    def upsert_session(self, project_id: str, session_id: str, person_id: str | None, agent_id: str | None) -> str:
        row = self._exec_returning("""
            INSERT INTO sessions (project_id, session_id, person_id, agent_id, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (project_id, session_id) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """, (project_id, session_id, person_id, agent_id))
        return str(row["id"])

    def list_sessions(self, project_id: str, agent_id: str | None, limit: int, offset: int) -> list[dict]:
        if agent_id:
            rows = self._q("""
                SELECT s.id, s.session_id, s.created_at, s.updated_at,
                       p.person_id, p.properties AS person_properties, a.agent_name
                FROM sessions s
                LEFT JOIN people p ON s.person_id = p.id
                LEFT JOIN agents a ON s.agent_id = a.id
                WHERE s.project_id = %s AND s.agent_id = %s
                ORDER BY s.updated_at DESC LIMIT %s OFFSET %s
            """, (project_id, agent_id, limit, offset))
        else:
            rows = self._q("""
                SELECT s.id, s.session_id, s.created_at, s.updated_at,
                       p.person_id, p.properties AS person_properties, a.agent_name
                FROM sessions s
                LEFT JOIN people p ON s.person_id = p.id
                LEFT JOIN agents a ON s.agent_id = a.id
                WHERE s.project_id = %s
                ORDER BY s.updated_at DESC LIMIT %s OFFSET %s
            """, (project_id, limit, offset))
        return [self._format_session(r) for r in rows]

    def get_session(self, project_id: str, session_id: str) -> dict | None:
        row = self._q1("""
            SELECT s.id, s.session_id, s.created_at, s.updated_at,
                   p.person_id, p.properties AS person_properties, a.agent_name
            FROM sessions s
            LEFT JOIN people p ON s.person_id = p.id
            LEFT JOIN agents a ON s.agent_id = a.id
            WHERE s.project_id = %s AND s.session_id = %s
        """, (project_id, session_id))
        return self._format_session(row) if row else None

    def list_sessions_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]:
        if agent_id:
            return self._q("SELECT id, created_at FROM sessions WHERE project_id = %s AND created_at >= %s AND agent_id = %s", (project_id, since, agent_id))
        return self._q("SELECT id, created_at FROM sessions WHERE project_id = %s AND created_at >= %s", (project_id, since))

    @staticmethod
    def _format_session(row: dict) -> dict:
        return {
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "created_at": row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else row.get("created_at"),
            "updated_at": row["updated_at"].isoformat() if hasattr(row.get("updated_at"), "isoformat") else row.get("updated_at"),
            "people": {"person_id": row["person_id"], "properties": row.get("person_properties") or {}} if row.get("person_id") else None,
            "agents": {"agent_name": row["agent_name"]} if row.get("agent_name") else None,
        }

    # --- Events ---

    def insert_event(self, data: dict) -> dict:
        props = data.get("properties", {})
        if not isinstance(props, str):
            props = json.dumps(props)
        return self._exec_returning("""
            INSERT INTO events (project_id, session_id, agent_id, agent_version_id, person_id, fingerprint_id,
                                event_name, properties, model, input_tokens, output_tokens, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (data.get("project_id"), data.get("session_id"), data.get("agent_id"), data.get("agent_version_id"),
              data.get("person_id"), data.get("fingerprint_id"), data.get("event_name"), props,
              data.get("model"), data.get("input_tokens"), data.get("output_tokens"), data.get("latency_ms")))

    def list_events(self, project_id: str, session_db_id: str | None, limit: int) -> list[dict]:
        if session_db_id:
            return self._q("SELECT * FROM events WHERE project_id = %s AND session_id = %s ORDER BY created_at DESC LIMIT %s", (project_id, session_db_id, limit))
        return self._q("SELECT * FROM events WHERE project_id = %s ORDER BY created_at DESC LIMIT %s", (project_id, limit))

    def get_event(self, project_id: str, event_id: str) -> dict | None:
        return self._q1("SELECT * FROM events WHERE project_id = %s AND id = %s", (project_id, event_id))

    def get_session_events_with_messages(self, session_db_id: str) -> list[dict]:
        events = self._q("""
            SELECT e.*, av.agent_version_name
            FROM events e
            LEFT JOIN agent_versions av ON e.agent_version_id = av.id
            WHERE e.session_id = %s ORDER BY e.created_at
        """, (session_db_id,))
        if not events:
            return []
        event_ids = [str(e["id"]) for e in events]
        messages = self.get_messages_for_events(event_ids)
        msg_by_event: dict[str, list] = defaultdict(list)
        for m in messages:
            msg_by_event[str(m["event_id"])].append(m)
        for e in events:
            e["messages"] = msg_by_event.get(str(e["id"]), [])
            e["agent_versions"] = {"agent_version_name": e.pop("agent_version_name", None)} if e.get("agent_version_name") else None
        return events

    def list_events_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]:
        if agent_id:
            return self._q("SELECT id, created_at, input_tokens, output_tokens, latency_ms FROM events WHERE project_id = %s AND created_at >= %s AND agent_id = %s", (project_id, since, agent_id))
        return self._q("SELECT id, created_at, input_tokens, output_tokens, latency_ms FROM events WHERE project_id = %s AND created_at >= %s", (project_id, since))

    # --- Messages ---

    def insert_messages(self, messages: list[dict]) -> None:
        if not messages:
            return
        with self._conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, """
                    INSERT INTO messages (event_id, role, content, tool_calls, tool_call_id)
                    VALUES %s
                """, [(m["event_id"], m["role"], m.get("content"), json.dumps(m["tool_calls"]) if m.get("tool_calls") else None, m.get("tool_call_id")) for m in messages])

    def get_messages_for_events(self, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []
        return self._q("SELECT * FROM messages WHERE event_id = ANY(%s) ORDER BY created_at", (event_ids,))

    # --- Analysis ---

    def replace_session_analysis(self, session_db_id: str, intents: list[dict], corrections: list[dict], resolution: dict) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM intents WHERE session_id = %s", (session_db_id,))
                cur.execute("DELETE FROM corrections WHERE session_id = %s", (session_db_id,))
                cur.execute("DELETE FROM resolutions WHERE session_id = %s", (session_db_id,))
                if intents:
                    psycopg2.extras.execute_values(cur,
                        "INSERT INTO intents (session_id, library_id, agent_id, intent, display_name, weight, msg_start, msg_end) VALUES %s",
                        [(i["session_id"], i.get("library_id"), i.get("agent_id"), i["intent"], i.get("display_name"), i.get("weight", 0), i.get("msg_start", 0), i.get("msg_end", 0)) for i in intents])
                if corrections:
                    psycopg2.extras.execute_values(cur,
                        "INSERT INTO corrections (session_id, msg_index, reason) VALUES %s",
                        [(c["session_id"], c.get("msg_index"), c.get("reason")) for c in corrections])
                cur.execute("INSERT INTO resolutions (session_id, resolved, resolution_type, summary) VALUES (%s, %s, %s, %s)",
                    (resolution["session_id"], resolution["resolved"], resolution["resolution_type"], resolution.get("summary")))

    def get_session_intents(self, session_db_id: str) -> list[dict]:
        return self._q("SELECT intent, display_name, weight, msg_start, msg_end, created_at FROM intents WHERE session_id = %s ORDER BY msg_start", (session_db_id,))

    def get_session_corrections(self, session_db_id: str) -> list[dict]:
        return self._q("SELECT msg_index, reason, created_at FROM corrections WHERE session_id = %s ORDER BY created_at", (session_db_id,))

    def get_session_resolution(self, session_db_id: str) -> dict | None:
        return self._q1("SELECT resolved, resolution_type, summary, created_at FROM resolutions WHERE session_id = %s", (session_db_id,))

    # --- Intent Library ---

    def get_intent_library(self, project_id: str) -> list[dict]:
        return self._q("SELECT id, name, display_name, description, session_count FROM intent_library WHERE project_id = %s ORDER BY session_count DESC", (project_id,))

    def upsert_intent_library(self, project_id: str, name: str, display_name: str) -> dict:
        return self._exec_returning("""
            INSERT INTO intent_library (project_id, name, display_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, name) DO UPDATE SET session_count = intent_library.session_count + 1
            RETURNING *
        """, (project_id, name, display_name))

    # --- Session meta ---

    def get_session_meta(self, session_db_id: str) -> dict | None:
        return self._q1("SELECT id, project_id, agent_id, last_analyzed_at FROM sessions WHERE id = %s", (session_db_id,))

    def update_session_analysis_meta(self, session_db_id: str, summary: str | None) -> None:
        self._exec("UPDATE sessions SET summary = %s, last_analyzed_at = NOW() WHERE id = %s", (summary, session_db_id))

    def count_session_events(self, session_db_id: str) -> int:
        row = self._q1("SELECT COUNT(*) AS cnt FROM events WHERE session_id = %s", (session_db_id,))
        return row["cnt"] if row else 0

    # --- Analytics ---

    def get_resolution_data(self, session_ids: list[str]) -> list[dict]:
        if not session_ids:
            return []
        return self._q("SELECT session_id, resolved FROM resolutions WHERE session_id = ANY(%s)", (session_ids,))

    def get_correction_session_ids(self, session_ids: list[str]) -> list[str]:
        if not session_ids:
            return []
        rows = self._q("SELECT DISTINCT session_id FROM corrections WHERE session_id = ANY(%s)", (session_ids,))
        return [str(r["session_id"]) for r in rows]

    def get_intent_weights(self, session_ids: list[str]) -> list[dict]:
        if not session_ids:
            return []
        rows = self._q("""
            SELECT intent, display_name, SUM(weight) AS total_weight
            FROM intents WHERE session_id = ANY(%s)
            GROUP BY intent, display_name ORDER BY total_weight DESC LIMIT 10
        """, (session_ids,))
        return [{"intent": r["intent"], "display_name": r["display_name"], "weight": round(float(r["total_weight"]), 3)} for r in rows]
