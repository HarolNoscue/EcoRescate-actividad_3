import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .domain import Offer, BusinessError
from .ports import OfferRepository


SCHEMA_PATH = Path(__file__).parent / "sql" / "schema.sql"



class SQLiteOfferRepository(OfferRepository):
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @contextmanager
    def _write(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")  # Serializa escritores; evita sobre-reserva.
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _load(db, offer_id: str) -> Offer:
        row = db.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
        if row is None:
            raise BusinessError("Donación no encontrada", "NOT_FOUND")
        return Offer(row["id"], row["provider"], row["title"], row["category"],
                     row["zone"], row["total_quantity"], row["available_quantity"],
                     datetime.fromisoformat(row["expires_at"]), row["version"])

    @staticmethod
    def _save_offer(db, offer: Offer):
        db.execute("UPDATE offers SET available_quantity=?, version=? WHERE id=?",
                   (offer.available_quantity, offer.version, offer.id))

    @staticmethod
    def _write_event(db, kind: str, data: dict):
        now = datetime.now(timezone.utc).isoformat()
        envelope = {
            "event_id": str(uuid4()), "event_type": kind, "occurred_at": now,
            "schema_version": 1, "data": data,
        }
        db.execute("INSERT INTO outbox(event_id,event_type,payload,created_at) VALUES (?,?,?,?)",
                   (envelope["event_id"], kind, json.dumps(envelope), now))

    def create(self, offer: Offer) -> dict:
        with self._write() as db:
            db.execute("INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?)",
                       (offer.id, offer.provider, offer.title, offer.category, offer.zone,
                        offer.total_quantity, offer.available_quantity,
                        offer.expires_at.isoformat(), offer.version))
            self._write_event(db, "offer.created", {"offer": offer.snapshot()})
        return offer.snapshot()

    def claim(self, offer_id: str, organization: str, quantity: int, now: datetime) -> dict:
        with self._write() as db:
            offer = self._load(db, offer_id)
            offer.reserve(quantity, now)
            self._save_offer(db, offer)
            claim = {"id": str(uuid4()), "offer_id": offer_id, "organization": organization,
                     "quantity": quantity, "status": "ACTIVE", "created_at": now.isoformat()}
            db.execute("INSERT INTO claims VALUES (?,?,?,?,?,?)",
                       (claim["id"], claim["offer_id"], claim["organization"],
                        claim["quantity"], claim["status"], claim["created_at"]))
            self._write_event(db, "offer.reserved", {"offer": offer.snapshot(), "claim": claim})
        return claim

    def cancel(self, claim_id: str) -> dict:
        with self._write() as db:
            row = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
            if row is None:
                raise BusinessError("Reserva no encontrada", "NOT_FOUND")
            if row["status"] != "ACTIVE":
                raise BusinessError("La reserva ya estaba cancelada", "ALREADY_CANCELLED")
            offer = self._load(db, row["offer_id"])
            offer.release(row["quantity"])
            self._save_offer(db, offer)
            db.execute("UPDATE claims SET status='CANCELLED' WHERE id=?", (claim_id,))
            claim = dict(row)
            claim["status"] = "CANCELLED"
            self._write_event(db, "offer.released", {"offer": offer.snapshot(), "claim": claim})
        return claim

    def pending_outbox(self, limit: int = 100):
        with self._connect() as db:
            rows = db.execute("SELECT seq, payload FROM outbox WHERE published_at IS NULL ORDER BY seq LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def mark_published(self, seq: int):
        with self._write() as db:
            db.execute("UPDATE outbox SET published_at=? WHERE seq=? AND published_at IS NULL",
                       (datetime.now(timezone.utc).isoformat(), seq))
