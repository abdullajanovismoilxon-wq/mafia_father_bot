from rest_framework import serializers
from .models import (
    Game, Player, Role, GamePhase, RoleTeam,
    GameConfiguration, RoleDistributionRule, RoleAbility, AbilityType, AbilityPhase,
)


# ---------------------------------------------------------------------------
# Role Serializers
# ---------------------------------------------------------------------------

class RoleAbilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleAbility
        fields = ('id', 'ability_type', 'phase', 'target_required', 'uses_per_game', 'cooldown_rounds', 'allowed_targets')


class RoleSerializer(serializers.ModelSerializer):
    """Lightweight role serializer for lists."""
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'name', 'code', 'team', 'description', 'is_system', 'is_active', 'priority', 'is_mine')
        read_only_fields = ('id', 'is_system', 'is_active')

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.owner == request.user
        return False


class RoleDetailSerializer(serializers.ModelSerializer):
    """Full role serializer with abilities."""
    abilities = RoleAbilitySerializer(many=True, required=False)

    class Meta:
        model = Role
        fields = (
            'id', 'name', 'code', 'team', 'description',
            'is_system', 'is_active', 'priority', 'abilities', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'is_system', 'created_at', 'updated_at')

    def validate_code(self, value):
        import re
        if not re.match(r'^[a-z0-9_-]+$', value):
            raise serializers.ValidationError("code must be lowercase letters, numbers, hyphens, or underscores.")
        return value

    def validate_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Role name must be at least 2 characters.")
        return value.strip()

    def create(self, validated_data):
        abilities_data = validated_data.pop('abilities', [])
        role = Role.objects.create(**validated_data)
        for ability_data in abilities_data:
            RoleAbility.objects.create(role=role, **ability_data)
        return role

    def update(self, instance, validated_data):
        abilities_data = validated_data.pop('abilities', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if abilities_data is not None:
            instance.abilities.all().delete()
            for ability_data in abilities_data:
                RoleAbility.objects.create(role=instance, **ability_data)
        return instance


# ---------------------------------------------------------------------------
# Player Serializer (Phase 2 preserved)
# ---------------------------------------------------------------------------

class PlayerSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True, default=None)
    role_team = serializers.CharField(source='role.team', read_only=True, default=None)

    class Meta:
        model = Player
        fields = (
            'id', 'telegram_user_id', 'username', 'display_name',
            'role_name', 'role_team', 'is_alive', 'is_ready',
            'eliminated_at', 'eliminated_reason', 'created_at'
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Hide role_name & role_team for living players if game is in progress
        request = self.context.get('request')
        game = instance.game
        if game.phase not in [GamePhase.FINISHED, GamePhase.CANCELED] and instance.is_alive:
            data['role_name'] = 'HIDDEN'
            data['role_team'] = 'HIDDEN'
        return data


# ---------------------------------------------------------------------------
# Game Serializers
# ---------------------------------------------------------------------------

class GameSerializer(serializers.ModelSerializer):
    bot_name = serializers.CharField(source='bot.name', read_only=True)
    players_count = serializers.IntegerField(source='players.count', read_only=True)
    alive_players_count = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = (
            'id', 'bot', 'bot_name', 'chat_id', 'status', 'phase',
            'round_number', 'winner_team', 'players_count',
            'alive_players_count', 'started_at', 'finished_at', 'created_at'
        )

    def get_alive_players_count(self, obj) -> int:
        return obj.players.filter(is_alive=True).count()


class GameDetailSerializer(GameSerializer):
    players = PlayerSerializer(many=True, read_only=True)

    class Meta(GameSerializer.Meta):
        fields = GameSerializer.Meta.fields + ('players',)


# ---------------------------------------------------------------------------
# Phase 3 — Configuration Serializers
# ---------------------------------------------------------------------------

class RoleDistributionRuleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    role_team = serializers.CharField(source='role.team', read_only=True)

    class Meta:
        model = RoleDistributionRule
        fields = (
            'id', 'role', 'role_name', 'role_code', 'role_team',
            'distribution_type', 'min_count', 'max_count', 'percentage', 'priority',
        )

    def validate(self, data):
        min_count = data.get('min_count', 1)
        max_count = data.get('max_count', 1)
        percentage = data.get('percentage', 0)
        dist_type = data.get('distribution_type', 'EXACT')

        if min_count < 0:
            raise serializers.ValidationError("min_count cannot be negative.")
        if max_count < min_count:
            raise serializers.ValidationError("max_count cannot be less than min_count.")
        if dist_type == 'PERCENTAGE' and not (0 <= percentage <= 100):
            raise serializers.ValidationError("percentage must be between 0 and 100.")
        return data


class GameConfigurationSerializer(serializers.ModelSerializer):
    distribution_rules = RoleDistributionRuleSerializer(many=True, required=False)

    class Meta:
        model = GameConfiguration
        fields = (
            'id', 'name', 'game_mode', 'bot',
            'minimum_players', 'maximum_players',
            'night_duration', 'discussion_duration', 'voting_duration',
            'allow_self_vote', 'allow_self_protection', 'reveal_role_on_elimination',
            'tie_behavior', 'mafia_vote_mode', 'allow_player_rejoin',
            'automatic_phase_transition', 'day_discussion_enabled',
            'distribution_rules',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, data):
        min_p = data.get('minimum_players', 4)
        max_p = data.get('maximum_players', 20)
        if min_p > max_p:
            raise serializers.ValidationError("minimum_players cannot exceed maximum_players.")
        if min_p < 2:
            raise serializers.ValidationError("minimum_players must be at least 2.")
        if data.get('night_duration', 60) < 10:
            raise serializers.ValidationError("night_duration must be at least 10 seconds.")
        if data.get('voting_duration', 60) < 10:
            raise serializers.ValidationError("voting_duration must be at least 10 seconds.")
        return data

    def create(self, validated_data):
        rules_data = validated_data.pop('distribution_rules', [])
        config = GameConfiguration.objects.create(**validated_data)
        for rule_data in rules_data:
            RoleDistributionRule.objects.create(configuration=config, **rule_data)
        return config

    def update(self, instance, validated_data):
        rules_data = validated_data.pop('distribution_rules', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if rules_data is not None:
            instance.distribution_rules.all().delete()
            for rule_data in rules_data:
                RoleDistributionRule.objects.create(configuration=instance, **rule_data)
        return instance
