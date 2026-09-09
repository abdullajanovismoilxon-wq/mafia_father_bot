from django.core.management.base import BaseCommand
from apps.superadmin.services import SettingService, TextService


class Command(BaseCommand):
    help = "Seeds default game settings and live system texts in database"

    def handle(self, *args, **options):
        SettingService.seed_defaults()
        TextService.seed_defaults()
        TextService.reload_cache()
        count = len(TextService._cache)
        self.stdout.write(self.style.SUCCESS(f"Successfully seeded defaults! Total active system texts: {count}"))
