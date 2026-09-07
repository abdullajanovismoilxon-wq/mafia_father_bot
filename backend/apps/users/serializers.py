from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserRole

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    group_name = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'group_name', 'password', 'password_confirm')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        group_name = validated_data.pop('group_name', '')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            group_name=group_name,
            role=UserRole.ADMIN if group_name else UserRole.USER
        )
        return user


class CoAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, required=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'group_name', 'role', 'created_at', 'password')
        read_only_fields = ('id', 'group_name', 'created_at')

    def create(self, validated_data):
        request_user = self.context['request'].user
        password = validated_data.pop('password', None)
        if not password:
            import secrets
            password = secrets.token_urlsafe(8)

        co_admin = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password,
            group_name=request_user.group_name or f"{request_user.username}'s Group",
            parent_admin=request_user.effective_owner,
            role=UserRole.MODERATOR
        )
        co_admin._raw_password = password
        return co_admin


class UserProfileSerializer(serializers.ModelSerializer):
    is_superadmin = serializers.SerializerMethodField()
    effective_group_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'telegram_id', 'group_name',
            'effective_group_name', 'role', 'is_platform_owner', 'is_superadmin',
            'is_active', 'created_at'
        )
        read_only_fields = ('id', 'email', 'created_at', 'role')

    def get_is_superadmin(self, obj) -> bool:
        return obj.role == UserRole.SUPERADMIN or obj.is_platform_owner or obj.is_superuser

    def get_effective_group_name(self, obj) -> str:
        return obj.effective_owner.group_name or f"{obj.effective_owner.username}'s Group"
