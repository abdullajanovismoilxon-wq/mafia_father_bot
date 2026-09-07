"""
Payment Provider Abstraction Interface.
Applies Dependency Inversion Principle. Control Plane depends on this abstraction,
not concrete provider implementations.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from decimal import Decimal


class PaymentProviderError(Exception):
    """Base exception for payment provider errors."""
    pass


class InvalidWebhookSignatureError(PaymentProviderError):
    """Raised when webhook signature verification fails."""
    pass


class ProviderConfigurationError(PaymentProviderError):
    """Raised when provider credentials/keys are missing from environment."""
    pass


@dataclass
class CheckoutSessionResult:
    checkout_url: str
    session_id: str
    provider: str
    metadata: Dict[str, Any]


@dataclass
class WebhookProcessResult:
    event_id: str
    event_type: str
    user_id: Optional[str]
    plan_code: Optional[str]
    provider_payment_id: Optional[str]
    amount: Optional[Decimal]
    currency: Optional[str]
    payment_status: str  # SUCCEEDED, FAILED, CANCELED
    metadata: Dict[str, Any]


class BasePaymentProvider(ABC):
    """
    Abstract Base Class for all payment provider integrations (Stripe, Payme, Click).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns provider machine code ('STRIPE', 'PAYME', 'CLICK')."""
        pass

    @abstractmethod
    def validate_configuration(self) -> bool:
        """
        Validates whether required environment keys are present.
        Raises ProviderConfigurationError if configuration is incomplete.
        """
        pass

    @abstractmethod
    def create_checkout_session(
        self,
        user,
        plan,
        return_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResult:
        """
        Creates a checkout session with the payment gateway.
        Returns CheckoutSessionResult containing redirect URL.
        """
        pass

    @abstractmethod
    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verifies webhook authenticity & signature.
        Raises InvalidWebhookSignatureError if signature is invalid.
        """
        pass

    @abstractmethod
    def process_webhook_event(self, headers: Dict[str, str], body: bytes) -> WebhookProcessResult:
        """
        Parses and verifies webhook payload, returning standardized WebhookProcessResult.
        """
        pass

    @abstractmethod
    def refund_payment(self, payment, amount: Optional[Decimal] = None, reason: str = '') -> Dict[str, Any]:
        """
        Initiates a refund with the provider.
        """
        pass

    @abstractmethod
    def get_payment_status(self, provider_payment_id: str) -> str:
        """
        Queries provider API for current status of a payment transaction.
        """
        pass
