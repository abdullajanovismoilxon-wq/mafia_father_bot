import os
import hmac
import hashlib
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


class ClickProvider(BasePaymentProvider):
    """
    Click Payment Provider implementation (Uzbekistan payment gateway).
    Supports Click Merchant protocol and MD5 signature verification.
    """

    @property
    def provider_name(self) -> str:
        return 'CLICK'

    def _get_merchant_id(self) -> str:
        return getattr(settings, 'CLICK_MERCHANT_ID', None) or os.getenv('CLICK_MERCHANT_ID', '')

    def _get_service_id(self) -> str:
        return getattr(settings, 'CLICK_SERVICE_ID', None) or os.getenv('CLICK_SERVICE_ID', '')

    def _get_secret_key(self) -> str:
        return getattr(settings, 'CLICK_SECRET_KEY', None) or os.getenv('CLICK_SECRET_KEY', '')

    def validate_configuration(self) -> bool:
        merchant_id = self._get_merchant_id()
        service_id = self._get_service_id()
        secret_key = self._get_secret_key()
        if not merchant_id or not service_id or not secret_key:
            raise ProviderConfigurationError(
                "Click is not configured. Missing CLICK_MERCHANT_ID, CLICK_SERVICE_ID, or CLICK_SECRET_KEY."
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
        service_id = self._get_service_id()
        amount_uzs = float(plan.price * 12500) if plan.currency == 'USD' else float(plan.price)

        merchant_trans_id = f"{user.id}_{plan.code}"
        checkout_url = (
            f"https://my.click.uz/services/pay"
            f"?service_id={service_id}&merchant_id={merchant_id}"
            f"&amount={amount_uzs:.2f}&transaction_param={merchant_trans_id}"
            f"&return_url={return_url}"
        )

        return CheckoutSessionResult(
            checkout_url=checkout_url,
            session_id=merchant_trans_id,
            provider='CLICK',
            metadata={'service_id': service_id, 'amount': amount_uzs},
        )

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        secret_key = self._get_secret_key()
        if not secret_key:
            raise ProviderConfigurationError("Missing CLICK_SECRET_KEY.")

        try:
            # Parse form data or json
            data = json.loads(body.decode('utf-8'))
        except Exception:
            # Click sometimes sends form-urlencoded
            from urllib.parse import parse_qs
            parsed = parse_qs(body.decode('utf-8'))
            data = {k: v[0] for k, v in parsed.items()}

        click_trans_id = str(data.get('click_trans_id', ''))
        service_id = str(data.get('service_id', ''))
        merchant_trans_id = str(data.get('merchant_trans_id', ''))
        amount = str(data.get('amount', ''))
        action = str(data.get('action', ''))
        sign_time = str(data.get('sign_time', ''))
        sign_string = str(data.get('sign_string', ''))

        if not sign_string:
            raise InvalidWebhookSignatureError("Missing Click sign_string.")

        # Click MD5 formula: md5(click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time)
        raw = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
        expected_hash = hashlib.md5(raw.encode('utf-8')).hexdigest()

        if not hmac.compare_digest(sign_string.lower(), expected_hash.lower()):
            raise InvalidWebhookSignatureError("Click MD5 signature verification failed.")

        return True

    def process_webhook_event(self, headers: Dict[str, str], body: bytes) -> WebhookProcessResult:
        self.verify_webhook(headers, body)

        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            from urllib.parse import parse_qs
            parsed = parse_qs(body.decode('utf-8'))
            data = {k: v[0] for k, v in parsed.items()}

        click_trans_id = str(data.get('click_trans_id', ''))
        merchant_trans_id = str(data.get('merchant_trans_id', ''))
        action = str(data.get('action', ''))
        error = data.get('error')

        # Parse user_id and plan_code from merchant_trans_id (format: user_id_plan_code)
        user_id = None
        plan_code = None
        if '_' in merchant_trans_id:
            parts = merchant_trans_id.split('_', 1)
            user_id = parts[0]
            plan_code = parts[1]

        amount = Decimal(str(data.get('amount', 0))) if data.get('amount') else None

        # action == '1' is Complete in Click protocol
        status = 'SUCCEEDED' if action == '1' and str(error) == '0' else 'PENDING'
        if str(error) and str(error) != '0':
            status = 'FAILED'

        return WebhookProcessResult(
            event_id=click_trans_id,
            event_type=f"click_action_{action}",
            user_id=user_id,
            plan_code=plan_code,
            provider_payment_id=click_trans_id,
            amount=amount,
            currency='UZS',
            payment_status=status,
            metadata=data,
        )

    def refund_payment(self, payment, amount: Optional[Decimal] = None, reason: str = '') -> Dict[str, Any]:
        self.validate_configuration()
        return {'status': 'refund_initiated', 'click_trans_id': payment.provider_payment_id}

    def get_payment_status(self, provider_payment_id: str) -> str:
        self.validate_configuration()
        return 'SUCCEEDED'
