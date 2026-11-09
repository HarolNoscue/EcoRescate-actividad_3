import sqlite3
from pathlib import Path
from datetime import datetime, timezone

SCHEMA_PATH = Path(__file__).parent / "sql" / "schema.sql"



class ProjectionStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def apply(self, event: dict) -> bool:
        """False significa que ese ID ya fue procesado. Transacción atómica."""
        if event.get("schema_version") != 1:
            raise ValueError("Versión de evento no soportada")
        if event.get("event_type") not in {"offer.created", "offer.reserved", "offer.released"}:
            raise ValueError("Evento desconocido")
        offer = event["data"]["offer"]
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute("SELECT 1 FROM inbox WHERE event_id=?", (event["event_id"],)).fetchone()
            if duplicate:
                db.rollback()
                return False
            # Un evento retrasado no sobrescribe una proyección más reciente.
            db.execute("""INSERT INTO offer_views
             (id,provider,title,category,zone,total_quantity,available_quantity,expires_at,version)
             VALUES (:id,:provider,:title,:category,:zone,:total_quantity,:available_quantity,:expires_at,:version)
             ON CONFLICT(id) DO UPDATE SET
               provider=excluded.provider, title=excluded.title, category=excluded.category,
               zone=excluded.zone, total_quantity=excluded.total_quantity,
               available_quantity=excluded.available_quantity, expires_at=excluded.expires_at,
               version=excluded.version
             WHERE excluded.version > offer_views.version""", offer)
            claim = event["data"].get("claim")
            if claim:
                db.execute("""INSERT INTO claim_views(id,offer_id,organization,quantity,status,created_at)
                 VALUES (:id,:offer_id,:organization,:quantity,:status,:created_at)
                 ON CONFLICT(id) DO UPDATE SET status=excluded.status
                 WHERE claim_views.status != 'CANCELLED'""", claim)
            db.execute("INSERT INTO inbox VALUES (?,?,?)",
                       (event["event_id"], event["event_type"], datetime.now(timezone.utc).isoformat()))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_offers(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM offer_views ORDER BY rowid DESC").fetchall()
            now = datetime.now(timezone.utc)
            result = []
            for row in rows:
                item = dict(row)
                expiry = datetime.fromisoformat(item["expires_at"])
                item["status"] = ("EXPIRED" if expiry <= now else
                                  "EXHAUSTED" if item["available_quantity"] == 0 else "AVAILABLE")
                result.append(item)
            return result

    def list_claims(self):
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM claim_views ORDER BY created_at DESC")]

    def metrics(self):
        with self._connect() as db:
            offers = db.execute("SELECT COUNT(*) FROM offer_views").fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM claim_views WHERE status='ACTIVE'").fetchone()[0]
            units = db.execute("SELECT COALESCE(SUM(quantity),0) FROM claim_views WHERE status='ACTIVE'").fetchone()[0]
            events = db.execute("SELECT COUNT(*) FROM inbox").fetchone()[0]
            return {"published_offers": offers, "active_claims": active,
                    "reserved_units": units, "processed_events": events,
                    "consistency": "eventual"}
