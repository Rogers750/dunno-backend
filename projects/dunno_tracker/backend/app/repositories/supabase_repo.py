"""Supabase implementation — wraps the existing supabase-py client."""
from __future__ import annotations
from supabase import create_client, Client
from app.repositories.base import BaseRepository


class SupabaseRepository(BaseRepository):

    def __init__(self, url: str, key: str) -> None:
        self._db: Client = create_client(url, key)

    def _db_client(self) -> Client:
        return self._db

    # --- Projects / Auth ---

    def get_api_key(self, key_hash: str) -> dict | None:
        res = self._db.table("api_keys").select("id, project_id, revoked_at").eq("key_hash", key_hash).maybe_single().execute()
        return res.data if res and res.data else None

    def touch_api_key(self, key_id: str) -> None:
        self._db.table("api_keys").update({"last_used_at": "now()"}).eq("id", key_id).execute()

    def get_project_count(self) -> int:
        res = self._db.table("projects").select("id", count="exact").limit(1).execute()
        return res.count or 0

    def create_project(self, name: str, slug: str) -> dict:
        res = self._db.table("projects").insert({"name": name, "slug": slug}).execute()
        return res.data[0]

    def insert_api_key(self, project_id: str, name: str, prefix: str, key_hash: str) -> None:
        self._db.table("api_keys").insert({"project_id": project_id, "name": name, "key_prefix": prefix, "key_hash": key_hash}).execute()

    def list_api_keys(self, project_id: str) -> list[dict]:
        res = self._db.table("api_keys").select("id, name, key_prefix, created_at, last_used_at, revoked_at").eq("project_id", project_id).is_("revoked_at", "null").order("created_at", desc=True).execute()
        return res.data or []

    def revoke_api_key(self, project_id: str, key_id: str) -> None:
        self._db.table("api_keys").update({"revoked_at": "now()"}).eq("id", key_id).eq("project_id", project_id).execute()

    # --- Agents ---

    def upsert_agent(self, project_id: str, agent_name: str, description: str | None = None, agent_number: int | None = None) -> dict:
        res = self._db.table("agents").upsert({"project_id": project_id, "agent_name": agent_name, "description": description, "agent_number": agent_number}, on_conflict="project_id,agent_name").execute()
        return res.data[0]

    def get_agent(self, project_id: str, agent_name: str) -> dict | None:
        res = self._db.table("agents").select("*").eq("project_id", project_id).eq("agent_name", agent_name).maybe_single().execute()
        return res.data if res and res.data else None

    def list_agents(self, project_id: str) -> list[dict]:
        res = self._db.table("agents").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
        return res.data or []

    def count_agents(self, project_id: str) -> int:
        res = self._db.table("agents").select("id", count="exact").eq("project_id", project_id).execute()
        return res.count or 0

    def upsert_agent_version(self, agent_id: str, name: str, description: str | None, model: str | None, system_prompt: str | None, number: int) -> dict:
        res = self._db.table("agent_versions").upsert({"agent_id": agent_id, "agent_version_name": name, "description": description, "model": model, "system_prompt": system_prompt, "agent_version_number": number}, on_conflict="agent_id,agent_version_name").execute()
        return res.data[0]

    def get_agent_version(self, agent_id: str, name: str) -> dict | None:
        res = self._db.table("agent_versions").select("*").eq("agent_id", agent_id).eq("agent_version_name", name).maybe_single().execute()
        return res.data if res and res.data else None

    def list_agent_versions(self, agent_id: str) -> list[dict]:
        res = self._db.table("agent_versions").select("*").eq("agent_id", agent_id).order("created_at", desc=True).execute()
        return res.data or []

    def count_agent_versions(self, agent_id: str) -> int:
        res = self._db.table("agent_versions").select("id", count="exact").eq("agent_id", agent_id).execute()
        return res.count or 0

    # --- People ---

    def upsert_person(self, project_id: str, person_id: str, properties: dict | None = None) -> dict:
        res = self._db.table("people").upsert({"project_id": project_id, "person_id": person_id, "properties": properties or {}}, on_conflict="project_id,person_id").execute()
        return res.data[0]

    def get_person(self, project_id: str, person_id: str) -> dict | None:
        res = self._db.table("people").select("*").eq("project_id", project_id).eq("person_id", person_id).maybe_single().execute()
        return res.data if res and res.data else None

    def update_person(self, db_id: str, properties: dict) -> dict:
        res = self._db.table("people").update({"properties": properties, "updated_at": "now()"}).eq("id", db_id).execute()
        return res.data[0]

    def list_people(self, project_id: str) -> list[dict]:
        res = self._db.table("people").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
        return res.data or []

    def count_people(self, project_id: str) -> int:
        res = self._db.table("people").select("id", count="exact").eq("project_id", project_id).execute()
        return res.count or 0

    # --- Fingerprints ---

    def insert_fingerprint(self, project_id: str, fingerprint_id: str, data: dict) -> dict:
        res = self._db.table("fingerprints").insert({**data, "project_id": project_id, "fingerprint_id": fingerprint_id}).execute()
        return res.data[0]

    def get_fingerprint_db_id(self, project_id: str, fingerprint_id: str) -> str | None:
        res = self._db.table("fingerprints").select("id").eq("project_id", project_id).eq("fingerprint_id", fingerprint_id).maybe_single().execute()
        return res.data["id"] if res and res.data else None

    # --- Sessions ---

    def upsert_session(self, project_id: str, session_id: str, person_id: str | None, agent_id: str | None) -> str:
        res = self._db.table("sessions").upsert({"project_id": project_id, "session_id": session_id, "person_id": person_id, "agent_id": agent_id, "updated_at": "now()"}, on_conflict="project_id,session_id").execute()
        return res.data[0]["id"]

    def list_sessions(self, project_id: str, agent_id: str | None, limit: int, offset: int) -> list[dict]:
        q = self._db.table("sessions").select("id, session_id, created_at, updated_at, people(person_id, properties), agents(agent_name)").eq("project_id", project_id).order("updated_at", desc=True).range(offset, offset + limit - 1)
        if agent_id:
            q = q.eq("agent_id", agent_id)
        return q.execute().data or []

    def get_session(self, project_id: str, session_id: str) -> dict | None:
        res = self._db.table("sessions").select("id, session_id, created_at, updated_at, people(person_id, properties), agents(agent_name)").eq("project_id", project_id).eq("session_id", session_id).maybe_single().execute()
        return res.data if res and res.data else None

    def list_sessions_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]:
        q = self._db.table("sessions").select("id, created_at").eq("project_id", project_id).gte("created_at", since)
        if agent_id:
            q = q.eq("agent_id", agent_id)
        return q.execute().data or []

    # --- Events ---

    def insert_event(self, data: dict) -> dict:
        res = self._db.table("events").insert(data).execute()
        return res.data[0]

    def list_events(self, project_id: str, session_db_id: str | None, limit: int) -> list[dict]:
        q = self._db.table("events").select("*").eq("project_id", project_id).order("created_at", desc=True).limit(limit)
        if session_db_id:
            q = q.eq("session_id", session_db_id)
        return q.execute().data or []

    def get_event(self, project_id: str, event_id: str) -> dict | None:
        res = self._db.table("events").select("*").eq("project_id", project_id).eq("id", event_id).maybe_single().execute()
        return res.data if res and res.data else None

    def get_session_events_with_messages(self, session_db_id: str) -> list[dict]:
        res = self._db.table("events").select("*, messages(*), agent_versions(agent_version_name)").eq("session_id", session_db_id).order("created_at").execute()
        return res.data or []

    def list_events_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]:
        q = self._db.table("events").select("id, created_at, input_tokens, output_tokens, latency_ms").eq("project_id", project_id).gte("created_at", since)
        if agent_id:
            q = q.eq("agent_id", agent_id)
        return q.execute().data or []

    # --- Messages ---

    def insert_messages(self, messages: list[dict]) -> None:
        if messages:
            self._db.table("messages").insert(messages).execute()

    def get_messages_for_events(self, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []
        res = self._db.table("messages").select("role, content, created_at").in_("event_id", event_ids).order("created_at").execute()
        return res.data or []

    # --- Analysis ---

    def replace_session_analysis(self, session_db_id: str, intents: list[dict], corrections: list[dict], resolution: dict) -> None:
        self._db.table("intents").delete().eq("session_id", session_db_id).execute()
        self._db.table("corrections").delete().eq("session_id", session_db_id).execute()
        self._db.table("resolutions").delete().eq("session_id", session_db_id).execute()
        if intents:
            self._db.table("intents").insert(intents).execute()
        if corrections:
            self._db.table("corrections").insert(corrections).execute()
        self._db.table("resolutions").insert(resolution).execute()

    def get_session_intents(self, session_db_id: str) -> list[dict]:
        res = self._db.table("intents").select("intent, display_name, weight, msg_start, msg_end, created_at").eq("session_id", session_db_id).order("msg_start").execute()
        return res.data or []

    def get_session_corrections(self, session_db_id: str) -> list[dict]:
        res = self._db.table("corrections").select("msg_index, reason, created_at").eq("session_id", session_db_id).order("created_at").execute()
        return res.data or []

    def get_session_resolution(self, session_db_id: str) -> dict | None:
        res = self._db.table("resolutions").select("resolved, resolution_type, summary, created_at").eq("session_id", session_db_id).maybe_single().execute()
        return res.data if res and res.data else None

    # --- Intent Library ---

    def get_intent_library(self, project_id: str) -> list[dict]:
        res = self._db.table("intent_library").select("id, name, display_name, description, session_count").eq("project_id", project_id).order("session_count", desc=True).execute()
        return res.data or []

    def upsert_intent_library(self, project_id: str, name: str, display_name: str) -> dict:
        res = self._db.table("intent_library").upsert(
            {"project_id": project_id, "name": name, "display_name": display_name},
            on_conflict="project_id,name",
        ).execute()
        return res.data[0] if res and res.data else {}

    # --- Session meta ---

    def get_session_meta(self, session_db_id: str) -> dict | None:
        res = self._db.table("sessions").select("id, project_id, agent_id").eq("id", session_db_id).maybe_single().execute()
        return res.data if res and res.data else None

    def update_session_analysis_meta(self, session_db_id: str, summary: str | None) -> None:
        self._db.table("sessions").update({"summary": summary, "last_analyzed_at": "now()"}).eq("id", session_db_id).execute()

    def count_session_events(self, session_db_id: str) -> int:
        res = self._db.table("events").select("id", count="exact").eq("session_id", session_db_id).execute()
        return res.count or 0

    # --- Analytics ---

    def get_resolution_data(self, session_ids: list[str]) -> list[dict]:
        if not session_ids:
            return []
        res = self._db.table("resolutions").select("session_id, resolved").in_("session_id", session_ids).execute()
        return res.data or []

    def get_correction_session_ids(self, session_ids: list[str]) -> list[str]:
        if not session_ids:
            return []
        res = self._db.table("corrections").select("session_id").in_("session_id", session_ids).execute()
        return list(set(r["session_id"] for r in (res.data or [])))

    def get_intent_weights(self, session_ids: list[str]) -> list[dict]:
        if not session_ids:
            return []
        res = self._db.table("intents").select("intent, display_name, weight").in_("session_id", session_ids).execute()
        from collections import defaultdict
        totals: dict[str, dict] = defaultdict(lambda: {"weight": 0.0, "display_name": ""})
        for r in (res.data or []):
            totals[r["intent"]]["weight"] += r.get("weight") or 0
            totals[r["intent"]]["display_name"] = r.get("display_name") or r["intent"]
        return sorted(
            [{"intent": k, "display_name": v["display_name"], "weight": round(v["weight"], 3)} for k, v in totals.items()],
            key=lambda x: -x["weight"],
        )[:10]
