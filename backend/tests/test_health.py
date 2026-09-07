from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status


class ObservabilityHealthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_liveness_health_endpoint(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')

    def test_readiness_health_endpoint(self):
        response = self.client.get('/health/ready/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        self.assertIn('checks', response.data)
        self.assertEqual(response.data['checks']['database'], 'healthy')
