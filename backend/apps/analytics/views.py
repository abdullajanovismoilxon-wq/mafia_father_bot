from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.bots.models import Bot
from apps.games.models import Game


class OverviewAnalyticsView(APIView):
    """Retrieve overview metrics for authenticated user's dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_bots = Bot.objects.filter(owner=request.user)
        total_bots = user_bots.count()
        active_bots = user_bots.filter(status='ACTIVE').count()
        total_games = Game.objects.filter(bot__owner=request.user).count()

        return Response({
            'total_bots': total_bots,
            'active_bots': active_bots,
            'total_games': total_games,
            'subscription_status': getattr(request.user.subscription, 'status', 'ACTIVE') if hasattr(request.user, 'subscription') else 'FREE',
        })
