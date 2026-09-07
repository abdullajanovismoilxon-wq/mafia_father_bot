from typing import Dict, Type
from .base import BasePaymentProvider, PaymentProviderError
from .stripe_provider import StripeProvider
from .payme_provider import PaymeProvider
from .click_provider import ClickProvider


class PaymentProviderFactory:
    """
    Factory creating PaymentProvider instances based on provider machine code.
    Applies Dependency Inversion Principle.
    """

    _PROVIDERS: Dict[str, Type[BasePaymentProvider]] = {
        'STRIPE': StripeProvider,
        'PAYME': PaymeProvider,
        'CLICK': ClickProvider,
    }

    @classmethod
    def get_provider(cls, provider_name: str) -> BasePaymentProvider:
        name = (provider_name or '').upper()
        if name not in cls._PROVIDERS:
            raise PaymentProviderError(
                f"Unsupported payment provider '{provider_name}'. "
                f"Supported providers: {list(cls._PROVIDERS.keys())}"
            )
        return cls._PROVIDERS[name]()

    @classmethod
    def list_supported_providers(cls) -> list:
        return list(cls._PROVIDERS.keys())
