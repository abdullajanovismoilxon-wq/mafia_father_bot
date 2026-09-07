from django.urls import path
from .views import MyPaymentsListView

urlpatterns = [
    path('', MyPaymentsListView.as_view(), name='my_payments'),
]
