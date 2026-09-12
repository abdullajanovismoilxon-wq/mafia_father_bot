import os
import json
import logging
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.users.models import User
from apps.economy.models import Wallet, Inventory, MarketplaceItem, MarketplaceCategory, MarketplaceItemType, PlayerHero
from apps.economy.services import HeroService, EconomyService, CasinoService
from apps.stats.models import PlayerStats, PlayerProfile
from apps.games.models import Role, RoleTeam
from apps.superadmin.services import SettingService, TextService

logger = logging.getLogger(__name__)

CIVILIAN_CODES = {
    'citizen', 'doctor', 'detective', 'serjant', 'hamshira',
    'omadli', 'janob', 'sotqin', 'admiral', 'robingud',
    'fotoparatchi', 'daydi', 'kezuvchi'
}
MAFIA_CODES = {
    'don', 'mafia', 'advokat', 'ubiytsa', 'jurnalist', 'aygoqchi', 'laborant'
}
CIVILIAN_ICONS = {
    'citizen': '👨🏼', 'doctor': '👨🏼‍⚕️', 'detective': '🕵🏻‍♂️', 'serjant': '👮🏼‍♂️',
    'hamshira': '👩🏼‍⚕️', 'omadli': '🤞🏼', 'janob': '🎖', 'sotqin': '🤓',
    'admiral': '🧑🏻‍✈️', 'robingud': '🏹', 'fotoparatchi': '📸', 'daydi': '🍾', 'kezuvchi': '💃'
}
MAFIA_ICONS = {
    'don': '🤵🏻', 'mafia': '🤵🏼', 'advokat': '💼', 'ubiytsa': '🥷',
    'jurnalist': '👩🏼‍💻', 'aygoqchi': '🦇', 'laborant': '👩‍⚕️'
}
SOLO_ICONS = {
    'kimyogar': '👨‍🔬', 'rais': '💰', 'bori': '🐺', 'aferist': '🤹🏻',
    'gazabkor': '🧌', 'sehrgar': '🧙', 'qotil': '🔪', 'konchi': '👷🏻‍♂️',
    'qaroqchi': '⚔️', 'qorbobo': '🎅🏻', 'oshpaz': '👨🏼‍🍳', 'afsungar': '🧙🏼',
    'tuzoqchi': '🕸', 'axmoq': '🤪', 'buqalamun': '🦎', 'joker': '🃏',
    'suidsid': '🤡', 'zombi': '🧟'
}
ROLE_HUMAN_NAMES = {
    'citizen': 'Tinch aholi', 'doctor': 'Shifokor', 'detective': 'Komissar',
    'serjant': 'Serjant', 'hamshira': 'Hamshira', 'omadli': 'Omadli',
    'janob': 'Janob', 'sotqin': 'Sotqin', 'admiral': 'Admiral',
    'robingud': 'Robin Gud', 'fotoparatchi': 'Fotoparatchi', 'daydi': 'Daydi',
    'kezuvchi': 'Kezuvchi', 'don': 'Don', 'mafia': 'Mafia',
    'advokat': 'Advokat', 'ubiytsa': 'Ubiytsa', 'jurnalist': 'Jurnalist',
    'aygoqchi': "Ayg'oqchi", 'laborant': 'Laborant', 'kimyogar': 'Kimyogar',
    'rais': 'Rais', 'bori': "Bo'ri", 'aferist': 'Aferist',
    'gazabkor': "G'azabkor", 'sehrgar': 'Sehrgar', 'qotil': 'Qotil',
    'konchi': 'Konchi', 'qaroqchi': 'Qaroqchi', 'qorbobo': 'Qorbobo',
    'oshpaz': 'Oshpaz', 'afsungar': 'Afsungar', 'tuzoqchi': 'Tuzoqchi',
    'axmoq': 'Axmoq', 'buqalamun': 'Buqalamun', 'joker': 'Joker',
    'suidsid': 'Suidsid', 'zombi': 'Zombi'
}


def _get_user_profile_payload(tg_id: int) -> dict:
    """Fetches real user profile, wallet balances, stats, and inventory. Shows ∞ for @ismoilo9."""
    profile = PlayerProfile.objects.filter(telegram_id=tg_id).first()
    wallet = Wallet.objects.filter(telegram_id=tg_id).first()
    stats = getattr(profile, 'stats', None) if profile else None

    display_name = "O'yinchi"
    if profile:
        display_name = profile.full_name or profile.first_name or profile.telegram_username or "O'yinchi"

    is_owner = (
        tg_id == 7782387930 or
        (profile and (
            profile.telegram_username == 'ismoilo9' or
            profile.is_platform_owner or
            (profile.user and profile.user.username == 'Ismoil')
        ))
    )

    if is_owner:
        total_games = 0
        total_wins = 0
        win_rate_num = 0.0
        money_display = "VIP (Cheksiz)"
        money_raw = 999999999
        diamonds_display = "VIP (Cheksiz)"
        diamonds_raw = 999999999
        rank_title = "👑 VIP ASOSCHI"
        rank_badge = "rank-owner"
    else:
        total_games = stats.games_played if stats else 0
        total_wins = stats.games_won if stats else 0
        win_rate_num = round((total_wins / total_games * 100), 1) if total_games > 0 else 0
        money = max(wallet.coins, int(wallet.money)) if wallet else 0
        diamonds = wallet.diamonds if wallet else 0
        money_display = f"{money:,}".replace(",", " ")
        money_raw = money
        diamonds_display = diamonds
        diamonds_raw = diamonds

        min_legend = SettingService.get_int('rank_legend_min_wins', 50)
        min_pro = SettingService.get_int('rank_pro_min_wins', 20)
        min_veteran = SettingService.get_int('rank_veteran_min_wins', 5)

        if total_wins >= min_legend:
            rank_title = "🔥 MAFIYA AFSONASI"
            rank_badge = "rank-legend"
        elif total_wins >= min_pro:
            rank_title = "⚡️ PRO O'YINCHI"
            rank_badge = "rank-pro"
        elif total_wins >= min_veteran:
            rank_title = "🎖 TAJRIBALI JANGCHI"
            rank_badge = "rank-veteran"
        else:
            rank_title = "🌱 YOSH FUQARO"
            rank_badge = "rank-novice"

    inv_state = {
        'himoya': {'count': 0, 'on': True},
        'osish_himoya': {'count': 0, 'on': True},
        'hujjat': {'count': 0, 'on': True},
        'geroy_himoya': {'count': 0, 'on': True},
        'sirpanish_himoya': {'count': 0, 'on': True},
        'vaksina': {'count': 0, 'on': True},
        'dori_himoya': {'count': 0, 'on': True},
        'geroy': {'count': 0, 'on': True},
    }

    if tg_id and not is_owner:
        inv_records = Inventory.objects.filter(telegram_id=tg_id).select_related('item')
        for inv in inv_records:
            code = inv.item.code if inv.item else ''
            if code in inv_state:
                inv_state[code]['count'] = inv.quantity
                inv_state[code]['on'] = inv.is_active

    # Couple / Partner Info
    from apps.stats.services import CoupleService
    partner_info = CoupleService.get_partner_info(tg_id) if tg_id else None
    if partner_info:
        since_date = partner_info['created_at'].strftime('%d.%m.%Y') if partner_info.get('created_at') else ''
        couple_data = {
            'has_partner': True,
            'partner_id': partner_info['partner_id'],
            'partner_name': partner_info['partner_name'],
            'partner_link': f"tg://user?id={partner_info['partner_id']}",
            'since': since_date,
        }
    else:
        couple_data = {
            'has_partner': False,
            'partner_id': 0,
            'partner_name': "Mavjud emas",
            'partner_link': "#",
            'since': '',
        }

    return {
        'tg_id': tg_id,
        'display_name': display_name if display_name != "O'yinchi" else ("Ismoil 👑" if is_owner else "O'yinchi"),
        'money': money_display,
        'money_raw': money_raw,
        'diamonds': diamonds_display,
        'diamonds_raw': diamonds_raw,
        'total_games': total_games,
        'total_wins': total_wins,
        'win_rate': f"{win_rate_num}%",
        'win_rate_num': win_rate_num,
        'rank_title': rank_title,
        'rank_badge': rank_badge,
        'avatar_letter': display_name[0].upper() if display_name else "👤",
        'clan_name': '👑 VIP Asoschi' if is_owner else 'Mavjud emas',
        'inv_state': inv_state,
        'couple': couple_data,
        'is_owner': is_owner,
    }



def _get_all_roles_payload() -> list:
    """Returns all 38 roles formatted for catalog."""
    roles_qs = Role.objects.filter(is_active=True).order_by('priority', 'name')
    roles_list = []
    for r in roles_qs:
        code = r.code.lower()
        if code in CIVILIAN_CODES:
            category = 'town'
            category_label = 'Tinch'
            category_badge = 'badge-town'
            icon = CIVILIAN_ICONS.get(code, '🏛')
        elif code in MAFIA_CODES:
            category = 'mafia'
            category_label = 'Mafia'
            category_badge = 'badge-mafia'
            icon = MAFIA_ICONS.get(code, '🤵🏻')
        else:
            category = 'solo'
            category_label = 'Yakka'
            category_badge = 'badge-solo'
            icon = SOLO_ICONS.get(code, '🃏')

        name_display = ROLE_HUMAN_NAMES.get(code, r.name.capitalize())
        roles_list.append({
            'name': name_display,
            'code': r.code,
            'icon': icon,
            'category': category,
            'category_label': category_label,
            'category_badge': category_badge,
            'description': r.description or "Mafiya o'yini ishtirokchisi.",
        })
    return roles_list


def _get_shop_prices_payload() -> dict:
    """Dynamically returns all shop product prices strictly from SuperAdmin SettingService."""
    return {
        # Items
        'himoya': SettingService.get_int('price_himoya', 300),
        'osish_himoya': SettingService.get_int('price_osish_himoya', 1),
        'hujjat': SettingService.get_int('price_hujjat', 200),
        'vaksina': SettingService.get_int('price_vaksina', 150),
        'dori_himoya': SettingService.get_int('price_dori_himoya', 130),
        'geroy_himoya': SettingService.get_int('price_geroy_himoya', 3),
        'sirpanish_himoya': SettingService.get_int('price_sirpanish_himoya', 150),
        'vip_30': SettingService.get_int('price_vip_30', 30),
        'geroy': SettingService.get_int('price_geroy', 80),
        'hero_rename': SettingService.get_int('price_hero_rename', 5),
        # Town Roles
        'role_citizen': SettingService.get_int('price_role_citizen', 100),
        'role_doctor': SettingService.get_int('price_role_shifokor', SettingService.get_int('price_role_doctor', 600)),
        'role_shifokor': SettingService.get_int('price_role_shifokor', 600),
        'role_detective': SettingService.get_int('price_role_komissar', SettingService.get_int('price_role_detective', 2)),
        'role_komissar': SettingService.get_int('price_role_komissar', 2),
        'role_serjant': SettingService.get_int('price_role_serjant', 300),
        'role_hamshira': SettingService.get_int('price_role_hamshira', 250),
        'role_omadli': SettingService.get_int('price_role_omadli', 350),
        'role_janob': SettingService.get_int('price_role_janob', 3),
        'role_sotqin': SettingService.get_int('price_role_sotqin', 300),
        'role_admiral': SettingService.get_int('price_role_admiral', 4),
        'role_robingud': SettingService.get_int('price_role_robingud', 350),
        'role_fotoparatchi': SettingService.get_int('price_role_fotoparatchi', 250),
        'role_daydi': SettingService.get_int('price_role_daydi', 200),
        'role_kezuvchi': SettingService.get_int('price_role_kezuvchi', 250),
        # Mafia Roles
        'role_don': SettingService.get_int('price_role_don', 2),
        'role_mafia': SettingService.get_int('price_role_mafia', 300),
        'role_advokat': SettingService.get_int('price_role_advokat', 250),
        'role_ubiytsa': SettingService.get_int('price_role_ubiytsa', 300),
        'role_jurnalist': SettingService.get_int('price_role_jurnalist', 350),
        'role_aygoqchi': SettingService.get_int('price_role_aygoqchi', 1),
        'role_laborant': SettingService.get_int('price_role_laborant', 350),
        # Solo Roles
        'role_qotil': SettingService.get_int('price_role_qotil', 3),
        'role_bori': SettingService.get_int('price_role_bori', 300),
        'role_aferist': SettingService.get_int('price_role_aferist', 2),
        'role_gazabkor': SettingService.get_int('price_role_gazabkor', 3),
        'role_sehrgar': SettingService.get_int('price_role_sehrgar', 10),
        'role_kimyogar': SettingService.get_int('price_role_kimyogar', 300),
        'role_rais': SettingService.get_int('price_role_rais', 2),
        'role_konchi': SettingService.get_int('price_role_konchi', 300),
        'role_qaroqchi': SettingService.get_int('price_role_qaroqchi', 300),
        'role_qorbobo': SettingService.get_int('price_role_qorbobo', 4),
        'role_oshpaz': SettingService.get_int('price_role_oshpaz', 350),
        'role_afsungar': SettingService.get_int('price_role_afsungar', 3),
        'role_tuzoqchi': SettingService.get_int('price_role_tuzoqchi', 350),
        'role_axmoq': SettingService.get_int('price_role_axmoq', 250),
        'role_buqalamun': SettingService.get_int('price_role_buqalamun', 2),
        'role_joker': SettingService.get_int('price_role_joker', 4),
        'role_suidsid': SettingService.get_int('price_role_suidsid', 300),
        'role_zombi': SettingService.get_int('price_role_zombi', 2),
    }


def profile_webapp_view(request):
    """Renders unified Telegram WebApp (Profile, Do'kon, Rollar)."""
    tg_id_param = request.GET.get('tg_id', '0')
    try:
        tg_id = int(tg_id_param)
    except ValueError:
        tg_id = 0

    user_data = _get_user_profile_payload(tg_id)
    roles_list = _get_all_roles_payload()

    context = {
        **user_data,
        'roles': roles_list,
        'roles_total_count': len(roles_list),
        'roles_town_count': sum(1 for r in roles_list if r['category'] == 'town'),
        'roles_mafia_count': sum(1 for r in roles_list if r['category'] == 'mafia'),
        'roles_solo_count': sum(1 for r in roles_list if r['category'] == 'solo'),
        'bot_username': 'MafiasFather_bot',
        'active_tab': request.GET.get('tab', 'profile'),
        'prices': _get_shop_prices_payload(),
        'hero': (None if user_data.get('is_owner') else (HeroService.get_hero(tg_id) if tg_id else None)),
    }

    return render(request, 'webapp/profile.html', context)


def roles_webapp_view(request):
    """Direct URL for roles, opens the unified WebApp with roles tab active."""
    request.GET = request.GET.copy()
    request.GET['tab'] = 'roles'
    return profile_webapp_view(request)


def get_profile_api(request):
    """AJAX endpoint to fetch real live profile payload for client-side WebApp."""
    tg_id_param = request.GET.get('tg_id', '0')
    try:
        tg_id = int(tg_id_param)
    except ValueError:
        tg_id = 0

    data = _get_user_profile_payload(tg_id)
    return JsonResponse({'ok': True, 'data': data})


@csrf_exempt
def toggle_inventory_item_api(request):
    """AJAX endpoint to toggle defense switch from WebApp."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        item_code = data.get('item_code')
        is_active = bool(data.get('is_active'))

        if not tg_id or not item_code:
            return JsonResponse({'ok': False, 'error': 'Invalid parameters'}, status=400)

        item = MarketplaceItem.objects.filter(code=item_code).first()
        if not item:
            cat, _ = MarketplaceCategory.objects.get_or_create(code='game_items', defaults={'name': "O'yin buyumlari"})
            item = MarketplaceItem.objects.create(
                code=item_code, category=cat, name=item_code.replace('_', ' ').title(),
                item_type=MarketplaceItemType.BONUS
            )

        inv, _ = Inventory.objects.get_or_create(
            telegram_id=tg_id, item=item,
            defaults={'quantity': 0, 'is_active': is_active}
        )
        inv.is_active = is_active
        inv.save(update_fields=['is_active'])

        return JsonResponse({'ok': True, 'item_code': item_code, 'is_active': is_active})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
def buy_inventory_item_api(request):
    """AJAX endpoint to purchase marketplace item from WebApp Do'kon."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        item_code = data.get('item_code')

        if not tg_id:
            return JsonResponse({'ok': False, 'error': "O'yinchi aniqlanmadi"}, status=400)

        from apps.economy.services import EconomyService
        from apps.superadmin.services import SettingService

        prices = {
            # Items
            'himoya': (SettingService.get_int('price_himoya', 300), 'MONEY'),
            'osish_himoya': (SettingService.get_int('price_osish_himoya', 1), 'DIAMONDS'),
            'hujjat': (SettingService.get_int('price_hujjat', 200), 'MONEY'),
            'vaksina': (SettingService.get_int('price_vaksina', 150), 'MONEY'),
            'dori_himoya': (SettingService.get_int('price_dori_himoya', 130), 'MONEY'),
            'geroy_himoya': (SettingService.get_int('price_geroy_himoya', 3), 'DIAMONDS'),
            'sirpanish_himoya': (SettingService.get_int('price_sirpanish_himoya', 150), 'MONEY'),
            'vip_30': (SettingService.get_int('price_vip_30', 30), 'DIAMONDS'),
            'geroy': (SettingService.get_int('price_geroy', 80), 'DIAMONDS'),
            # Town Roles
            'role_citizen': (SettingService.get_int('price_role_citizen', 100), 'MONEY'),
            'role_doctor': (SettingService.get_int('price_role_doctor', 400), 'MONEY'),
            'role_shifokor': (SettingService.get_int('price_role_doctor', 400), 'MONEY'),
            'role_detective': (SettingService.get_int('price_role_detective', 8), 'DIAMONDS'),
            'role_komissar': (SettingService.get_int('price_role_detective', 8), 'DIAMONDS'),
            'role_serjant': (SettingService.get_int('price_role_serjant', 300), 'MONEY'),
            'role_hamshira': (SettingService.get_int('price_role_hamshira', 250), 'MONEY'),
            'role_omadli': (SettingService.get_int('price_role_omadli', 350), 'MONEY'),
            'role_janob': (SettingService.get_int('price_role_janob', 5), 'DIAMONDS'),
            'role_sotqin': (SettingService.get_int('price_role_sotqin', 300), 'MONEY'),
            'role_admiral': (SettingService.get_int('price_role_admiral', 6), 'DIAMONDS'),
            'role_robingud': (SettingService.get_int('price_role_robingud', 450), 'MONEY'),
            'role_fotoparatchi': (SettingService.get_int('price_role_fotoparatchi', 250), 'MONEY'),
            'role_daydi': (SettingService.get_int('price_role_daydi', 200), 'MONEY'),
            'role_kezuvchi': (SettingService.get_int('price_role_kezuvchi', 300), 'MONEY'),
            # Mafia Roles
            'role_don': (SettingService.get_int('price_role_don', 10), 'DIAMONDS'),
            'role_mafia': (SettingService.get_int('price_role_mafia', 400), 'MONEY'),
            'role_advokat': (SettingService.get_int('price_role_advokat', 350), 'MONEY'),
            'role_ubiytsa': (SettingService.get_int('price_role_ubiytsa', 500), 'MONEY'),
            'role_jurnalist': (SettingService.get_int('price_role_jurnalist', 350), 'MONEY'),
            'role_aygoqchi': (SettingService.get_int('price_role_aygoqchi', 6), 'DIAMONDS'),
            'role_laborant': (SettingService.get_int('price_role_laborant', 400), 'MONEY'),
            # Solo Roles
            'role_qotil': (SettingService.get_int('price_role_qotil', 7), 'DIAMONDS'),
            'role_bori': (SettingService.get_int('price_role_bori', 500), 'MONEY'),
            'role_aferist': (SettingService.get_int('price_role_aferist', 5), 'DIAMONDS'),
            'role_gazabkor': (SettingService.get_int('price_role_gazabkor', 6), 'DIAMONDS'),
            'role_sehrgar': (SettingService.get_int('price_role_sehrgar', 10), 'DIAMONDS'),
            'role_kimyogar': (SettingService.get_int('price_role_kimyogar', 450), 'MONEY'),
            'role_rais': (SettingService.get_int('price_role_rais', 8), 'DIAMONDS'),
            'role_konchi': (SettingService.get_int('price_role_konchi', 300), 'MONEY'),
            'role_qaroqchi': (SettingService.get_int('price_role_qaroqchi', 400), 'MONEY'),
            'role_qorbobo': (SettingService.get_int('price_role_qorbobo', 5), 'DIAMONDS'),
            'role_oshpaz': (SettingService.get_int('price_role_oshpaz', 350), 'MONEY'),
            'role_afsungar': (SettingService.get_int('price_role_afsungar', 5), 'DIAMONDS'),
            'role_tuzoqchi': (SettingService.get_int('price_role_tuzoqchi', 400), 'MONEY'),
            'role_axmoq': (SettingService.get_int('price_role_axmoq', 250), 'MONEY'),
            'role_buqalamun': (SettingService.get_int('price_role_buqalamun', 5), 'DIAMONDS'),
            'role_joker': (SettingService.get_int('price_role_joker', 8), 'DIAMONDS'),
            'role_suidsid': (SettingService.get_int('price_role_suidsid', 300), 'MONEY'),
            'role_zombi': (SettingService.get_int('price_role_zombi', 5), 'DIAMONDS'),
        }

        if item_code not in prices:
            return JsonResponse({'ok': False, 'error': "Mahsulot topilmadi"}, status=404)

        price, currency = prices[item_code]
        wallet = EconomyService.get_or_create_wallet(telegram_id=tg_id)

        user_profile = PlayerProfile.objects.filter(telegram_id=tg_id).first()
        is_owner = user_profile and getattr(user_profile, 'is_platform_owner', False)

        if not is_owner:
            cur_money = max(wallet.coins, int(wallet.money))
            if currency == 'MONEY' and cur_money < price:
                return JsonResponse({'ok': False, 'error': f"Hisobingizda mablag' yetarli emas! (Kerak: {price} 💶)"}, status=400)
            elif currency == 'DIAMONDS' and wallet.diamonds < price:
                return JsonResponse({'ok': False, 'error': f"Hisobingizda olmos yetarli emas! (Kerak: {price} 💎)"}, status=400)

            if currency == 'MONEY':
                wallet.coins = max(0, wallet.coins - price)
                wallet.money = max(Decimal('0.00'), wallet.money - Decimal(str(price)))
                wallet.save(update_fields=['coins', 'money'])
            elif currency == 'DIAMONDS':
                wallet.diamonds -= price
                wallet.save(update_fields=['diamonds'])

        cat, _ = MarketplaceCategory.objects.get_or_create(code='game_items', defaults={'name': "O'yin buyumlari"})
        item, _ = MarketplaceItem.objects.get_or_create(
            code=item_code,
            defaults={'category': cat, 'name': item_code.replace('_', ' ').title(), 'item_type': MarketplaceItemType.BONUS}
        )
        inv, _ = Inventory.objects.get_or_create(telegram_id=tg_id, item=item, defaults={'quantity': 0, 'is_active': True})
        inv.quantity += 1
        inv.is_active = True
        inv.save(update_fields=['quantity', 'is_active'])

        cur_money_after = max(wallet.coins, int(wallet.money))
        return JsonResponse({
            'ok': True,
            'message': f"{item.name} muvaffaqiyatli xarid qilindi!",
            'new_money': f"{cur_money_after:,}".replace(",", " "),
            'new_diamonds': wallet.diamonds,
            'item_code': item_code,
            'new_count': inv.quantity
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
def transfer_funds_api(request):
    """
    AJAX endpoint to transfer dollars or diamonds to another user.
    POST /webapp/api/transfer-funds/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        sender_tg_id = int(data.get('sender_tg_id', 0))
        recipient_input = str(data.get('recipient', '')).strip()
        currency = str(data.get('currency', 'MONEY')).upper()
        amount = int(data.get('amount', 0))

        if not sender_tg_id:
            return JsonResponse({'ok': False, 'error': "Yuboruvchi aniqlanmadi"}, status=400)
        if not recipient_input:
            return JsonResponse({'ok': False, 'error': "Qabul qiluvchini kiriting"}, status=400)
        if amount <= 0:
            return JsonResponse({'ok': False, 'error': "O'tkazma miqdori 0 dan katta bo'lishi kerak"}, status=400)

        # Find recipient by ID or username
        clean_recipient = recipient_input.lstrip('@')
        recipient_profile = None
        if clean_recipient.isdigit():
            rec_id = int(clean_recipient)
            recipient_profile = PlayerProfile.objects.filter(telegram_id=rec_id).first()
        if not recipient_profile:
            recipient_profile = PlayerProfile.objects.filter(telegram_username__iexact=clean_recipient).first()

        if not recipient_profile:
            return JsonResponse({'ok': False, 'error': f"'{recipient_input}' nomli foydalanuvchi topilmadi"}, status=404)

        if recipient_profile.telegram_id == sender_tg_id:
            return JsonResponse({'ok': False, 'error': "O'zingizga mablag' o'tkaza olmaysiz"}, status=400)

        from apps.economy.services import EconomyService
        sender_wallet = EconomyService.get_or_create_wallet(telegram_id=sender_tg_id)
        recipient_wallet = EconomyService.get_or_create_wallet(telegram_id=recipient_profile.telegram_id)

        sender_profile = PlayerProfile.objects.filter(telegram_id=sender_tg_id).first()
        is_owner = sender_profile and sender_profile.is_platform_owner

        commission = 0 if is_owner else int(amount * 0.03)
        net_amount = max(0, amount - commission)

        if currency == 'MONEY':
            cur_money = max(sender_wallet.coins, int(sender_wallet.money))
            if not is_owner and cur_money < amount:
                return JsonResponse({'ok': False, 'error': f"Hisobingizda mablag' yetarli emas! (Mavjud: {cur_money} 💶)"}, status=400)

            if not is_owner:
                sender_wallet.coins = max(0, sender_wallet.coins - amount)
                sender_wallet.money = max(Decimal('0.00'), sender_wallet.money - Decimal(str(amount)))
                sender_wallet.save(update_fields=['coins', 'money'])

            recipient_wallet.coins += net_amount
            recipient_wallet.money += Decimal(str(net_amount))
            recipient_wallet.save(update_fields=['coins', 'money'])

            unit = "💶"
        elif currency == 'DIAMONDS':
            if not is_owner and sender_wallet.diamonds < amount:
                return JsonResponse({'ok': False, 'error': f"Hisobingizda olmos yetarli emas! (Mavjud: {sender_wallet.diamonds} 💎)"}, status=400)

            if not is_owner:
                sender_wallet.diamonds -= amount
                sender_wallet.save(update_fields=['diamonds'])

            recipient_wallet.diamonds += net_amount
            recipient_wallet.save(update_fields=['diamonds'])

            unit = "💎"
        else:
            return JsonResponse({'ok': False, 'error': "Noma'lum valyuta turi"}, status=400)

        rec_name = recipient_profile.full_name or recipient_profile.first_name or clean_recipient
        sender_name = sender_profile.full_name or sender_profile.first_name if sender_profile else "Foydalanuvchi"

        cur_money_after = max(sender_wallet.coins, int(sender_wallet.money))

        # Send Telegram notification to both parties
        try:
            import urllib.request
            token = os.environ.get('MASTER_BOT_TOKEN') or '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
            
            rec_text = (
                f"🎁 <b>Hisobingiz to'ldirildi!</b>\n\n"
                f"Sizga <b>{sender_name}</b> tomonidan <b>{net_amount} {unit}</b> o'tkazildi!\n"
                f"Yangi balansingiz: 💶 {max(recipient_wallet.coins, int(recipient_wallet.money))} | 💎 {recipient_wallet.diamonds}"
            )
            send_text = (
                f"💸 <b>O'tkazma muvaffaqiyatli amalga oshirildi!</b>\n\n"
                f"Siz <b>{rec_name}</b> ga <b>{amount} {unit}</b> yubordingiz.\n"
                f"Qolgan balansingiz: 💶 {cur_money_after} | 💎 {sender_wallet.diamonds}"
            )
            
            def _send_tg(chat_id, text):
                try:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = json.dumps({
                        'chat_id': chat_id,
                        'text': text,
                        'parse_mode': 'HTML'
                    }).encode('utf-8')
                    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=4)
                except Exception:
                    pass

            import threading
            threading.Thread(target=_send_tg, args=(recipient_profile.telegram_id, rec_text)).start()
            threading.Thread(target=_send_tg, args=(sender_tg_id, send_text)).start()
        except Exception:
            pass

        return JsonResponse({
            'ok': True,
            'message': f"{amount} {unit} foydalanuvchi {rec_name} ga muvaffaqiyatli o'tkazildi!",
            'new_money': f"{cur_money_after:,}".replace(",", " "),
            'new_diamonds': sender_wallet.diamonds,
        })
    except Exception as e:
        logger.exception("Error in transfer_funds_api:")
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)



def get_notifications_api(request):
    """AJAX endpoint to fetch user's notifications for in-app notification center."""
    tg_id_param = request.GET.get('tg_id', '0')
    try:
        tg_id = int(tg_id_param)
    except ValueError:
        tg_id = 0

    from apps.superadmin.models import UserNotification
    from django.db.models import Q

    notifs_qs = UserNotification.objects.filter(
        Q(telegram_id=tg_id) | Q(telegram_id__isnull=True)
    ).order_by('-created_at')[:20]

    notifs_list = []
    for n in notifs_qs:
        notifs_list.append({
            'id': str(n.id),
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'date': n.created_at.strftime('%Y-%m-%d %H:%M'),
        })

def get_user_groups_api(request):
    """
    AJAX endpoint to list groups owned by the user or search all active groups.
    GET /webapp/api/groups/list/?tg_id=...&query=...
    """
    tg_id_param = request.GET.get('tg_id', '0')
    query = request.GET.get('query', '').strip()
    try:
        tg_id = int(tg_id_param)
    except ValueError:
        tg_id = 0

    import secrets
    from apps.bots.models import BotGroup
    from apps.stats.models import PlayerProfile
    from django.db.models import Q

    profile = PlayerProfile.objects.filter(telegram_id=tg_id).first()
    is_owner = (tg_id == 7782387930) or (profile and profile.is_platform_owner)

    if is_owner or not tg_id:
        qs = BotGroup.objects.all()
    else:
        qs = BotGroup.objects.filter(Q(owner_telegram_id=tg_id) | Q(chat_id=tg_id))
        if not qs.exists():
            qs = BotGroup.objects.all()

    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(username__icontains=query) | Q(cabinet_login__icontains=query))

    groups_data = []
    seen_chat_ids = set()
    for g in qs.order_by('-last_active_at')[:50]:
        if g.chat_id in seen_chat_ids:
            continue
        seen_chat_ids.add(g.chat_id)

        need_save = False
        if not g.cabinet_login:
            g.cabinet_login = f"guruh_{abs(g.chat_id)}"
            need_save = True
        if not g.cabinet_password:
            g.cabinet_password = f"mafia{secrets.randbelow(900000) + 100000}"
            need_save = True
        if need_save:
            g.save(update_fields=['cabinet_login', 'cabinet_password'])

        is_group_owner = (is_owner or (tg_id and g.owner_telegram_id == tg_id))
        groups_data.append({
            'id': str(g.id),
            'title': g.title,
            'chat_id': g.chat_id,
            'username': g.username,
            'owner_name': g.owner_name or 'Guruh Egasi',
            'bot_name': g.bot.name if g.bot else '',
            'cabinet_login': g.cabinet_login,
            'cabinet_password': g.cabinet_password,
            'total_games': g.total_games_played,
            'is_owner': is_group_owner,
        })

    return JsonResponse({'ok': True, 'groups': groups_data})


@csrf_exempt
@require_POST
def group_cabinet_login_api(request):
    """Authenticates a group owner or admin using cabinet_login and cabinet_password, or direct 1-click tg_id for owner."""
    try:
        data = json.loads(request.body.decode('utf-8'))
        login = str(data.get('login', '')).strip()
        password = str(data.get('password', '')).strip()
        group_id = str(data.get('group_id', '')).strip()
        tg_id_param = data.get('tg_id')
        try:
            tg_id = int(tg_id_param) if tg_id_param else 0
        except ValueError:
            tg_id = 0

        from apps.bots.models import BotGroup
        from apps.stats.models import PlayerProfile

        group = None

        # 1. 1-Click Direct Owner / Platform Owner Authentication
        if group_id and tg_id:
            g_candidate = BotGroup.objects.select_related('bot').filter(id=group_id).first()
            if g_candidate:
                profile = PlayerProfile.objects.filter(telegram_id=tg_id).first()
                is_platform_admin = (tg_id == 7782387930) or (profile and profile.is_platform_owner)
                if is_platform_admin or (g_candidate.owner_telegram_id == tg_id):
                    group = g_candidate

        # 2. Login & Password Authentication
        if not group:
            if not login or not password:
                return JsonResponse({'ok': False, 'error': "Login va parol kiritilmadi."}, status=400)
            group = BotGroup.objects.select_related('bot').filter(cabinet_login__iexact=login, cabinet_password=password).first()

        if not group:
            return JsonResponse({'ok': False, 'error': "Login yoki parol noto'g'ri!"}, status=401)

        # Default settings if empty
        settings = group.group_settings or {}
        bot_cfg = getattr(group.bot, 'configuration', None)
        extra = bot_cfg.extra_settings if bot_cfg and bot_cfg.extra_settings else {}

        defaults = {
            'night_duration': settings.get('night_duration', bot_cfg.night_duration_seconds if bot_cfg else 60),
            'voting_duration': settings.get('voting_duration', bot_cfg.voting_duration_seconds if bot_cfg else 20),
            'dawn_wait_duration': settings.get('dawn_wait_duration', extra.get('dawn_wait_duration', 15)),
            'last_words_duration': settings.get('last_words_duration', extra.get('last_words_duration', 50)),
            'lobby_timeout_minutes': settings.get('lobby_timeout_minutes', extra.get('lobby_timeout_minutes', 15)),
            'night_silence_mode': settings.get('night_silence_mode', extra.get('night_silence_mode', 'DELETE_ALL')),
            'cmd_perm_game': settings.get('cmd_perm_game', extra.get('cmd_perm_game', 'ALL')),
            'cmd_perm_start_game': settings.get('cmd_perm_start_game', extra.get('cmd_perm_start_game', 'ADMINS')),
            'cmd_perm_stop_game': settings.get('cmd_perm_stop_game', extra.get('cmd_perm_stop_game', 'ADMINS')),
            'cmd_perm_utag': settings.get('cmd_perm_utag', extra.get('cmd_perm_utag', 'ADMINS')),
            'cmd_perm_stop_tag': settings.get('cmd_perm_stop_tag', extra.get('cmd_perm_stop_tag', 'ADMINS')),
            'cmd_perm_rules': settings.get('cmd_perm_rules', extra.get('cmd_perm_rules', 'ALL')),
            'disabled_roles': settings.get('disabled_roles', []),
        }

        return JsonResponse({
            'ok': True,
            'group': {
                'id': str(group.id),
                'chat_id': group.chat_id,
                'title': group.title,
                'username': group.username,
                'owner_name': group.owner_name or 'Guruh Egasi',
                'bot_name': group.bot.name if group.bot else 'Mafia Bot',
                'bot_username': group.bot.telegram_username if group.bot else '',
                'cabinet_login': group.cabinet_login,
                'cabinet_password': group.cabinet_password,
                'settings': defaults
            }
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def group_cabinet_dashboard_api(request):
    """Returns dashboard statistics, timeline chart data, and top most active players for a specific group."""
    group_id = request.GET.get('group_id')
    timeframe = request.GET.get('timeframe', 'today')  # 'today', 'month', 'year'

    if not group_id:
        return JsonResponse({'ok': False, 'error': "Guruh ID kiritilmadi."}, status=400)

    import datetime
    import calendar
    from apps.bots.models import BotGroup
    from apps.games.models import Game, Player
    from django.db.models import Count, Q

    group = BotGroup.objects.filter(id=group_id).first()
    if not group:
        return JsonResponse({'ok': False, 'error': "Guruh topilmadi."}, status=404)

    now = timezone.now()
    qs_games = Game.objects.filter(bot=group.bot, chat_id=group.chat_id)
    qs_players = Player.objects.filter(game__bot=group.bot, game__chat_id=group.chat_id)

    if timeframe == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs_games = qs_games.filter(created_at__gte=start_date)
        qs_players = qs_players.filter(created_at__gte=start_date)
    elif timeframe == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        qs_games = qs_games.filter(created_at__gte=start_date)
        qs_players = qs_players.filter(created_at__gte=start_date)
    elif timeframe == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        qs_games = qs_games.filter(created_at__gte=start_date)
        qs_players = qs_players.filter(created_at__gte=start_date)

    total_games = qs_games.count()
    completed_games = qs_games.filter(phase='FINISHED').count()
    unique_players_count = qs_players.values('telegram_user_id').distinct().count()

    # Timeline buckets for Chart
    chart_labels = []
    chart_data = []

    if timeframe == 'today':
        intervals = [
            ("00:00-04:00", 0, 4),
            ("04:00-08:00", 4, 8),
            ("08:00-12:00", 8, 12),
            ("12:00-16:00", 12, 16),
            ("16:00-20:00", 16, 20),
            ("20:00-00:00", 20, 24),
        ]
        base_day = now.date()
        for label, h_start, h_end in intervals:
            chart_labels.append(label)
            t_start = timezone.make_aware(datetime.datetime.combine(base_day, datetime.time(h_start, 0, 0)))
            if h_end == 24:
                t_end = timezone.make_aware(datetime.datetime.combine(base_day + datetime.timedelta(days=1), datetime.time(0, 0, 0)))
            else:
                t_end = timezone.make_aware(datetime.datetime.combine(base_day, datetime.time(h_end, 0, 0)))
            cnt = qs_games.filter(created_at__gte=t_start, created_at__lt=t_end).count()
            chart_data.append(cnt)

    elif timeframe == 'month':
        year = now.year
        month = now.month
        last_day = calendar.monthrange(year, month)[1]
        intervals = [
            ("1-5", 1, 5),
            ("6-10", 6, 10),
            ("11-15", 11, 15),
            ("16-20", 16, 20),
            ("21-25", 21, 25),
            (f"26-{last_day}", 26, last_day),
        ]
        for label, d_start, d_end in intervals:
            chart_labels.append(f"{label}-kun")
            t_start = timezone.make_aware(datetime.datetime(year, month, d_start, 0, 0, 0))
            if d_end == last_day:
                if month == 12:
                    t_end = timezone.make_aware(datetime.datetime(year + 1, 1, 1, 0, 0, 0))
                else:
                    t_end = timezone.make_aware(datetime.datetime(year, month + 1, 1, 0, 0, 0))
            else:
                t_end = timezone.make_aware(datetime.datetime(year, month, d_end + 1, 0, 0, 0))
            cnt = qs_games.filter(created_at__gte=t_start, created_at__lt=t_end).count()
            chart_data.append(cnt)

    elif timeframe == 'year':
        month_names = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
        year = now.year
        for m_idx in range(1, 13):
            chart_labels.append(month_names[m_idx - 1])
            t_start = timezone.make_aware(datetime.datetime(year, m_idx, 1, 0, 0, 0))
            if m_idx == 12:
                t_end = timezone.make_aware(datetime.datetime(year + 1, 1, 1, 0, 0, 0))
            else:
                t_end = timezone.make_aware(datetime.datetime(year, m_idx + 1, 1, 0, 0, 0))
            cnt = qs_games.filter(created_at__gte=t_start, created_at__lt=t_end).count()
            chart_data.append(cnt)
    else:
        chart_labels = ["Jami"]
        chart_data = [total_games]

    # Top most active players (ranked by games played and games survived)
    top_players_qs = qs_players.values('telegram_user_id', 'display_name', 'username').annotate(
        games_played=Count('id'),
        games_survived=Count('id', filter=Q(is_alive=True))
    ).order_by('-games_played', '-games_survived')[:10]

    top_players = []
    total_wins_sum = 0
    total_played_sum = 0
    for rank, p in enumerate(top_players_qs, start=1):
        g_played = p['games_played']
        g_survived = p['games_survived']
        win_rate = round((g_survived / g_played * 100), 1) if g_played > 0 else 0
        total_played_sum += g_played
        total_wins_sum += g_survived
        d_name = (p['display_name'] or "O'yinchi").strip()
        avatar_letter = d_name[0].upper() if d_name else "👤"
        top_players.append({
            'rank': rank,
            'name': d_name,
            'username': f"@{p['username']}" if p['username'] else "",
            'avatar_letter': avatar_letter,
            'games_played': g_played,
            'games_won': g_survived,
            'win_rate': f"{win_rate}%",
            'win_rate_num': win_rate
        })

    avg_win_rate = round((total_wins_sum / total_played_sum * 100), 1) if total_played_sum > 0 else 0

    # Current group settings
    group_settings = group.group_settings or {}
    defaults = {
        'night_duration': group_settings.get('night_duration', 60),
        'voting_duration': group_settings.get('voting_duration', 20),
        'dawn_wait_duration': group_settings.get('dawn_wait_duration', 15),
        'last_words_duration': group_settings.get('last_words_duration', 50),
        'lobby_timeout_minutes': group_settings.get('lobby_timeout_minutes', 15),
        'cmd_perm_game': group_settings.get('cmd_perm_game', 'ALL'),
        'cmd_perm_start_game': group_settings.get('cmd_perm_start_game', 'ADMINS'),
        'cmd_perm_stop_game': group_settings.get('cmd_perm_stop_game', 'ADMINS'),
        'cmd_perm_utag': group_settings.get('cmd_perm_utag', 'ADMINS'),
        'cmd_perm_stop_tag': group_settings.get('cmd_perm_stop_tag', 'ADMINS'),
        'cmd_perm_rules': group_settings.get('cmd_perm_rules', 'ALL'),
    }

    return JsonResponse({
        'ok': True,
        'stats': {
            'timeframe': timeframe,
            'total_games': total_games,
            'completed_games': completed_games,
            'total_unique_players': unique_players_count,
            'win_rate_avg': f"{avg_win_rate}%",
            'chart': {
                'labels': chart_labels,
                'data': chart_data
            },
            'top_players': top_players
        },
        'settings': defaults
    })


@csrf_exempt
@require_POST
def group_cabinet_save_settings_api(request):
    """Saves custom per-group settings from the Mini App Guruhim portal."""
    try:
        data = json.loads(request.body.decode('utf-8'))
        group_id = data.get('group_id')
        settings = data.get('settings', {})

        if not group_id:
            return JsonResponse({'ok': False, 'error': "Guruh ID kiritilmadi."}, status=400)

        from apps.bots.models import BotGroup
        group = BotGroup.objects.filter(id=group_id).first()
        if not group:
            return JsonResponse({'ok': False, 'error': "Guruh topilmadi."}, status=404)

        current_settings = group.group_settings or {}
        current_settings.update({
            'night_duration': int(settings.get('night_duration', 60)),
            'voting_duration': int(settings.get('voting_duration', 20)),
            'dawn_wait_duration': int(settings.get('dawn_wait_duration', 15)),
            'last_words_duration': int(settings.get('last_words_duration', 50)),
            'lobby_timeout_minutes': int(settings.get('lobby_timeout_minutes', 15)),
            'night_silence_mode': settings.get('night_silence_mode', 'DELETE_ALL'),
            'cmd_perm_game': settings.get('cmd_perm_game', 'ALL'),
            'cmd_perm_start_game': settings.get('cmd_perm_start_game', 'ADMINS'),
            'cmd_perm_stop_game': settings.get('cmd_perm_stop_game', 'ADMINS'),
            'cmd_perm_utag': settings.get('cmd_perm_utag', 'ADMINS'),
            'cmd_perm_stop_tag': settings.get('cmd_perm_stop_tag', 'ADMINS'),
            'cmd_perm_rules': settings.get('cmd_perm_rules', 'ALL'),
            'disabled_roles': settings.get('disabled_roles', []),
        })

        group.group_settings = current_settings
        group.save(update_fields=['group_settings'])

        return JsonResponse({'ok': True, 'message': "Guruh sozlamalari saqlandi!"})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Hero (Geroy) WebApp APIs
# ---------------------------------------------------------------------------
def hero_info_api(request):
    """GET /webapp/api/hero/info/?tg_id=..."""
    tg_id_param = request.GET.get('tg_id', '0')
    try:
        tg_id = int(tg_id_param)
    except ValueError:
        tg_id = 0

    profile = PlayerProfile.objects.filter(telegram_id=tg_id).first()
    is_owner = (
        tg_id == 7782387930 or
        (profile and (
            profile.telegram_username == 'ismoilo9' or
            profile.is_platform_owner or
            (profile.user and profile.user.username == 'Ismoil')
        ))
    )
    if is_owner:
        return JsonResponse({'ok': True, 'has_hero': False})

    hero = HeroService.get_hero(tg_id)

    if not hero:
        return JsonResponse({'ok': True, 'has_hero': False})


    inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
    def_count = inv.quantity if inv else 0

    return JsonResponse({
        'ok': True,
        'has_hero': True,
        'hero': {
            'name': hero.name,
            'owner_name': hero.owner_name,
            'level': hero.level,
            'power_min': hero.power_min,
            'power_max': hero.power_max,
            'min_damage_percent': hero.power_min,
            'max_damage_percent': hero.power_max,
            'current_defense': hero.current_defense,
            'max_defense': hero.max_defense,
            'charges': hero.charges,
            'score': hero.score,
            'geroy_himoya_count': def_count,
            'next_level': hero.level + 1,
            'next_level_score': hero.next_level_score,
            'recharge_cost': hero.recharge_cost_diamonds,
            'rename_cost': SettingService.get_int('price_hero_rename', 5),
            'is_active': hero.is_active
        }
    })


@csrf_exempt
@require_POST
def hero_recharge_api(request):
    """POST /webapp/api/hero/recharge/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        success, msg, charges = HeroService.recharge_hero(tg_id)
        if not success:
            return JsonResponse({'ok': False, 'error': msg}, status=400)
        
        wallet = EconomyService.get_or_create_wallet(telegram_id=tg_id)
        return JsonResponse({
            'ok': True,
            'message': msg,
            'charges': charges,
            'diamonds': wallet.diamonds
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def hero_rename_api(request):
    """POST /webapp/api/hero/rename/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        new_name = str(data.get('name', '')).strip()
        success, msg = HeroService.rename_hero(tg_id, new_name)
        if not success:
            return JsonResponse({'ok': False, 'error': msg}, status=400)
        
        wallet = EconomyService.get_or_create_wallet(telegram_id=tg_id)
        return JsonResponse({
            'ok': True,
            'message': msg,
            'name': new_name,
            'new_diamonds': wallet.diamonds
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def hero_transfer_api(request):
    """POST /webapp/api/hero/transfer/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        sender_tg_id = int(data.get('sender_tg_id', 0))
        target_input = str(data.get('recipient', '')).strip().lstrip('@')

        target_profile = None
        if target_input.isdigit():
            target_profile = PlayerProfile.objects.filter(telegram_id=int(target_input)).first()
        if not target_profile:
            target_profile = PlayerProfile.objects.filter(telegram_username__iexact=target_input).first()

        if not target_profile:
            return JsonResponse({'ok': False, 'error': f"'{target_input}' topilmadi!"}, status=404)

        rec_name = target_profile.full_name or target_profile.first_name or target_input
        success, msg = HeroService.transfer_hero(sender_tg_id, target_profile.telegram_id, rec_name)
        if not success:
            return JsonResponse({'ok': False, 'error': msg}, status=400)

        # Notify recipient on telegram
        try:
            import urllib.request
            token = os.environ.get('MASTER_BOT_TOKEN') or '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = json.dumps({
                'chat_id': target_profile.telegram_id,
                'text': f"🎁 Sizga yangi <b>Geroy</b> o'tkazildi! (/myhero orqali ko'ring)",
                'parse_mode': 'HTML'
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

        return JsonResponse({'ok': True, 'message': msg})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def hero_create_api(request):
    """POST /webapp/api/hero/create/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        name = str(data.get('name', 'Mening Geroyim')).strip()
        
        profile = PlayerProfile.objects.filter(telegram_id=tg_id).first()
        owner_name = profile.full_name or profile.first_name if profile else "O'yinchi"

        success, msg, hero = HeroService.create_hero(tg_id, name, owner_name, price_diamonds=80)
        if not success:
            return JsonResponse({'ok': False, 'error': msg}, status=400)

        wallet = EconomyService.get_or_create_wallet(telegram_id=tg_id)
        return JsonResponse({
            'ok': True,
            'message': msg,
            'diamonds': wallet.diamonds,
            'hero': {
                'name': hero.name,
                'level': hero.level,
                'charges': hero.charges
            }
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def hero_toggle_api(request):
    """POST /webapp/api/hero/toggle/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        success, is_active = HeroService.toggle_hero(tg_id)
        if not success:
            return JsonResponse({'ok': False, 'error': "Geroy topilmadi"}, status=400)
        return JsonResponse({'ok': True, 'is_active': is_active})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# ---------------------------------------------------------------------------
# 🎰 Kazino (Casino) WebApp APIs
# ---------------------------------------------------------------------------
@csrf_exempt
@require_POST
def casino_roulette_spin_api(request):
    """POST /webapp/api/casino/roulette/spin/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        bet_amount = int(data.get('bet_amount', 100))
        bet_color = str(data.get('bet_color', 'red')).lower().strip()

        result = CasinoService.play_roulette(tg_id, bet_amount, bet_color)
        status_code = 200 if result.get('ok') else 400
        return JsonResponse(result, status=status_code)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def casino_chest_open_api(request):
    """POST /webapp/api/casino/chest/open/"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        tg_id = int(data.get('tg_id', 0))
        chest_type = int(data.get('chest_type', 1))

        result = CasinoService.open_chest(tg_id, chest_type)
        status_code = 200 if result.get('ok') else 400
        return JsonResponse(result, status=status_code)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


def casino_state_api(request):
    """GET /webapp/api/casino/state/?tg_id=..."""
    tg_id_param = request.GET.get('tg_id', '0')
    try:
        tg_id = int(tg_id_param)
    except ValueError:
        tg_id = 0

    result = CasinoService.get_casino_state(tg_id)
    return JsonResponse(result)
