from abc import ABC, abstractmethod


class BaseRepository(ABC):

    # --- Projects / Auth ---

    @abstractmethod
    def get_api_key(self, key_hash: str) -> dict | None: ...

    @abstractmethod
    def touch_api_key(self, key_id: str) -> None: ...

    @abstractmethod
    def get_project_count(self) -> int: ...

    @abstractmethod
    def create_project(self, name: str, slug: str) -> dict: ...

    @abstractmethod
    def insert_api_key(self, project_id: str, name: str, prefix: str, key_hash: str) -> None: ...

    @abstractmethod
    def list_api_keys(self, project_id: str) -> list[dict]: ...

    @abstractmethod
    def revoke_api_key(self, project_id: str, key_id: str) -> None: ...

    # --- Agents ---

    @abstractmethod
    def upsert_agent(self, project_id: str, agent_name: str, description: str | None = None, agent_number: int | None = None) -> dict: ...

    @abstractmethod
    def get_agent(self, project_id: str, agent_name: str) -> dict | None: ...

    @abstractmethod
    def list_agents(self, project_id: str) -> list[dict]: ...

    @abstractmethod
    def count_agents(self, project_id: str) -> int: ...

    @abstractmethod
    def upsert_agent_version(self, agent_id: str, name: str, description: str | None, model: str | None, system_prompt: str | None, number: int) -> dict: ...

    @abstractmethod
    def get_agent_version(self, agent_id: str, name: str) -> dict | None: ...

    @abstractmethod
    def list_agent_versions(self, agent_id: str) -> list[dict]: ...

    @abstractmethod
    def count_agent_versions(self, agent_id: str) -> int: ...

    # --- People ---

    @abstractmethod
    def upsert_person(self, project_id: str, person_id: str, properties: dict | None = None) -> dict: ...

    @abstractmethod
    def get_person(self, project_id: str, person_id: str) -> dict | None: ...

    @abstractmethod
    def update_person(self, db_id: str, properties: dict) -> dict: ...

    @abstractmethod
    def list_people(self, project_id: str) -> list[dict]: ...

    @abstractmethod
    def count_people(self, project_id: str) -> int: ...

    # --- Fingerprints ---

    @abstractmethod
    def insert_fingerprint(self, project_id: str, fingerprint_id: str, data: dict) -> dict: ...

    @abstractmethod
    def get_fingerprint_db_id(self, project_id: str, fingerprint_id: str) -> str | None: ...

    # --- Sessions ---

    @abstractmethod
    def upsert_session(self, project_id: str, session_id: str, person_id: str | None, agent_id: str | None) -> str: ...

    @abstractmethod
    def list_sessions(self, project_id: str, agent_id: str | None, limit: int, offset: int) -> list[dict]: ...

    @abstractmethod
    def get_session(self, project_id: str, session_id: str) -> dict | None: ...

    @abstractmethod
    def list_sessions_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]: ...

    # --- Events ---

    @abstractmethod
    def insert_event(self, data: dict) -> dict: ...

    @abstractmethod
    def list_events(self, project_id: str, session_db_id: str | None, limit: int) -> list[dict]: ...

    @abstractmethod
    def get_event(self, project_id: str, event_id: str) -> dict | None: ...

    @abstractmethod
    def get_session_events_with_messages(self, session_db_id: str) -> list[dict]: ...

    @abstractmethod
    def list_events_in_range(self, project_id: str, since: str, agent_id: str | None) -> list[dict]: ...

    # --- Messages ---

    @abstractmethod
    def insert_messages(self, messages: list[dict]) -> None: ...

    # --- Analysis ---

    @abstractmethod
    def replace_session_analysis(self, session_db_id: str, intents: list[dict], corrections: list[dict], resolution: dict) -> None: ...

    @abstractmethod
    def get_session_intents(self, session_db_id: str) -> list[dict]: ...

    @abstractmethod
    def get_session_corrections(self, session_db_id: str) -> list[dict]: ...

    @abstractmethod
    def get_session_resolution(self, session_db_id: str) -> dict | None: ...

    @abstractmethod
    def get_messages_for_events(self, event_ids: list[str]) -> list[dict]: ...

    # --- Intent Library ---

    @abstractmethod
    def get_intent_library(self, project_id: str) -> list[dict]: ...

    @abstractmethod
    def upsert_intent_library(self, project_id: str, name: str, display_name: str) -> dict: ...

    # --- Session meta ---

    @abstractmethod
    def get_session_meta(self, session_db_id: str) -> dict | None: ...

    @abstractmethod
    def update_session_analysis_meta(self, session_db_id: str, summary: str | None) -> None: ...

    @abstractmethod
    def count_session_events(self, session_db_id: str) -> int: ...

    # --- Analytics ---

    @abstractmethod
    def get_resolution_data(self, session_ids: list[str]) -> list[dict]: ...

    @abstractmethod
    def get_correction_session_ids(self, session_ids: list[str]) -> list[str]: ...

    @abstractmethod
    def get_intent_weights(self, session_ids: list[str]) -> list[dict]: ...
