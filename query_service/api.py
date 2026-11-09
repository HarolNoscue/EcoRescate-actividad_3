import os
from fastapi import FastAPI
from .projector import ProjectionStore


def create_app(db_path: str | None = None):
    store = ProjectionStore(db_path or os.getenv("QUERY_DB", "/tmp/ecorescate/query.sqlite3"))
    app = FastAPI(title="EcoRescate | Servicio de consultas", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "queries"}

    @app.get("/offers")
    def list_offers():
        return store.list_offers()

    @app.get("/claims")
    def list_claims():
        return store.list_claims()

    @app.get("/metrics")
    def metrics():
        return store.metrics()

    app.state.store = store
    return app


app = create_app()
