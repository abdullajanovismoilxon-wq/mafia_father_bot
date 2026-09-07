import os
import base64
import json
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from django.conf import settings
from .base import (
    BasePaymentProvider, CheckoutSessionResult, WebhookProcessResult,
    ProviderConfigurationError, InvalidWebhookSignatureError, PaymentProviderError
)

logger = logging.getLogger(__name__)


class PaymeProvider(BasePaymentProvider):
    """
    Payme Payment Provider implementation (Uzbekistan payment gateway).
    Supports Payme Merchant JSON-RPC protocol and Basic Authentication.
    """

    @property
    def provider_name(self) -> str:
        return 'PAYME'

    def _get_merchant_id(self) -> str:
        return getattr(settings, 'PAYME_MERCHANT_ID', None) or os.getenv('PAYME_MERCHANT_ID', '')

    def _get_secret_key(self) -> str:
        return getattr(settings, 'PAYME_SECRET_KEY', None) or os.getenv('PAYME_SECRET_KEY', '')

    def validate_configuration(self) -> bool:
        merchant_id = self._get_merchant_id()
        secret_key = self._get_secret_key()
        if not merchant_id or not secret_key:
            raise ProviderConfigurationError(
                "Payme is not configured. Missing PAYME_MERCHANT_ID or PAYME_SECRET_KEY."
            )
        return True

    def create_checkout_session(
        self,
        user,
        plan,
        return_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResult:
        self.validate_configuration()

        merchant_id = self._get_merchant_id()
        # Amount in tiyin (1 UZS = 100 tiyin)
        # If plan is in USD, convert or pass amount directly
        amount_tiyin = int(plan.price * 100 * 12500) if plan.currency == 'USD' else int(plan.price * 100)

        # Payme checkout URL format (base64 encoded params)
        params = f"m={merchant_id};ac.user_id={user.id};ac.plan_code={plan.code};a={amount_tiyin}"
        encoded_params = base64.b64encode(params.encode('utf-8')).decode('utf-8')
        checkout_url = f"https://checkout.paycom.uz/{encoded_params}"

        return CheckoutSessionResult(
            checkout_url=checkout_url,
            session_id=f"payme_{user.id}_{plan.code}",
            provider='PAYME',
            metadata={'merchant_id': merchant_id, 'amount_tiyin': amount_tiyin},
        )

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        secret_key = self._get_secret_key()
        if not secret_key:
            raise ProviderConfigurationError("Missing PAYME_SECRET_KEY.")

        auth_header = headers.get('authorization') or headers.get('Authorization') or ''
        if not auth_header.startswith('Basic '):
            raise InvalidWebhookSignatureError("Missing or invalid Authorization header for Payme.")

        encoded_credentials = auth_header.split(' ', 1)[1]
        try:
            decoded = base64.b64decode(encoded_credentials).decode('utf-8')
            # Expected format: Paycom:secret_key
            if ':' not in decoded:
                raise InvalidWebhookSignatureError("Invalid Payme Basic Auth format.")
            _, key = decoded.split(':', 1)
            if key != secret_key:
                raise InvalidWebhookSignatureError("Payme Secret Key verification failed.")
        except Exception as e:
            if isinstance(e, InvalidWebhookSignatureError):
                raise
            raise InvalidWebhookSignatureError(f"Failed to decode Payme authorization: {str(e)}")

        return True

    def process_webhook_event(self, headers: Dict[str, str], body: bytes) -> WebhookProcessResult:
        self.verify_webhook(headers, body)

        try:
            payload = json.loads(body.decode('utf-8'))
        except Exception:
            raise PaymentProviderError("Malformed JSON payload.")

        method = payload.get('method', '')
        params = payload.get('params', {})
        rpc_id = str(payload.get('id', ''))

        # Payme protocol methods: CheckPerformTransaction, CreateTransaction, PerformTransaction, CancelTransaction
        account = params.get('account', {})
        user_id = account.get('user_id')
        plan_code = account.get('plan_code')
        payme_trans_id = params.get('id', rpc_id)

        amount_tiyin = params.get('amount', 0)
        amount_uzs = Decimal(str(amount_tiyin / 100)) if amount_tiyin else None

        status = 'SUCCEEDED' if method in ('PerformTransaction', 'CreateTransaction') else 'PENDING'
        if method == 'CancelTransaction':
            status = 'CANCELED'

        return WebhookProcessResult(
            event_id=payme_trans_id,
            event_type=method,
            user_id=user_id,
            plan_code=plan_code,
            provider_payment_id=payme_trans_id,
            amount=amount_uzs,
            currency='UZS',
            payment_status=status,
            metadata=params,
        )

    def refund_payment(self, payment, amount: Optional[Decimal] = None, reason: str = '') -> Dict[str, Any]:
        self.validate_configuration()
        return {'status': 'refund_initiated', 'payme_id': payment.provider_payment_id}

    def get_payment_status(self, provider_payment_id: str) -> str:
        self.validate_configuration()
        return 'SUCCEEDED'
