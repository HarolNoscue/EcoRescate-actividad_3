-- Esquema de lectura: CQRS y recepción idempotente de eventos.
-- MVP académico: para producción se recomiendan migraciones versionadas.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS offer_views (
    id                 TEXT PRIMARY KEY,
    provider           TEXT NOT NULL,
    title              TEXT NOT NULL,
    category           TEXT NOT NULL,
    zone               TEXT NOT NULL,
    total_quantity     INTEGER NOT NULL,
    available_quantity INTEGER NOT NULL,
    expires_at         TEXT NOT NULL,
    version            INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_views (
    id           TEXT PRIMARY KEY,
    offer_id     TEXT NOT NULL,
    organization TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbox (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    processed_at TEXT NOT NULL
);
