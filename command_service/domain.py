from dataclasses import dataclass
from datetime import datetime, timezone


class BusinessError(Exception):
    def __init__(self, message: str, code: str = "BUSINESS_RULE"):
        super().__init__(message)
        self.code = code


@dataclass
class Offer:
    id: str
    provider: str
    title: str
    category: str
    zone: str
    total_quantity: int
    available_quantity: int
    expires_at: datetime
    version: int = 1

    def _ensure_not_expired(self, now: datetime) -> None:
        if self.expires_at <= now:
            raise BusinessError("La donación ya venció", "OFFER_EXPIRED")

    def reserve(self, quantity: int, now: datetime) -> None:
        self._ensure_not_expired(now)
        if quantity <= 0:
            raise BusinessError("La cantidad debe ser positiva", "INVALID_QUANTITY")
        if quantity > self.available_quantity:
            raise BusinessError("No existe inventario suficiente", "INSUFFICIENT_STOCK")
        self.available_quantity -= quantity
        self.version += 1

    def release(self, quantity: int) -> None:
        if quantity <= 0 or self.available_quantity + quantity > self.total_quantity:
            raise BusinessError("No es posible devolver esa cantidad", "INVALID_RELEASE")
        self.available_quantity += quantity
        self.version += 1

    @property
    def status(self) -> str:
        if self.expires_at <= datetime.now(timezone.utc):
            return "EXPIRED"
        return "EXHAUSTED" if self.available_quantity == 0 else "AVAILABLE"

    def snapshot(self) -> dict:
        return {
            "id": self.id, "provider": self.provider, "title": self.title,
            "category": self.category, "zone": self.zone,
            "total_quantity": self.total_quantity,
            "available_quantity": self.available_quantity,
            "expires_at": self.expires_at.isoformat(),
            "version": self.version,
        }
