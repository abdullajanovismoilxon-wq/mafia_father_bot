import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import User, UserRole
from apps.stats.models import PlayerProfile
from apps.economy.services import EconomyService

def create_superadmin():
    email = "superadmin@mafiabotfather.uz"
    password = "SuperAdmin2026!"
    
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': 'superadmin',
            'role': UserRole.SUPERADMIN,
            'is_platform_owner': True,
            'is_staff': True,
            'is_superuser': True,
        }
    )
    user.role = UserRole.SUPERADMIN
    user.is_platform_owner = True
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()

    # Link profile to @ismoilo9
    profile = PlayerProfile.objects.filter(user=user).first()
    if not profile:
        profile = PlayerProfile.objects.create(
            user=user,
            telegram_id=999999999,
            telegram_username='ismoilo9',
            first_name='Super',
            last_name='Admin',
            is_platform_owner=True
        )
    else:
        profile.is_platform_owner = True
        profile.telegram_username = 'ismoilo9'
        profile.save()

    # Create wallet with infinite resources
    wallet = EconomyService.get_or_create_wallet(user=user)
    wallet.diamonds = 999999
    wallet.coins = 999999
    wallet.money = 999999.00
    wallet.save()

    print(f"SUCCESS: Superadmin account created!")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print(f"Role: {user.role}")

if __name__ == '__main__':
    create_superadmin()
