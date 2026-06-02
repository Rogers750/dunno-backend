-- Dunno Analytics — ClickHouse Schema (events + messages only)
-- Relational tables (projects, agents, sessions, etc.) stay on Postgres.
-- Run: clickhouse-client --host $CH_HOST --query "$(cat clickhouse/schema.sql)"

CREATE DATABASE IF NOT EXISTS dunno;

USE dunno;

CREATE TABLE IF NOT EXISTS events (
    id          UUID    DEFAULT generateUUIDv4(),
    project_id  UUID,
    session_id  UUID,
    agent_id    UUID,
    agent_version_id UUID,
    person_id   UUID,
    fingerprint_id UUID,
    event_name  String,
    properties  String  DEFAULT '{}',
    model       String  DEFAULT '',
    input_tokens  Int32 DEFAULT 0,
    output_tokens Int32 DEFAULT 0,
    latency_ms    Int32 DEFAULT 0,
    created_at  DateTime64(3) DEFAULT now64()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (project_id, created_at, id);

CREATE TABLE IF NOT EXISTS messages (
    id           UUID   DEFAULT generateUUIDv4(),
    event_id     UUID,
    role         String,
    content      String DEFAULT '',
    tool_calls   String DEFAULT '',
    tool_call_id String DEFAULT '',
    created_at   DateTime64(3) DEFAULT now64()
)
ENGINE = MergeTree()
ORDER BY (event_id, created_at);
