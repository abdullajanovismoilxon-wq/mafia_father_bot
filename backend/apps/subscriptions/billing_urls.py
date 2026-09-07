from django.urls import path
from .views import (
    PlanListView, MySubscriptionView, CheckoutView, CancelSubscriptionView,
    ResumeSubscriptionView, MyPaymentsListView, MyInvoicesListView,
    MyUsageView, MyEntitlementsView, WebhookReceiverView,
)

urlpatterns = [
    path('plans/', PlanListView.as_view(), name='billing_plans'),
    path('subscription/', MySubscriptionView.as_view(), name='billing_subscription'),
    path('checkout/', CheckoutView.as_view(), name='billing_checkout'),
    path('cancel/', CancelSubscriptionView.as_view(), name='billing_cancel'),
    path('resume/', ResumeSubscriptionView.as_view(), name='billing_resume'),
    path('payments/', MyPaymentsListView.as_view(), name='billing_payments'),
    path('invoices/', MyInvoicesListView.as_view(), name='billing_invoices'),
    path('usage/', MyUsageView.as_view(), name='billing_usage'),
    path('entitlements/', MyEntitlementsView.as_view(), name='billing_entitlements'),
    path('webhooks/<str:provider_name>/', WebhookReceiverView.as_view(), name='billing_webhook'),
]
