import os
import json
import logging
import threading
from asgiref.sync import async_to_sync
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User
from apps.bots.models import Bot as BotModel, BotStatus, RuntimeStatus, BotConfiguration
from apps.games.models import Game, Role, Player, GamePhase
from apps.stats.models import PlayerProfile, PlayerStats
from apps.economy.models import Wallet, Inventory, MarketplaceItem, WalletTransaction, VIPSubscription
from apps.superadmin.models import BotSystemText, GameSetting, PromoCode, BroadcastMessage, AuditLog
from apps.superadmin.services import SettingService, TextService, PlayerInventoryService, PromoCodeService, BroadcastService
from bot_runtime.manager import BotRuntimeManager

logger = logging.getLogger(__name__)


def get_excluded_owner_tg_ids() -> list[int]:
    """Returns list of telegram_ids belonging to platform owner / founder / test dummy accounts."""
    owner_ids = {7782387930, 999999999}
    try:
        profiles = PlayerProfile.objects.filter(
            Q(is_platform_owner=True) |
            Q(telegram_username__iexact='ismoilo9') |
            Q(user__is_platform_owner=True) |
            Q(user__username__iexact='Ismoil') |
            Q(user__username__iexact='ismoilo9')
        ).values_list('telegram_id', flat=True)
        for pid in profiles:
            if pid:
                owner_ids.add(pid)
    except Exception:
        pass
    return list(owner_ids)


def is_superadmin(user):
    return user.is_authenticated and (user.is_superuser or user.is_platform_owner or user.is_staff or getattr(user, 'role', '') == 'SUPERADMIN')


def login_view(request):
    if request.user.is_authenticated and is_superadmin(request.user):
        return redirect('superadmin:dashboard')

    if request.method == 'POST':
        login_input = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        found_user = User.objects.filter(username__iexact=login_input).first() or User.objects.filter(email__iexact=login_input).first()
        user = None
        if found_user:
            user = authenticate(request, email=found_user.email, password=password)

        if user and is_superadmin(user):
            login(request, user)
            AuditLog.log(action="ADMIN_KIRISHI", actor=user.username or user.email, target="SuperAdmin Panel", ip=request.META.get('REMOTE_ADDR', ''))
            messages.success(request, f"Xush kelibsiz, {user.first_name or user.username}!")
            return redirect('superadmin:dashboard')
        else:
            messages.error(request, "Login yoki parol noto'g'ri kiritildi.")

    return render(request, 'superadmin/login.html')


@login_required
def logout_view(request):
    AuditLog.log(action="ADMIN_CHIQISHI", actor=request.user.username or request.user.email, target="SuperAdmin Panel", ip=request.META.get('REMOTE_ADDR', ''))
    logout(request)
    return redirect('superadmin:login')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def dashboard_view(request):
    SettingService.seed_defaults()
    TextService.seed_defaults()

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    excluded_owner_ids = get_excluded_owner_tg_ids()

    total_bots = BotModel.objects.count()
    active_bots = BotModel.objects.filter(status=BotStatus.ACTIVE).count()
    total_players = PlayerProfile.objects.exclude(telegram_id__in=excluded_owner_ids).count()
    new_players_today = PlayerProfile.objects.exclude(telegram_id__in=excluded_owner_ids).filter(created_at__gte=today_start).count()
    
    total_games = Game.objects.count()
    live_games_count = Game.objects.exclude(phase__in=['FINISHED', 'CANCELED']).count()
    games_today = Game.objects.filter(created_at__gte=today_start).count()

    wallet_aggregates = Wallet.objects.exclude(telegram_id__in=excluded_owner_ids).aggregate(
        total_coins=Sum('coins'),
        total_diamonds=Sum('diamonds')
    )
    total_coins = wallet_aggregates['total_coins'] or 0
    total_diamonds = wallet_aggregates['total_diamonds'] or 0

    from apps.economy.models import PlayerHero
    total_heroes = PlayerHero.objects.exclude(telegram_id__in=excluded_owner_ids).count()
    active_heroes = PlayerHero.objects.exclude(telegram_id__in=excluded_owner_ids).filter(is_active=True).count()

    vip_count = VIPSubscription.objects.filter(is_active=True).exclude(telegram_id__in=excluded_owner_ids).count()
    tx_count = WalletTransaction.objects.exclude(wallet__telegram_id__in=excluded_owner_ids).count()

    # 7-day Analytics for Charts
    days_labels = []
    games_data = []
    users_data = []

    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        day_start = timezone.make_aware(timezone.datetime.combine(day_date, timezone.datetime.min.time()))
        day_end = timezone.make_aware(timezone.datetime.combine(day_date, timezone.datetime.max.time()))
        
        days_labels.append(day_date.strftime('%d-%b'))
        g_count = Game.objects.filter(created_at__range=(day_start, day_end)).count()
        u_count = PlayerProfile.objects.exclude(telegram_id__in=excluded_owner_ids).filter(created_at__range=(day_start, day_end)).count()
        games_data.append(g_count)
        users_data.append(u_count)

    # Role distribution data (Town, Mafia, Solo, Zombie)
    civilian_roles = ['CITIZEN', 'DOCTOR', 'DETECTIVE', 'SERJANT', 'HAMSHIRA', 'OMADLI', 'JANOB', 'SOTQIN', 'ADMIRAL', 'ROBINGUD', 'FOTOPARATCHI', 'DAYDI', 'KEZUVCHI']
    mafia_roles = ['DON', 'MAFIA', 'ADVOKAT', 'UBIYTSA', 'JURNALIST', 'AYGOQCHI', 'LABORANT']
    solo_roles = ['QOTIL', 'BORI', 'AFERIST', 'GAZABKOR', 'SEHRGAR', 'KIMYOGAR', 'RAIS', 'KONCHI', 'QAROQCHI', 'QORBOBO', 'OSHPAZ', 'AFSUNGAR', 'TUZOQCHI', 'AXMOQ', 'BUQALAMUN', 'JOKER', 'SUIDSID']
    
    town_players = Player.objects.filter(role__name__in=civilian_roles).count()
    maf_players = Player.objects.filter(role__name__in=mafia_roles).count()
    solo_players = Player.objects.filter(role__name__in=solo_roles).count()
    zombie_players = Player.objects.filter(role__name='ZOMBI').count()

    recent_bots = BotModel.objects.select_related('owner', 'configuration').order_by('-created_at')[:8]
    top_players = PlayerProfile.objects.exclude(telegram_id__in=excluded_owner_ids).select_related('stats').order_by('-stats__games_won', '-stats__games_played')[:5]

    from apps.bots.models import BotGroup
    total_groups = BotGroup.objects.count()

    context = {
        'total_bots': total_bots,
        'active_bots': active_bots,
        'total_players': total_players,
        'new_players_today': new_players_today,
        'total_games': total_games,
        'games_today': games_today,
        'live_games_count': live_games_count,
        'total_groups': total_groups,
        'total_coins': total_coins,
        'total_diamonds': total_diamonds,
        'total_heroes': total_heroes,
        'active_heroes': active_heroes,
        'vip_count': vip_count,
        'tx_count': tx_count,
        'recent_bots': recent_bots,
        'top_players': top_players,
        'chart_days_json': json.dumps(days_labels),
        'chart_games_json': json.dumps(games_data),
        'chart_users_json': json.dumps(users_data),
        'chart_roles_json': json.dumps([town_players or 35, maf_players or 20, solo_players or 15, zombie_players or 5]),
        'active_tab': 'dashboard',
    }
    return render(request, 'superadmin/dashboard.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
def bots_view(request):
    query = request.GET.get('q', '').strip()
    bots_qs = BotModel.objects.select_related('owner', 'configuration').annotate(
        games_count=Count('games')
    ).order_by('-created_at')

    if query:
        bots_qs = bots_qs.filter(Q(name__icontains=query) | Q(telegram_username__icontains=query))

    bot_list = []
    for b in bots_qs:
        owner_profile = None
        if b.owner and b.owner.telegram_id:
            owner_profile = PlayerProfile.objects.filter(telegram_id=b.owner.telegram_id).first()

        players_count = Player.objects.filter(game__bot=b).values('telegram_user_id').distinct().count()
        cfg = getattr(b, 'configuration', None)
        extra = cfg.extra_settings if cfg and cfg.extra_settings else {}

        bot_list.append({
            'bot': b,
            'owner_profile': owner_profile,
            'players_count': players_count,
            'games_count': b.games_count,
            'is_running': b.runtime_status == RuntimeStatus.RUNNING and b.status == BotStatus.ACTIVE,
            'night_duration': cfg.night_duration_seconds if cfg and cfg.night_duration_seconds else SettingService.get_int('night_duration', 60),
            'voting_duration': cfg.voting_duration_seconds if cfg and cfg.voting_duration_seconds else SettingService.get_int('voting_duration', 20),
            'dawn_wait': extra.get('dawn_wait_duration', SettingService.get_int('dawn_wait_duration', 15)),
            'last_words': extra.get('last_words_duration', SettingService.get_int('last_words_duration', 50)),
            'lobby_timeout': extra.get('lobby_timeout_minutes', SettingService.get_int('lobby_timeout_minutes', 15)),
            'night_silence_mode': extra.get('night_silence_mode', 'DELETE_ALL'),
            'auto_pin_lobby': extra.get('auto_pin_lobby', True),
            'require_admin': extra.get('require_admin_to_play', True),
            'cmd_perm_start_game': extra.get('cmd_perm_start_game', 'ADMINS'),
            'cmd_perm_stop_game': extra.get('cmd_perm_stop_game', 'ADMINS'),
            'cmd_perm_game': extra.get('cmd_perm_game', 'ALL'),
        })

    context = {
        'bot_list': bot_list,
        'query': query,
        'active_tab': 'bots',
    }
    return render(request, 'superadmin/bots.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def bot_config_save_view(request, bot_id):
    """Saves full configuration for a specific bot."""
    bot_obj = get_object_or_404(BotModel, id=bot_id)
    name = request.POST.get('name', '').strip()
    if name:
        bot_obj.name = name
        bot_obj.save(update_fields=['name'])

    night_duration = int(request.POST.get('night_duration', 60))
    voting_duration = int(request.POST.get('voting_duration', 20))
    dawn_wait = int(request.POST.get('dawn_wait_duration', 15))
    last_words = int(request.POST.get('last_words_duration', 50))
    lobby_timeout = int(request.POST.get('lobby_timeout_minutes', 15))
    night_silence_mode = request.POST.get('night_silence_mode', 'DELETE_ALL')
    auto_pin_lobby = request.POST.get('auto_pin_lobby') == 'on'
    require_admin = request.POST.get('require_admin_to_play') == 'on'

    cmd_perm_start_game = request.POST.get('cmd_perm_start_game', 'ADMINS')
    cmd_perm_stop_game = request.POST.get('cmd_perm_stop_game', 'ADMINS')
    cmd_perm_game = request.POST.get('cmd_perm_game', 'ALL')

    SettingService.set_bot_timing(
        bot_id=str(bot_obj.id),
        night_duration=night_duration,
        voting_duration=voting_duration,
        dawn_wait=dawn_wait,
        last_words=last_words,
        lobby_timeout=lobby_timeout,
        night_silence_mode=night_silence_mode,
        auto_pin_lobby=auto_pin_lobby,
        require_admin=require_admin,
        cmd_perm_start_game=cmd_perm_start_game,
        cmd_perm_stop_game=cmd_perm_stop_game,
        cmd_perm_game=cmd_perm_game
    )

    AuditLog.log(action="BOT_SOZLAMASI_YANGILANDI", actor=request.user.username, target=f"@{bot_obj.telegram_username}", details=f"Vaqtlar va sukut rejimi saqlandi ({night_silence_mode})", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"✅ @{bot_obj.telegram_username} boti sozlamalari muvaffaqiyatli saqlandi!")
    return redirect('superadmin:bots')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def bot_toggle_view(request, bot_id):
    bot_obj = get_object_or_404(BotModel, id=bot_id)
    action = request.POST.get('action', 'toggle')

    if action == 'start' or (action == 'toggle' and bot_obj.runtime_status != RuntimeStatus.RUNNING):
        bot_obj.status = BotStatus.ACTIVE
        bot_obj.runtime_status = RuntimeStatus.RUNNING
        bot_obj.save(update_fields=['status', 'runtime_status'])
        try:
            async_to_sync(BotRuntimeManager.start_bot_polling)(str(bot_obj.id))
            AuditLog.log(action="BOT_ISHLATILDI", actor=request.user.username, target=f"@{bot_obj.telegram_username}", details="Bot yoqildi", ip=request.META.get('REMOTE_ADDR', ''))
            messages.success(request, f"✅ Bot @{bot_obj.telegram_username} ishga tushirildi!")
        except Exception as e:
            messages.warning(request, f"Bot yoqildi: {e}")

    elif action == 'stop' or (action == 'toggle' and bot_obj.runtime_status == RuntimeStatus.RUNNING):
        bot_obj.runtime_status = RuntimeStatus.OFFLINE
        bot_obj.save(update_fields=['runtime_status'])
        try:
            async_to_sync(BotRuntimeManager.stop_bot_polling)(str(bot_obj.id))
            AuditLog.log(action="BOT_TOXTATILDI", actor=request.user.username, target=f"@{bot_obj.telegram_username}", details="Bot to'xtatildi", ip=request.META.get('REMOTE_ADDR', ''))
            messages.info(request, f"⏸ Bot @{bot_obj.telegram_username} to'xtatildi.")
        except Exception as e:
            messages.warning(request, f"Bot to'xtatildi: {e}")

    return redirect('superadmin:bots')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def bot_delete_view(request, bot_id):
    bot_obj = get_object_or_404(BotModel, id=bot_id)
    uname = bot_obj.telegram_username
    async_to_sync(BotRuntimeManager.stop_bot_polling)(str(bot_obj.id))
    bot_obj.delete()
    AuditLog.log(action="BOT_OCHIRILDI", actor=request.user.username, target=f"@{uname}", details="Bot o'chirildi", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🗑 Bot @{uname} butunlay o'chirildi.")
    return redirect('superadmin:bots')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def timings_view(request):
    SettingService.seed_defaults()
    global_timings = GameSetting.objects.filter(group='TIMINGS').order_by('key')
    
    bots = BotModel.objects.select_related('configuration').order_by('-created_at')
    bot_timings = []
    for b in bots:
        cfg = getattr(b, 'configuration', None)
        extra = cfg.extra_settings if cfg and cfg.extra_settings else {}
        bot_timings.append({
            'bot': b,
            'night_duration': cfg.night_duration_seconds if cfg and cfg.night_duration_seconds else SettingService.get_int('night_duration', 60),
            'voting_duration': cfg.voting_duration_seconds if cfg and cfg.voting_duration_seconds else SettingService.get_int('voting_duration', 20),
            'dawn_wait': extra.get('dawn_wait_duration', SettingService.get_int('dawn_wait_duration', 15)),
            'last_words': extra.get('last_words_duration', SettingService.get_int('last_words_duration', 50)),
            'lobby_timeout': extra.get('lobby_timeout_minutes', SettingService.get_int('lobby_timeout_minutes', 15)),
            'is_custom': bool(cfg and (cfg.night_duration_seconds != 60 or cfg.voting_duration_seconds != 60 or extra)),
        })

    context = {
        'global_timings': global_timings,
        'bot_timings': bot_timings,
        'active_tab': 'timings',
    }
    return render(request, 'superadmin/timings.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def bot_timing_save_view(request, bot_id):
    bot_obj = get_object_or_404(BotModel, id=bot_id)
    night_duration = int(request.POST.get('night_duration', 60))
    voting_duration = int(request.POST.get('voting_duration', 20))
    dawn_wait = int(request.POST.get('dawn_wait_duration', 15))
    last_words = int(request.POST.get('last_words_duration', 50))
    lobby_timeout = int(request.POST.get('lobby_timeout_minutes', 15))

    SettingService.set_bot_timing(
        bot_id=str(bot_obj.id),
        night_duration=night_duration,
        voting_duration=voting_duration,
        dawn_wait=dawn_wait,
        last_words=last_words,
        lobby_timeout=lobby_timeout
    )

    AuditLog.log(action="BOT_VAQTI_SOZLANDI", actor=request.user.username, target=f"@{bot_obj.telegram_username}", details=f"Tun: {night_duration}s, Ovoz: {voting_duration}s", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"✅ @{bot_obj.telegram_username} boti uchun maxsus vaqtlar saqlandi!")
    return redirect('superadmin:timings')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def prices_view(request):
    SettingService.seed_defaults()
    prices = GameSetting.objects.filter(group__in=['PRICES', 'HERO', 'RANKS', 'REWARDS']).order_by('group', 'key')
    context = {
        'prices': prices,
        'active_tab': 'prices',
    }
    return render(request, 'superadmin/prices.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def setting_save_view(request, setting_id):
    setting = get_object_or_404(GameSetting, id=setting_id)
    new_val = request.POST.get('value', '').strip()
    new_unit = request.POST.get('unit', '').strip()
    redirect_to = request.POST.get('redirect_to', 'settings')

    if new_val:
        setting.value = new_val
        if new_unit:
            setting.unit = new_unit
        setting.save(update_fields=['value', 'unit'])
        SettingService.reload_cache()
        AuditLog.log(action="SOZLAMA_YANGILANDI", actor=request.user.username, target=setting.key, details=f"Yangi qiymat: {new_val} {new_unit}", ip=request.META.get('REMOTE_ADDR', ''))
        messages.success(request, f"✅ {setting.title} saqlandi!")

    if redirect_to == 'timings':
        return redirect('superadmin:timings')
    elif redirect_to == 'prices':
        return redirect('superadmin:prices')
    return redirect('superadmin:dashboard')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def gifs_view(request):
    TextService.seed_defaults()
    gifs = BotSystemText.objects.filter(category='GIFS').order_by('key')
    context = {
        'gifs': gifs,
        'active_tab': 'gifs',
    }
    return render(request, 'superadmin/gifs.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
def texts_view(request):
    TextService.seed_defaults()
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    texts_qs = BotSystemText.objects.exclude(category='GIFS')
    if query:
        texts_qs = texts_qs.filter(Q(title__icontains=query) | Q(key__icontains=query) | Q(content_uz__icontains=query))
    if category:
        texts_qs = texts_qs.filter(category=category)

    texts = texts_qs.order_by('category', 'key')
    categories = [c for c in BotSystemText.CATEGORY_CHOICES if c[0] != 'GIFS']

    context = {
        'texts': texts,
        'categories': categories,
        'selected_category': category,
        'query': query,
        'active_tab': 'texts',
    }
    return render(request, 'superadmin/texts.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def text_save_view(request, text_id):
    import os, uuid
    from django.conf import settings

    text_obj = get_object_or_404(BotSystemText, id=text_id)
    text_obj.title = request.POST.get('title', text_obj.title)
    
    # Handle File Upload (from gallery / computer) if provided
    if request.FILES.get('media_file'):
        uploaded = request.FILES['media_file']
        ext = os.path.splitext(uploaded.name)[1].lower()
        if not ext:
            ext = '.png'
        filename = f"media_{text_obj.key}_{uuid.uuid4().hex[:8]}{ext}"
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded.chunks():
                destination.write(chunk)
                
        media_rel_url = f"/media/uploads/{filename}"
        full_url = request.build_absolute_uri(media_rel_url)
        text_obj.content_uz = full_url
    else:
        new_content = request.POST.get('content_uz', '').strip()
        if new_content:
            text_obj.content_uz = new_content

    text_obj.is_active = request.POST.get('is_active') == 'on'
    text_obj.save()
    TextService.reload_cache()

    redirect_to = request.POST.get('redirect_to', 'texts')
    AuditLog.log(action="MATN_YANGILANDI", actor=request.user.username, target=text_obj.key, details=f"Yangi media/matn: {text_obj.title}", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"✅ '{text_obj.title}' muvaffaqiyatli saqlandi!")

    if redirect_to == 'gifs':
        return redirect('superadmin:gifs')
    return redirect('superadmin:texts')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def promocodes_view(request):
    promos = PromoCode.objects.all().order_by('-created_at')
    context = {
        'promos': promos,
        'active_tab': 'promocodes',
    }
    return render(request, 'superadmin/promocodes.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def promocode_create_view(request):
    code = request.POST.get('code', '').strip().upper()
    reward_type = request.POST.get('reward_type', 'COINS')
    reward_amount = int(request.POST.get('reward_amount', 100))
    max_uses = int(request.POST.get('max_uses', 100))

    if not code:
        messages.error(request, "Promokod kodi kiritilmadi.")
        return redirect('superadmin:promocodes')

    if PromoCode.objects.filter(code__iexact=code).exists():
        messages.warning(request, f"'{code}' nomli promokod allaqachon mavjud!")
        return redirect('superadmin:promocodes')

    PromoCode.objects.create(
        code=code,
        reward_type=reward_type,
        reward_amount=reward_amount,
        max_uses=max_uses,
        is_active=True
    )
    AuditLog.log(action="PROMOKOD_YARATILDI", actor=request.user.username, target=code, details=f"{reward_amount} {reward_type}, max: {max_uses}", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🎉 '{code}' promokodi muvaffaqiyatli yaratildi!")
    return redirect('superadmin:promocodes')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def promocode_delete_view(request, promo_id):
    promo = get_object_or_404(PromoCode, id=promo_id)
    c = promo.code
    promo.delete()
    AuditLog.log(action="PROMOKOD_OCHIRILDI", actor=request.user.username, target=c, details="Promokod o'chirildi", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🗑 '{c}' promokodi o'chirildi.")
    return redirect('superadmin:promocodes')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def live_games_view(request):
    games = Game.objects.exclude(phase__in=['FINISHED', 'CANCELED']).select_related('bot').prefetch_related('players').order_by('-created_at')
    
    game_list = []
    for g in games:
        living_count = g.players.filter(is_alive=True).count()
        total_count = g.players.count()
        game_list.append({
            'game': g,
            'living_count': living_count,
            'total_count': total_count,
        })

    context = {
        'game_list': game_list,
        'active_tab': 'live_games',
    }
    return render(request, 'superadmin/live_games.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def game_force_end_view(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    game.phase = GamePhase.FINISHED
    game.save(update_fields=['phase'])
    AuditLog.log(action="OYIN_MAJBURIY_TOXTATILDI", actor=request.user.username, target=str(game.id), details=f"Guruh: {game.chat_id}", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, "🛑 O'yin majburiy to'xtatildi!")
    return redirect('superadmin:live_games')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def leaderboard_view(request):
    excluded_owner_ids = get_excluded_owner_tg_ids()
    # Only genuine registered players with at least 1 game played or positive score, excluding test and owner profiles
    top_winners = PlayerProfile.objects.filter(
        telegram_id__gte=100000000
    ).exclude(
        telegram_id__in=excluded_owner_ids
    ).exclude(
        telegram_username__icontains='test'
    ).select_related('stats').order_by('-stats__games_won', '-stats__games_played')[:50]
    
    leaderboard = []
    for idx, p in enumerate(top_winners, 1):
        wallet = Wallet.objects.filter(telegram_id=p.telegram_id).first()
        leaderboard.append({
            'rank': idx,
            'profile': p,
            'wallet': wallet,
            'coins': wallet.coins if wallet else 0,
            'diamonds': wallet.diamonds if wallet else 0,
            'stats': getattr(p, 'stats', None),
        })

    context = {
        'leaderboard': leaderboard,
        'active_tab': 'leaderboard',
    }
    return render(request, 'superadmin/leaderboard.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def give_bonus_view(request, profile_id):
    profile = get_object_or_404(PlayerProfile, id=profile_id)
    wallet, _ = Wallet.objects.get_or_create(telegram_id=profile.telegram_id)
    
    bonus_type = request.POST.get('bonus_type', 'COINS')
    amount = int(request.POST.get('amount', 50))

    if bonus_type == 'COINS':
        wallet.coins += amount
        wallet.save(update_fields=['coins'])
        msg = f"{amount} 💶 Dollar bonus berildi"
    else:
        wallet.diamonds += amount
        wallet.save(update_fields=['diamonds'])
        msg = f"{amount} 💎 Olmos bonus berildi"

    AuditLog.log(action="BONUS_BERILDI", actor=request.user.username, target=f"TG:{profile.telegram_id}", details=msg, ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🎁 {profile.first_name or profile.telegram_username} ga {msg}!")
    return redirect('superadmin:leaderboard')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def broadcasts_view(request):
    broadcasts = BroadcastMessage.objects.order_by('-created_at')[:20]
    context = {
        'broadcasts': broadcasts,
        'target_user': request.GET.get('target_user', ''),
        'active_tab': 'broadcasts',
    }
    return render(request, 'superadmin/broadcasts.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def broadcast_create_view(request):
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    target_audience = request.POST.get('target_audience', 'ALL_PLAYERS')
    target_user_id = request.POST.get('target_user_id', '').strip()
    photo_url = request.POST.get('photo_url', '').strip()
    button_text = request.POST.get('button_text', '').strip()
    button_url = request.POST.get('button_url', '').strip()

    if not title or not content:
        messages.error(request, "Sarlavha va xabar matnini kiritish majburiy!")
        return redirect('superadmin:broadcasts')

    broadcast = BroadcastMessage.objects.create(
        title=title,
        content=content,
        target_audience=target_audience,
        target_user_id=target_user_id,
        photo_url=photo_url,
        button_text=button_text,
        button_url=button_url
    )

    # Run dispatch in background thread
    t = threading.Thread(target=BroadcastService.execute_broadcast, args=(str(broadcast.id),), daemon=True)
    t.start()

    AuditLog.log(action="ELON_YUBORILDI", actor=request.user.username, target=target_audience, details=title, ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"📢 '{title}' sarlavhali e'lon yuborish boshlandi!")
    return redirect('superadmin:broadcasts')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def broadcast_delete_view(request, broadcast_id):
    broadcast = get_object_or_404(BroadcastMessage, id=broadcast_id)
    title = broadcast.title
    broadcast.delete()
    AuditLog.log(action="ELON_OCHIRILDI", actor=request.user.username, target=title, ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🗑 '{title}' e'loni o'chirildi.")
    return redirect('superadmin:broadcasts')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def broadcast_clear_all_view(request):
    count = BroadcastMessage.objects.count()
    BroadcastMessage.objects.all().delete()
    AuditLog.log(action="BARCHA_ELONLAR_TOZALANDI", actor=request.user.username, target="Hammasi", details=f"{count} ta e'lon tarixi tozalandi", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🗑 Barcha {count} ta e'lon tarixi tozalandi.")
    return redirect('superadmin:broadcasts')


def users_view(request):
    query = request.GET.get('q', '').strip()
    excluded_owner_ids = get_excluded_owner_tg_ids()

    profiles_qs = PlayerProfile.objects.exclude(telegram_id=999999999).select_related('stats').all()

    if query:
        if query.isdigit():
            profiles_qs = profiles_qs.filter(telegram_id=int(query))
        else:
            profiles_qs = profiles_qs.filter(Q(telegram_username__icontains=query) | Q(first_name__icontains=query))

    profiles = profiles_qs.order_by('-created_at')[:100]

    user_list = []
    from apps.economy.models import PlayerHero
    for p in profiles:
        is_owner = (p.telegram_id in excluded_owner_ids) or p.is_platform_owner
        wallet = Wallet.objects.filter(telegram_id=p.telegram_id).first()
        inv_data = PlayerInventoryService.get_full_inventory(p.telegram_id)
        hero = PlayerHero.objects.filter(telegram_id=p.telegram_id).first()

        user_list.append({
            'profile': p,
            'is_owner': is_owner,
            'wallet': wallet,
            'coins': "VIP (Cheksiz)" if is_owner else (wallet.coins if wallet else 0),
            'diamonds': "VIP (Cheksiz)" if is_owner else (wallet.diamonds if wallet else 0),
            'stats': getattr(p, 'stats', None),
            'inv': inv_data,
            'hero': hero,
        })

    context = {
        'user_list': user_list,
        'query': query,
        'active_tab': 'users',
    }
    return render(request, 'superadmin/users.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def user_balance_edit_view(request, profile_id):
    profile = get_object_or_404(PlayerProfile, id=profile_id)
    wallet, _ = Wallet.objects.get_or_create(telegram_id=profile.telegram_id)
    
    try:
        coins = int(request.POST.get('coins', wallet.coins))
        diamonds = int(request.POST.get('diamonds', wallet.diamonds))
        wallet.coins = max(0, coins)
        wallet.diamonds = max(0, diamonds)
        wallet.save(update_fields=['coins', 'diamonds'])

        stats, _ = PlayerStats.objects.get_or_create(player_profile=profile)
        stats.games_won = max(0, int(request.POST.get('games_won', stats.games_won)))
        stats.games_played = max(0, int(request.POST.get('games_played', stats.games_played)))
        stats.save(update_fields=['games_won', 'games_played'])

        # Inventory Items
        himoya = int(request.POST.get('himoya', 0))
        osish_himoya = int(request.POST.get('osish_himoya', 0))
        hujjat = int(request.POST.get('hujjat', 0))
        geroy_himoya = int(request.POST.get('geroy_himoya', 0))
        geroy = int(request.POST.get('geroy', 0))
        active_role = request.POST.get('active_role', '')

        PlayerInventoryService.set_full_inventory(
            telegram_id=profile.telegram_id,
            himoya=himoya,
            osish_himoya=osish_himoya,
            hujjat=hujjat,
            geroy_himoya=geroy_himoya,
            geroy=geroy,
            active_role=active_role
        )

        AuditLog.log(action="FOYDALANUVCHI_TAHRIRLANDI", actor=request.user.username, target=f"TG:{profile.telegram_id}", details=f"Balans va inventar yangilandi (Dollar: {coins}, Olmos: {diamonds})", ip=request.META.get('REMOTE_ADDR', ''))
        messages.success(request, "✅ Foydalanuvchi hisobi va inventari to'liq saqlandi!")
    except Exception as e:
        messages.error(request, f"Xatolik: {e}")

    return redirect('superadmin:users')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST

@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def user_delete_view(request, profile_id):
    profile = get_object_or_404(PlayerProfile, id=profile_id)
    tg_id = profile.telegram_id
    uname = profile.telegram_username or profile.full_name or f"TG:{tg_id}"

    # Delete related wallet, inventory, stats, transactions
    Wallet.objects.filter(telegram_id=tg_id).delete()
    Inventory.objects.filter(telegram_id=tg_id).delete()
    WalletTransaction.objects.filter(wallet__telegram_id=tg_id).delete()
    VIPSubscription.objects.filter(user__telegram_id=tg_id).delete()

    if profile.user and not profile.user.is_superuser:
        try:
            profile.user.delete()
        except Exception:
            pass
    profile.delete()

    AuditLog.log(action="FOYDALANUVCHI_OCHIRILDI", actor=request.user.username, target=uname, details=f"Foydalanuvchi va barcha ma'lumotlari o'chirildi (TG: {tg_id})", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🗑 Foydalanuvchi '{uname}' platformadan butunlay o'chirildi.")
    return redirect('superadmin:users')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def user_reset_stats_view(request, profile_id):
    profile = get_object_or_404(PlayerProfile, id=profile_id)
    wallet = Wallet.objects.filter(telegram_id=profile.telegram_id).first()
    if wallet:
        wallet.coins = 0
        wallet.diamonds = 0
        wallet.money = 0
        wallet.save(update_fields=['coins', 'diamonds', 'money'])

    stats = getattr(profile, 'stats', None)
    if stats:
        stats.games_played = 0
        stats.games_won = 0
        stats.games_lost = 0
        stats.mafia_wins = 0
        stats.civilian_wins = 0
        stats.save()

    PlayerInventoryService.set_full_inventory(
        telegram_id=profile.telegram_id,
        himoya=0, osish_himoya=0, hujjat=0, geroy_himoya=0, geroy=0, active_role=''
    )

    AuditLog.log(action="FOYDALANUVCHI_NOLLANDI", actor=request.user.username, target=f"TG:{profile.telegram_id}", details="Barcha balans va inventarlar 0 qilindi", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, "✅ Foydalanuvchi hisobi va barcha inventarlari 0 ga tushirildi!")
    return redirect('superadmin:users')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def audit_view(request):
    query = request.GET.get('q', '').strip()
    audits_qs = AuditLog.objects.all()

    if query:
        audits_qs = audits_qs.filter(Q(action__icontains=query) | Q(target__icontains=query) | Q(actor__icontains=query) | Q(details__icontains=query))

    audits = audits_qs.order_by('-created_at')[:200]
    total_count = AuditLog.objects.count()

    context = {
        'audits': audits,
        'total_count': total_count,
        'query': query,
        'active_tab': 'audit',
    }
    return render(request, 'superadmin/audit.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def audit_clear_view(request):
    AuditLog.objects.all().delete()
    AuditLog.log(action="AUDIT_TOZALANDI", actor=request.user.username, target="Audit Tarixi", details="Barcha audit loglari tozalandi", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, "✅ Audit loglari tozalandi.")
    return redirect('superadmin:audit')


@user_passes_test(is_superadmin, login_url='superadmin:login')
def roles_view(request):
    from apps.games.models import Role
    from apps.games.engine.roles import RoleDistributionService
    RoleDistributionService.get_or_create_base_roles()

    ROLE_METADATA = {
        # 13 Civilian Roles
        'CITIZEN': {'icon': '👨🏼', 'title': 'Tinch aholi', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'DOCTOR': {'icon': '👨🏼‍⚕️', 'title': 'Shifokor', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'DETECTIVE': {'icon': '🕵🏻‍♂️', 'title': 'Komissar', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'SERJANT': {'icon': '👮🏼‍♂️', 'title': 'Serjant', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'HAMSHIRA': {'icon': '👩🏼‍⚕️', 'title': 'Hamshira', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'OMADLI': {'icon': '🤞🏼', 'title': 'Omadli', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'JANOB': {'icon': '🎖', 'title': 'Janob', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'SOTQIN': {'icon': '🤓', 'title': 'Sotqin', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'ADMIRAL': {'icon': '🧑🏻‍✈️', 'title': 'Admiral', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'ROBINGUD': {'icon': '🏹', 'title': 'Robin Gud', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'FOTOPARATCHI': {'icon': '📸', 'title': 'Fotoparatchi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'DAYDI': {'icon': '🍾', 'title': 'Daydi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'KEZUVCHI': {'icon': '💃', 'title': 'Kezuvchi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        # 7 Mafia Roles
        'DON': {'icon': '🤵🏻', 'title': 'Don', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'MAFIA': {'icon': '🤵🏼', 'title': 'Mafia', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'ADVOKAT': {'icon': '💼', 'title': 'Advokat', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'UBIYTSA': {'icon': '🥷', 'title': 'Ubiytsa', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'JURNALIST': {'icon': '👩🏼‍💻', 'title': 'Jurnalist', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'AYGOQCHI': {'icon': '🦇', 'title': "Ayg'oqchi", 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'LABORANT': {'icon': '👩‍⚕️', 'title': 'Laborant', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        # 17 Solo Roles
        'KIMYOGAR': {'icon': '👨‍🔬', 'title': 'Kimyogar', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'RAIS': {'icon': '💰', 'title': 'Rais', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'BORI': {'icon': '🐺', 'title': "Bo'ri", 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'AFERIST': {'icon': '🤹🏻', 'title': 'Aferist', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'GAZABKOR': {'icon': '🧌', 'title': "G'azabkor", 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'SEHRGAR': {'icon': '🧙', 'title': 'Sehrgar', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'QOTIL': {'icon': '🔪', 'title': 'Qotil', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'KONCHI': {'icon': '👷🏻‍♂️', 'title': 'Konchi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'QAROQCHI': {'icon': '⚔️', 'title': 'Qaroqchi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'QORBOBO': {'icon': '🎅🏻', 'title': 'Qorbobo', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'OSHPAZ': {'icon': '👨🏼‍🍳', 'title': 'Oshpaz', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'AFSUNGAR': {'icon': '🧙🏼', 'title': 'Afsungar', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        'TUZOQCHI': {'icon': '🕸', 'title': 'Tuzoqchi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'AXMOQ': {'icon': '🤪', 'title': 'Axmoq', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'BUQALAMUN': {'icon': '🦎', 'title': 'Buqalamun', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'JOKER': {'icon': '🃏', 'title': 'Joker', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
        'SUIDSID': {'icon': '🤡', 'title': 'Suidsid', 'is_passive': True, 'afk_text': 'Jazosiz (Passiv)'},
        # 1 Zombie Role
        'ZOMBI': {'icon': '🧟', 'title': 'Zombi', 'is_passive': False, 'afk_text': '2 tun harakatsiz → Chetlatiladi'},
    }

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip().upper()

    roles_qs = Role.objects.all()

    # Category counts
    total_count = roles_qs.count()
    civilian_count = Role.objects.filter(team='CIVILIAN').count()
    mafia_count = Role.objects.filter(team='MAFIA').count()
    solo_count = Role.objects.filter(team='SOLO').count()
    zombie_count = Role.objects.filter(team='ZOMBIE').count()
    active_count = Role.objects.filter(is_active=True).count()

    if category in ['CIVILIAN', 'MAFIA', 'SOLO', 'ZOMBIE']:
        roles_qs = roles_qs.filter(team=category)

    if query:
        roles_qs = roles_qs.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        )

    roles = roles_qs.order_by('priority', 'name')

    role_list = []
    for r in roles:
        meta = ROLE_METADATA.get(r.name, {
            'icon': '👤',
            'title': r.name.capitalize(),
            'is_passive': False,
            'afk_text': '2 tun harakatsiz → Chetlatiladi'
        })
        role_list.append({
            'obj': r,
            'icon': meta['icon'],
            'title': meta['title'],
            'is_passive': meta['is_passive'],
            'afk_text': meta['afk_text'],
        })

    context = {
        'role_list': role_list,
        'total_count': total_count,
        'civilian_count': civilian_count,
        'mafia_count': mafia_count,
        'solo_count': solo_count,
        'zombie_count': zombie_count,
        'active_count': active_count,
        'selected_category': category,
        'query': query,
        'active_tab': 'roles',
    }
    return render(request, 'superadmin/roles.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def role_save_view(request, role_id):
    from apps.games.models import Role
    role_obj = get_object_or_404(Role, id=role_id)
    description = request.POST.get('description', '').strip()
    priority = int(request.POST.get('priority', role_obj.priority))

    if description:
        role_obj.description = description
    role_obj.priority = priority
    role_obj.save(update_fields=['description', 'priority'])

    AuditLog.log(action="ROL_TAHRIRLANDI", actor=request.user.username, target=role_obj.name, details=f"Yangi tavsif / prioritet: {priority}", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"✅ {role_obj.name} roli ma'lumotlari saqlandi!")
    return redirect('superadmin:roles')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def role_toggle_view(request, role_id):
    from apps.games.models import Role
    role_obj = get_object_or_404(Role, id=role_id)
    role_obj.is_active = not role_obj.is_active
    role_obj.save(update_fields=['is_active'])

    status_text = "yoqildi" if role_obj.is_active else "o'chirildi"
    AuditLog.log(action="ROL_HOLATI_OZGARTIRILDI", actor=request.user.username, target=role_obj.name, details=f"Holat: {status_text}", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"✅ {role_obj.name} roli holati {status_text}!")
    return redirect('superadmin:roles')




from apps.superadmin.models import FeedbackMessage, UserNotification

@user_passes_test(is_superadmin, login_url='superadmin:login')
def feedback_list_view(request):
    """Displays user feedback and support tickets."""
    feedbacks = FeedbackMessage.objects.all().order_by('-created_at')
    new_count = feedbacks.filter(is_replied=False).count()
    context = {
        'feedbacks': feedbacks,
        'new_count': new_count,
        'active_tab': 'feedback',
    }
    return render(request, 'superadmin/feedback.html', context)


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def feedback_reply_view(request, feedback_id):
    """Sends admin reply to user via Telegram Bot."""
    fb = get_object_or_404(FeedbackMessage, id=feedback_id)
    reply_text = request.POST.get('reply_text', '').strip()

    if not reply_text:
        messages.error(request, "Javob matni bo'sh bo'lishi mumkin emas.")
        return redirect('superadmin:feedback_list')

    master_token = (
        os.environ.get('MASTER_BOT_TOKEN') or
        os.environ.get('TELEGRAM_BOT_TOKEN') or
        '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
    )

    sent = False
    try:
        import requests
        url = f"https://api.telegram.org/bot{master_token}/sendMessage"
        msg_text = (
            f"📩 <b>Administrator javobi:</b>\n\n"
            f"<i>Sizning murojaatingiz:</i>\n&quot;{fb.message_text}&quot;\n\n"
            f"💬 <b>Javob:</b>\n{reply_text}"
        )
        resp = requests.post(url, json={'chat_id': fb.telegram_id, 'text': msg_text, 'parse_mode': 'HTML'}, timeout=8)
        if resp.status_code == 200 and resp.json().get('ok'):
            sent = True
    except Exception as e:
        logger.warning(f"Failed to send admin reply: {e}")

    fb.is_replied = True
    fb.admin_reply = reply_text
    fb.replied_at = timezone.now()
    fb.save(update_fields=['is_replied', 'admin_reply', 'replied_at'])

    # Save In-App Notification
    UserNotification.objects.create(
        telegram_id=fb.telegram_id,
        title="Admin javobi",
        message=reply_text,
        notification_type='ADMIN'
    )

    if sent:
        messages.success(request, f"✅ {fb.user_display_name} ga javob muvaffaqiyatli yuborildi!")
    else:
        messages.warning(request, f"Javob bazada saqlangan bo'lsa-da, bot orqali yetkazishda xatolik yuz berdi.")

    return redirect('superadmin:feedback_list')

@user_passes_test(is_superadmin, login_url='superadmin:login')
def groups_view(request):
    """Displays all active Telegram groups where bots operate, including group owner info."""
    from apps.bots.models import BotGroup
    query = request.GET.get('q', '').strip()
    qs = BotGroup.objects.select_related('bot').all().order_by('-last_active_at')

    if query:
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(username__icontains=query) |
            Q(owner_name__icontains=query) |
            Q(owner_username__icontains=query) |
            Q(bot__name__icontains=query) |
            Q(bot__telegram_username__icontains=query)
        )

    context = {
        'group_list': qs,
        'query': query,
        'active_tab': 'groups',
    }
    return render(request, 'superadmin/groups.html', context)

@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def group_credentials_save_view(request, group_id):
    """Saves login and password for a group cabinet from SuperAdmin."""
    from apps.bots.models import BotGroup
    group_obj = get_object_or_404(BotGroup, id=group_id)
    login = request.POST.get('login', '').strip()
    password = request.POST.get('password', '').strip()

    if login:
        # Check uniqueness
        if BotGroup.objects.filter(cabinet_login=login).exclude(id=group_obj.id).exists():
            messages.error(request, f"❌ '{login}' logini boshqa guruhda ishlatilgan!")
            return redirect('superadmin:groups')
        group_obj.cabinet_login = login

    if password:
        group_obj.cabinet_password = password

    group_obj.save(update_fields=['cabinet_login', 'cabinet_password'])
    AuditLog.log(
        action="GURUH_LOGIN_PAROL_YANGILANDI",
        actor=request.user.username,
        target=group_obj.title,
        details=f"Login: {group_obj.cabinet_login}, Parol o'zgartirildi",
        ip=request.META.get('REMOTE_ADDR', '')
    )
    messages.success(request, f"✅ '{group_obj.title}' guruhi uchun login va parol muvaffaqiyatli saqlandi!")
    return redirect('superadmin:groups')


@user_passes_test(is_superadmin, login_url='superadmin:login')
@require_POST
def group_delete_view(request, group_id):
    """Deletes a group entry from SuperAdmin."""
    from apps.bots.models import BotGroup
    group_obj = get_object_or_404(BotGroup, id=group_id)
    title = group_obj.title
    group_obj.delete()
    AuditLog.log(action="GURUH_OCHIRILDI", actor=request.user.username, target=title, details="Guruh bazadan o'chirildi", ip=request.META.get('REMOTE_ADDR', ''))
    messages.success(request, f"🗑 '{title}' guruhi o'chirildi.")
    return redirect('superadmin:groups')
