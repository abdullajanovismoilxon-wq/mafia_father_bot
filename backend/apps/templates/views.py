import logging
from django.db import transaction
from django.utils.text import slugify
from rest_framework import viewsets, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import GameTemplate, BotTemplate, TemplateType, TemplateVisibility, GameTemplateStatus
from .serializers import GameTemplateSerializer, GameTemplateDetailSerializer, BotTemplateSerializer

logger = logging.getLogger(__name__)


class GameTemplateViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for Game Templates + duplicate + use actions.
    Multi-tenancy: users can only modify their own templates.
    They can read PUBLIC or SYSTEM templates from other users (read-only).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = GameTemplateSerializer

    def get_queryset(self):
        user = self.request.user
        filter_type = self.request.query_params.get('type', 'all')

        if filter_type == 'mine':
            # Only this user's templates
            return GameTemplate.objects.filter(owner=user, status=GameTemplateStatus.ACTIVE)
        elif filter_type == 'system':
            return GameTemplate.objects.filter(
                template_type=TemplateType.SYSTEM, status=GameTemplateStatus.ACTIVE
            )
        elif filter_type == 'public':
            # Public templates from all users (not system)
            return GameTemplate.objects.filter(
                visibility=TemplateVisibility.PUBLIC,
                template_type=TemplateType.USER,
                status=GameTemplateStatus.ACTIVE,
            ).exclude(owner=user)
        else:
            # All accessible: own + system + public
            from django.db.models import Q
            return GameTemplate.objects.filter(
                Q(owner=user) |
                Q(template_type=TemplateType.SYSTEM) |
                Q(visibility=TemplateVisibility.PUBLIC, template_type=TemplateType.USER)
            ).filter(status=GameTemplateStatus.ACTIVE).distinct()

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return GameTemplateDetailSerializer
        return GameTemplateSerializer

    def get_object(self):
        """Override to allow reading public/system templates but restrict writes."""
        obj = super().get_object()
        if self.action not in ('retrieve', 'list', 'duplicate', 'use'):
            # Write actions: must own the template
            if obj.owner != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You do not own this template.")
        return obj

    def perform_create(self, serializer):
        from apps.subscriptions.services import EntitlementService, EntitlementLimitExceededError
        from rest_framework.exceptions import APIException

        try:
            EntitlementService.can_create_template(self.request.user)
        except EntitlementLimitExceededError as e:
            class PlanLimitReached(APIException):
                status_code = 403
                default_detail = 'Plan limit reached.'
            err = PlanLimitReached()
            err.detail = {
                'code': 'PLAN_LIMIT_REACHED',
                'feature': e.feature_code,
                'limit': e.limit,
                'current_usage': e.current_usage,
                'detail': str(e),
            }
            raise err

        serializer.save(
            owner=self.request.user,
            template_type=TemplateType.USER,
        )

    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not own this template.")
        # Soft delete
        instance.status = GameTemplateStatus.ARCHIVED
        instance.save(update_fields=['status'])

    @action(detail=True, methods=['post'], url_path='duplicate')
    def duplicate(self, request, pk=None):
        """
        Create a personal copy of a template (own, public, or system).
        The copy is independent — changes to the original won't affect it.
        """
        original = self.get_object()

        with transaction.atomic():
            copy = GameTemplate.objects.create(
                owner=request.user,
                name=f"{original.name} (Copy)",
                slug='',  # will be auto-generated in save()
                description=original.description,
                template_type=TemplateType.USER,
                visibility=TemplateVisibility.PRIVATE,
                status=GameTemplateStatus.ACTIVE,
                game_mode=original.game_mode,
                configuration_data=dict(original.configuration_data),
                role_distribution_data=list(original.role_distribution_data),
                source_template=original,
                version=1,
            )

        serializer = GameTemplateDetailSerializer(copy)
        logger.info(f"Template #{original.id} duplicated -> #{copy.id} by {request.user.email}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='use')
    def use(self, request, pk=None):
        """
        Apply this template to a bot or return its configuration for game creation.
        Body: {"bot_id": "<uuid>"}  — optional, updates bot's default template.
        """
        template = self.get_object()

        bot_id = request.data.get('bot_id')
        if bot_id:
            from apps.bots.models import Bot
            try:
                bot = Bot.objects.get(id=bot_id, owner=request.user)
            except Bot.DoesNotExist:
                return Response({'detail': 'Bot not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Update BotConfiguration to reference this template (stored in extra_settings)
            from apps.bots.models import BotConfiguration
            config, _ = BotConfiguration.objects.get_or_create(bot=bot)
            config.extra_settings['default_game_template_id'] = str(template.id)
            config.save(update_fields=['extra_settings'])

            return Response({
                'detail': f"Template '{template.name}' applied to bot '{bot.name}'.",
                'template': GameTemplateSerializer(template).data,
            })

        # Without bot: just return the configuration data
        return Response({
            'detail': 'Template configuration data.',
            'template': GameTemplateDetailSerializer(template).data,
            'configuration_data': template.get_default_configuration(),
            'role_distribution_data': template.role_distribution_data,
        })


class BotTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for Bot Templates."""
    permission_classes = [IsAuthenticated]
    serializer_class = BotTemplateSerializer

    def get_queryset(self):
        return BotTemplate.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
