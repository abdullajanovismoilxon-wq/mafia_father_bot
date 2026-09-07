from rest_framework import serializers
from .models import GameTemplate, BotTemplate


class GameTemplateSerializer(serializers.ModelSerializer):
    """Lightweight list serializer."""
    owner_email = serializers.SerializerMethodField()
    is_owned_by_me = serializers.SerializerMethodField()

    class Meta:
        model = GameTemplate
        fields = (
            'id', 'name', 'slug', 'description', 'template_type', 'visibility',
            'game_mode', 'status', 'version', 'owner_email', 'is_owned_by_me',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'slug', 'status', 'version', 'created_at', 'updated_at')

    def get_owner_email(self, obj):
        return obj.owner.email if obj.owner else 'SYSTEM'

    def get_is_owned_by_me(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.owner == request.user
        return False


class GameTemplateDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer including configuration data and role distribution."""
    owner_email = serializers.SerializerMethodField(read_only=True)
    source_template_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = GameTemplate
        fields = (
            'id', 'name', 'slug', 'description', 'template_type', 'visibility',
            'game_mode', 'status', 'version',
            'configuration_data', 'role_distribution_data',
            'owner_email', 'source_template_name',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'slug', 'template_type', 'status', 'version', 'created_at', 'updated_at')

    def get_owner_email(self, obj):
        return obj.owner.email if obj.owner else 'SYSTEM'

    def get_source_template_name(self, obj):
        return obj.source_template.name if obj.source_template else None

    def validate_configuration_data(self, value):
        """Validate configuration_data structure."""
        required_numeric = ['minimum_players', 'maximum_players', 'night_duration',
                            'discussion_duration', 'voting_duration']
        for key in required_numeric:
            if key in value and not isinstance(value[key], int):
                raise serializers.ValidationError(f"'{key}' must be an integer.")

        min_p = value.get('minimum_players', 4)
        max_p = value.get('maximum_players', 20)
        if min_p > max_p:
            raise serializers.ValidationError("minimum_players cannot exceed maximum_players.")
        if min_p < 2:
            raise serializers.ValidationError("minimum_players must be at least 2.")

        night = value.get('night_duration', 60)
        voting = value.get('voting_duration', 60)
        if night < 10:
            raise serializers.ValidationError("night_duration must be at least 10 seconds.")
        if voting < 10:
            raise serializers.ValidationError("voting_duration must be at least 10 seconds.")

        return value

    def validate_role_distribution_data(self, value):
        """Validate role_distribution_data is a list of dicts with required fields."""
        if not isinstance(value, list):
            raise serializers.ValidationError("role_distribution_data must be a list.")
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each role distribution item must be a dict.")
            for required in ('role_code', 'min_count'):
                if required not in item:
                    raise serializers.ValidationError(f"Each role distribution item must have '{required}'.")
        return value


class BotTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotTemplate
        fields = (
            'id', 'name', 'description', 'default_language',
            'default_game_template', 'game_mode', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
