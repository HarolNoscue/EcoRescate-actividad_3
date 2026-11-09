import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from .application import DonationApplication
from .domain import BusinessError
from .sqlite_adapter import SQLiteOfferRepository


class NewOffer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    provider: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    zone: str = Field(min_length=2, max_length=100)
    quantity: int = Field(ge=1, le=100000)
    expires_at: datetime


class NewClaim(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    organization: str = Field(min_length=2, max_length=120)
    quantity: int = Field(ge=1, le=100000)


def create_app(db_path: str | None = None) -> FastAPI:
    repo = SQLiteOfferRepository(db_path or os.getenv("COMMAND_DB", "/tmp/ecorescate/command.sqlite3"))
    use_cases = DonationApplication(repo)
    app = FastAPI(title="EcoRescate | Servicio de comandos", version="1.0.0")

    @app.exception_handler(BusinessError)
    async def business_error_handler(_, exc: BusinessError):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404 if exc.code == "NOT_FOUND" else
                            422 if exc.code == "INVALID_EXPIRATION" else 409,
                            content={"code": exc.code, "detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "commands"}

    @app.post("/offers", status_code=201)
    def publish(body: NewOffer):
        return use_cases.publish(**body.model_dump())

    @app.post("/offers/{offer_id}/claims", status_code=201)
    def reserve(offer_id: str, body: NewClaim):
        return use_cases.reserve(offer_id, body.organization, body.quantity)

    @app.post("/claims/{claim_id}/cancel")
    def cancel(claim_id: str):
        return use_cases.cancel(claim_id)

    app.state.repository = repo
    return app


app = create_app()
