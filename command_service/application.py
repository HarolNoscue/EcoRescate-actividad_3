from datetime import datetime, timezone
from uuid import uuid4
from .domain import Offer, BusinessError
from .ports import OfferRepository


class DonationApplication:
    def __init__(self, repository: OfferRepository):
        self.repository = repository

    def publish(self, *, provider: str, title: str, category: str, zone: str,
                quantity: int, expires_at: datetime) -> dict:
        if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
            raise BusinessError("La fecha de caducidad debe ser futura y tener zona horaria", "INVALID_EXPIRATION")
        offer = Offer(str(uuid4()), provider.strip(), title.strip(), category.strip(),
                      zone.strip(), quantity, quantity, expires_at.astimezone(timezone.utc))
        return self.repository.create(offer)

    def reserve(self, offer_id: str, organization: str, quantity: int) -> dict:
        return self.repository.claim(offer_id, organization.strip(), quantity, datetime.now(timezone.utc))

    def cancel(self, claim_id: str) -> dict:
        return self.repository.cancel(claim_id)
