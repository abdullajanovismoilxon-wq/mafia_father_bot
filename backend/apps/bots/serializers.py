from rest_framework import serializers
from .models import Bot, BotCredential, BotConfiguration, BotStatus, RuntimeStatus


class BotConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotConfiguration
        fields = (
            'id', 'language', 'night_duration_seconds',
            'day_duration_seconds', 'voting_duration_seconds',
            'allow_custom_roles', 'show_roles_on_death', 'extra_settings'
        )


class BotSerializer(serializers.ModelSerializer):
    configuration = BotConfigurationSerializer(read_only=True)
    bot_token = serializers.CharField(write_only=True, required=False, help_text="Telegram Bot Token from BotFather")
    masked_token = serializers.SerializerMethodField()

    class Meta:
        model = Bot
        fields = (
            'id', 'name', 'telegram_username', 'telegram_bot_id',
            'status', 'runtime_status', 'description', 'configuration',
            'bot_token', 'masked_token', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'status', 'runtime_status', 'created_at', 'updated_at')

    def get_masked_token(self, obj) -> str:
        if hasattr(obj, 'credential'):
            return obj.credential.get_masked_token()
        return "****"

    def create(self, validated_data):
        bot_token = validated_data.pop('bot_token', None)
        request = self.context.get('request')
        validated_data['owner'] = request.user
        validated_data['status'] = BotStatus.ACTIVE if bot_token else BotStatus.PENDING

        bot = Bot.objects.create(**validated_data)

        # Create default BotConfiguration
        BotConfiguration.objects.create(bot=bot)

        # Create encrypted BotCredential
        if bot_token:
            credential = BotCredential(bot=bot)
            credential.set_token(bot_token)
            credential.save()

        return bot

    def update(self, instance, validated_data):
        bot_token = validated_data.pop('bot_token', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if bot_token:
            credential, _ = BotCredential.objects.get_or_create(bot=instance)
            credential.set_token(bot_token)
            credential.save()
            instance.status = BotStatus.ACTIVE
            instance.save()

        return instance
