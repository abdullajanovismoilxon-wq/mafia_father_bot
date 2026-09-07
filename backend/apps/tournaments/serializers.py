from rest_framework import serializers
from .models import Tournament, TournamentRound, TournamentParticipant, TournamentGame


class TournamentParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TournamentParticipant
        fields = (
            'id', 'telegram_user_id', 'display_name', 'username',
            'score', 'games_played', 'games_won', 'games_lost',
            'kills', 'survival_count', 'status', 'joined_at',
        )
        read_only_fields = fields


class TournamentRoundSerializer(serializers.ModelSerializer):
    games_count = serializers.SerializerMethodField()

    class Meta:
        model = TournamentRound
        fields = ('id', 'number', 'status', 'started_at', 'finished_at', 'games_count')
        read_only_fields = fields

    def get_games_count(self, obj):
        return obj.tournament_games.count()


class TournamentSerializer(serializers.ModelSerializer):
    """Lightweight list serializer."""
    owner_email = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = (
            'id', 'name', 'description', 'status',
            'max_players', 'players_per_game', 'total_rounds', 'current_round',
            'owner_email', 'participant_count',
            'started_at', 'finished_at', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'status', 'current_round', 'owner_email',
            'participant_count', 'started_at', 'finished_at', 'created_at', 'updated_at',
        )

    def get_owner_email(self, obj):
        return obj.owner.email

    def get_participant_count(self, obj):
        return obj.participants.filter(status='ACTIVE').count()


class TournamentDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer."""
    owner_email = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    rounds = TournamentRoundSerializer(many=True, read_only=True)
    scoring_config = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = (
            'id', 'name', 'description', 'status',
            'max_players', 'players_per_game', 'total_rounds', 'current_round',
            'game_template', 'configuration_data', 'scoring_config',
            'owner_email', 'participant_count',
            'started_at', 'finished_at', 'created_at', 'updated_at',
            'rounds',
        )
        read_only_fields = (
            'id', 'status', 'current_round', 'owner_email',
            'participant_count', 'started_at', 'finished_at', 'created_at', 'updated_at',
        )

    def get_owner_email(self, obj):
        return obj.owner.email

    def get_participant_count(self, obj):
        return obj.participants.filter(status='ACTIVE').count()

    def get_scoring_config(self, obj):
        return obj.get_default_scoring()

    def validate(self, data):
        max_p = data.get('max_players', self.instance.max_players if self.instance else 24)
        ppg = data.get('players_per_game', self.instance.players_per_game if self.instance else 6)
        if max_p < ppg:
            raise serializers.ValidationError("max_players must be >= players_per_game.")
        if ppg < 4:
            raise serializers.ValidationError("players_per_game must be at least 4.")
        return data


class TournamentCreateSerializer(serializers.ModelSerializer):
    """Serializer used specifically for tournament creation."""
    class Meta:
        model = Tournament
        fields = (
            'name', 'description', 'max_players', 'players_per_game',
            'total_rounds', 'game_template', 'scoring_config',
        )

    def validate_players_per_game(self, value):
        if value < 4:
            raise serializers.ValidationError("players_per_game must be at least 4.")
        return value

    def validate_total_rounds(self, value):
        if value < 1:
            raise serializers.ValidationError("total_rounds must be at least 1.")
        return value

    def validate(self, data):
        max_p = data.get('max_players', 24)
        ppg = data.get('players_per_game', 6)
        if max_p < ppg:
            raise serializers.ValidationError("max_players must be >= players_per_game.")
        return data
