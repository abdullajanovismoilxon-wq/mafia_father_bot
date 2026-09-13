import os
import sys
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.bots.models import Bot

print("--- CHECKING BOTS IN DATABASE ---")
for b in Bot.objects.all():
    token = None
    if hasattr(b, 'credential'):
        token = b.credential.get_token()
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.urlopen(url, timeout=5)
        res = json.loads(req.read().decode())
        actual_username = res.get('result', {}).get('username')
        print(f"[VALID] DB Username: @{b.telegram_username} | Telegram Username: @{actual_username} | Status: {b.status} | ID: {b.id} | Token: {token}")
    except Exception as e:
        print(f"[INVALID/UNAUTHORIZED] DB Username: @{b.telegram_username} | Status: {b.status} | ID: {b.id} | Token: {token} | Error: {e}")
