-- Esquema de escritura: comandos, reservas y transactional outbox.
-- MVP académico: para producción se recomiendan migraciones versionadas.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS offers (
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

CREATE TABLE IF NOT EXISTS claims (
    id            TEXT PRIMARY KEY,
    offer_id      TEXT NOT NULL REFERENCES offers(id),
    organization  TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    status        TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT UNIQUE NOT NULL,
    event_type   TEXT NOT NULL,
    payload      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    published_at TEXT
);
