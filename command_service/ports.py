from abc import ABC, abstractmethod
from datetime import datetime
from .domain import Offer


class OfferRepository(ABC):
    @abstractmethod
    def create(self, offer: Offer) -> dict: ...

    @abstractmethod
    def claim(self, offer_id: str, organization: str, quantity: int, now: datetime) -> dict: ...

    @abstractmethod
    def cancel(self, claim_id: str) -> dict: ...
