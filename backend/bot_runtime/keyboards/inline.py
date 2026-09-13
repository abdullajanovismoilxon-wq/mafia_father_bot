"""
MAFIA BOT FATHER — Telegram Inline Keyboards
=============================================
Compact callback_data (under 64 bytes limit):
  - Night action:  n:{game12}:{act}:{player12}
  - Komissar menu: km:{game12}:inv / km:{game12}:sht
  - Vote:          v:{game12}:{player12}
  - Hanging:       hg:{game12}:kill:{player12} / hg:{game12}:save:{player12}
  - Economy/Shop:  eco:...
"""
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


def _short(uid: str) -> str:
    """Returns first 12 chars of a UUID string for compact callback_data."""
    return str(uid)[:12]


# ---------------------------------------------------------------------------
# Master/Child PM /start keyboards
# ---------------------------------------------------------------------------

def build_child_start_keyboard(bot_username: str, lang_code: str = 'uz') -> InlineKeyboardMarkup:
    """Builds localized PM /start keyboard."""
    builder = InlineKeyboardBuilder()

    labels = {
        'uz': {
            'add': "➕ O'yinni guruhingizga qo'shing ↗",
            'lang': "🌐 Til",
            'news': "📢 Yangiliklar ↗",
            'rules': "🃏 Qoidalar"
        },
        'ru': {
            'add': "➕ Добавить бота в группу ↗",
            'lang': "🌐 Язык",
            'news': "📢 Новости ↗",
            'rules': "🃏 Правила игры"
        },
        'en': {
            'add': "➕ Add bot to group ↗",
            'lang': "🌐 Language",
            'news': "📢 News ↗",
            'rules': "🃏 Rules"
        }
    }
    l = labels.get(lang_code, labels['uz'])

    from apps.superadmin.services import TextService
    txt_add = TextService.get_text('btn_child_add_group', fallback=l['add'])
    txt_lang = TextService.get_text('btn_child_lang', fallback=l['lang'])
    txt_news = TextService.get_text('btn_child_news', fallback=l['news'])
    txt_rules = TextService.get_text('btn_child_rules', fallback=l['rules'])

    builder.row(
        InlineKeyboardButton(
            text=txt_add,
            url=f"https://t.me/{bot_username}?startgroup=true"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=txt_lang,
            callback_data="child:lang"
        ),
        InlineKeyboardButton(
            text=txt_news,
            url="https://t.me/MafiaBotFather"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=txt_rules,
            callback_data="child:rules"
        )
    )
    return builder.as_markup()


def build_language_keyboard() -> InlineKeyboardMarkup:
    """Builds language selection keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:set:uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:set:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:set:en")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="child:start")
    )
    return builder.as_markup()


def build_rules_back_keyboard() -> InlineKeyboardMarkup:
    """Builds back button for rules text."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="child:start")
    )
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Roles Guide Keyboards (/roles in PM)
# ---------------------------------------------------------------------------


def build_roles_guide_keyboard(current_tab: str = 'all') -> InlineKeyboardMarkup:
    """Builds interactive tabs for /roles command."""
    builder = InlineKeyboardBuilder()
    
    t_civ = "✅ 🏛 Tinch aholi" if current_tab == 'civ' else "🏛 Tinch aholi"
    t_maf = "✅ 🔫 Mafiya" if current_tab == 'maf' else "🔫 Mafiya"
    t_solo = "✅ 🃏 Yakka rollar" if current_tab == 'solo' else "🃏 Yakka rollar"
    t_zomb = "✅ 🧟 Zombi" if current_tab == 'zomb' else "🧟 Zombi"
    t_all = "✅ 📋 Barchasi" if current_tab == 'all' else "📋 Barchasi"

    builder.row(
        InlineKeyboardButton(text=t_civ, callback_data="roles:tab:civ"),
        InlineKeyboardButton(text=t_maf, callback_data="roles:tab:maf")
    )
    builder.row(
        InlineKeyboardButton(text=t_solo, callback_data="roles:tab:solo"),
        InlineKeyboardButton(text=t_zomb, callback_data="roles:tab:zomb")
    )
    builder.row(
        InlineKeyboardButton(text=t_all, callback_data="roles:tab:all")
    )
    return builder.as_markup()


def build_roles_list_keyboard() -> InlineKeyboardMarkup:
    """Builds roles list keyboard for PM /roles command."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🤵🏻 Don", callback_data="role_info:don"),
        InlineKeyboardButton(text="🤵🏼 Mafia", callback_data="role_info:mafia")
    )
    builder.row(
        InlineKeyboardButton(text="👨🏼‍⚕️ Shifokor", callback_data="role_info:doctor"),
        InlineKeyboardButton(text="🕵🏻‍♂️ Komissar", callback_data="role_info:detective")
    )
    builder.row(
        InlineKeyboardButton(text="👨🏼 Tinch aholi", callback_data="role_info:citizen")
    )
    return builder.as_markup()


def build_role_detail_back_keyboard() -> InlineKeyboardMarkup:
    """Builds back button for single role description view."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Rollar ro'yxatiga qaytish", callback_data="role_info:menu")
    )
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Group Lobby & Navigation
# ---------------------------------------------------------------------------

def _player_team_badge(player) -> str:
    """Returns 🔴 or 🔵 if player has a team_side assigned."""
    if hasattr(player, 'metadata') and isinstance(player.metadata, dict):
        side = player.metadata.get('team_side', '')
        if side == 'RED':
            return '🔴 '
        elif side == 'BLUE':
            return '🔵 '
    return ''


def _player_health_badge(player) -> str:
    """Returns ' (❤️ 45%)' if player has taken damage and health is below 100%."""
    if player and hasattr(player, 'health') and player.health is not None:
        try:
            hp = int(player.health)
            if 0 < hp < 100:
                return f" (❤️ {hp}%)"
        except (ValueError, TypeError):
            pass
    return ''



def build_team_lobby_keyboard(bot_username: str, game_id: str, red_count: int = 0, blue_count: int = 0) -> InlineKeyboardMarkup:
    """Builds group /team lobby keyboard with Red and Blue team deep links."""
    from apps.superadmin.services import TextService
    lbl_red = TextService.get_text('btn_team_red', fallback="🔴 Qizil jamoa ({count})").replace('{count}', str(red_count))
    lbl_blue = TextService.get_text('btn_team_blue', fallback="🔵 Ko'k jamoa ({count})").replace('{count}', str(blue_count))
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=lbl_red,
            url=f"https://t.me/{bot_username}?start=jointeam_{game_id}_RED"
        ),
        InlineKeyboardButton(
            text=lbl_blue,
            url=f"https://t.me/{bot_username}?start=jointeam_{game_id}_BLUE"
        )
    )
    return builder.as_markup()


def build_group_lobby_keyboard(arg1: str, arg2: str) -> InlineKeyboardMarkup:
    """
    Builds group /game lobby keyboard with join deep link.
    Auto-detects which argument is bot_username and which is game_id to avoid any order mismatch.
    """
    str1 = str(arg1).strip().lstrip('@')
    str2 = str(arg2).strip().lstrip('@')

    if '-' in str1 and len(str1) >= 20: # str1 is UUID game_id
        game_id = str1
        bot_username = str2
    elif '-' in str2 and len(str2) >= 20: # str2 is UUID game_id
        bot_username = str1
        game_id = str2
    elif str1.lower().endswith('bot'):
        bot_username = str1
        game_id = str2
    else:
        bot_username = str2
        game_id = str1

    from apps.superadmin.services import TextService
    btn_label = TextService.get_text('btn_join_game', fallback="👱🏻 Qo'shilish ↗")
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=btn_label,
            url=f"https://t.me/{bot_username}?start=join_{game_id}"
        )
    )
    return builder.as_markup()


def build_back_to_group_keyboard(chat_id: int = None, chat_username: str = None) -> InlineKeyboardMarkup:
    """Builds 'Guruhga o'tish ↗' PM button."""
    from apps.superadmin.services import TextService
    lbl = TextService.get_text('btn_back_group', fallback="Guruhga o'tish ↗")
    builder = InlineKeyboardBuilder()
    if chat_username:
        url = f"https://t.me/{chat_username.replace('@', '')}"
    elif chat_id:
        clean_id = str(abs(chat_id))
        if clean_id.startswith("100"):
            clean_id = clean_id[3:]
        url = f"https://t.me/c/{clean_id}/999999"
    else:
        url = "https://t.me"
    builder.row(
        InlineKeyboardButton(text=lbl, url=url)
    )
    return builder.as_markup()


def build_bot_pm_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Builds 'Botga o'tish ↗' button for group messages."""
    from apps.superadmin.services import TextService
    lbl = TextService.get_text('btn_bot_pm', fallback="Botga o'tish ↗")
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=lbl,
            url=f"https://t.me/{bot_username}"
        )
    )
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Night action target keyboard
# callback_data: "n:{game12}:{act}:{player12}"  ≤ 32 bytes ✓
# ---------------------------------------------------------------------------

def build_night_target_keyboard(
    game_id: str,
    action_type: str,
    living_players: list,
    current_player_id: str = None
) -> InlineKeyboardMarkup:
    """
    Builds vertical night target selection keyboard.
    Excludes the actor from targets unless doctor/advokat/kimyogar self-targetable actions.
    """
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    act_map = {
        "kill": "k",
        "protect": "p",
        "investigate": "inv",
        "shoot": "sht",
        "qotil": "qot",
        "kezuvchi": "kez",
        "daydi": "day",
        "advokat": "adv",
        "ubiytsa": "ubi",
        "tuzoqchi": "tuz",
        "zombi": "zom",
        "kimyogar": "kim",
        "axmoq": "axm",
        "buqalamun": "buq",
        "rais": "rai",
        "joker": "jk",
    }
    act = act_map.get(action_type, action_type)

    if act in ["p", "adv", "kim"]:
        targets = list(living_players)
    else:
        targets = [p for p in living_players if str(p.id) != str(current_player_id)]
        if not targets:
            targets = list(living_players)

    actor = next((p for p in living_players if str(p.id) == str(current_player_id)), None)
    actor_rname = actor.role.name if actor and actor.role else None

    is_actor_mafia = bool(actor_rname and actor_rname in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"])
    is_actor_police = bool(actor_rname and actor_rname in ["DETECTIVE", "KOMISSAR", "SHERIFF", "SERJANT", "ADMIRAL"])
    is_actor_medical = bool(actor_rname and actor_rname in ["DOCTOR", "SHIFOKOR", "DOKTOR", "HAMSHIRA"])

    for idx, player in enumerate(targets, 1):
        display = (player.display_name or player.username or "O'yinchi")[:20]
        team_badge = _player_team_badge(player)
        hp_badge = _player_health_badge(player)
        pid = _short(str(player.id))

        p_rname = player.role.name if player.role else None
        role_hint = ""
        if p_rname:
            if is_actor_mafia and p_rname in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"]:
                from bot_runtime.handlers.night import role_icon
                role_hint = f" {role_icon(p_rname)}"
            elif is_actor_police and p_rname in ["DETECTIVE", "KOMISSAR", "SHERIFF", "SERJANT", "ADMIRAL"]:
                from bot_runtime.handlers.night import role_icon
                role_hint = f" {role_icon(p_rname)}"
            elif is_actor_medical and p_rname in ["DOCTOR", "SHIFOKOR", "DOKTOR", "HAMSHIRA"]:
                from bot_runtime.handlers.night import role_icon
                role_hint = f" {role_icon(p_rname)}"

        builder.button(
            text=f"{team_badge}{idx}. {display}{role_hint}{hp_badge}",
            callback_data=f"n:{gid}:{act}:{pid}"
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"n_skip:{gid}")
    )
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Voting keyboard (PM-based)
# callback_data: "v:{game12}:{player12}" — max 28 bytes ✓
# ---------------------------------------------------------------------------

def build_voting_keyboard(
    game_id: str,
    living_players: list,
    voter_id: str
) -> InlineKeyboardMarkup:
    """Builds PM voting keyboard with teammate badges (voter cannot vote for themselves)."""
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    targets = [p for p in living_players if str(p.id) != str(voter_id)]
    if not targets:
        targets = list(living_players)

    voter = next((p for p in living_players if str(p.id) == str(voter_id)), None)
    voter_rname = voter.role.name if voter and voter.role else None

    is_voter_mafia = bool(voter_rname and voter_rname in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"])
    is_voter_police = bool(voter_rname and voter_rname in ["DETECTIVE", "KOMISSAR", "SHERIFF", "SERJANT", "ADMIRAL"])
    is_voter_medical = bool(voter_rname and voter_rname in ["DOCTOR", "SHIFOKOR", "DOKTOR", "HAMSHIRA"])

    for idx, player in enumerate(targets, 1):
        display = (player.display_name or player.username or "O'yinchi")[:20]
        team_badge = _player_team_badge(player)
        hp_badge = _player_health_badge(player)
        pid = _short(str(player.id))

        p_rname = player.role.name if player.role else None
        role_hint = ""
        if p_rname:
            if is_voter_mafia and p_rname in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"]:
                from bot_runtime.handlers.night import role_icon
                role_hint = f" {role_icon(p_rname)}"
            elif is_voter_police and p_rname in ["DETECTIVE", "KOMISSAR", "SHERIFF", "SERJANT", "ADMIRAL"]:
                from bot_runtime.handlers.night import role_icon
                role_hint = f" {role_icon(p_rname)}"
            elif is_voter_medical and p_rname in ["DOCTOR", "SHIFOKOR", "DOKTOR", "HAMSHIRA"]:
                from bot_runtime.handlers.night import role_icon
                role_hint = f" {role_icon(p_rname)}"

        builder.button(
            text=f"{team_badge}{idx}. {display}{role_hint}{hp_badge}",
            callback_data=f"v:{gid}:{pid}"
        )
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Komissar action keyboard
# callback_data: "km:{game12}:inv" or "km:{game12}:sht" — max 20 bytes ✓
# ---------------------------------------------------------------------------

def build_komissar_action_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Builds Komissar 2-option keyboard (Tekshirish / Otish) with Skip option."""
    from apps.superadmin.services import TextService
    btn_inv = TextService.get_text('btn_action_investigate', fallback="🔍 Tekshirish")
    btn_sht = TextService.get_text('btn_action_shoot', fallback="🔫 Otish")
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    builder.button(text=btn_inv, callback_data=f"km:{gid}:inv")
    builder.button(text=btn_sht, callback_data=f"km:{gid}:sht")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"n_skip:{gid}")
    )
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Hanging confirmation keyboard
# callback_data: "hg:{game12}:kill:{player12}" — max 30 bytes ✓
# ---------------------------------------------------------------------------

def build_hanging_keyboard(game_id: str, target_id: str, kill_count: int = 0, save_count: int = 0) -> InlineKeyboardMarkup:
    """Builds hanging confirmation keyboard (👍 {kill_count} | 👎 {save_count}) matching Image 2."""
    from apps.superadmin.services import TextService
    btn_hang = TextService.get_text('btn_hanging_kill', fallback="👍 {count}").replace('{count}', str(kill_count))
    btn_save = TextService.get_text('btn_hanging_save', fallback="👎 {count}").replace('{count}', str(save_count))
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    pid = _short(target_id)
    builder.button(text=btn_hang, callback_data=f"hg:{gid}:kill:{pid}")
    builder.button(text=btn_save, callback_data=f"hg:{gid}:save:{pid}")
    builder.adjust(2)
    return builder.as_markup()


def build_profile_interactive_keyboard(
    himoya_on: bool = True,
    osish_on: bool = True,
    hujjat_on: bool = True,
    geroy_himoya_on: bool = True,
    vaksina_on: bool = True,
    dori_on: bool = True,
    sirpanish_on: bool = True,
    tg_id: int = 0
) -> InlineKeyboardMarkup:
    """Builds /profile keyboard matching user's exact specification with dynamic TextService."""
    from apps.superadmin.services import TextService
    builder = InlineKeyboardBuilder()

    h_btn = TextService.get_text('btn_profile_himoya_on' if himoya_on else 'btn_profile_himoya_off', fallback="🛡 - 🟢 ON" if himoya_on else "🛡 - 🔴 OFF")
    d_btn = TextService.get_text('btn_profile_hujjat_on' if hujjat_on else 'btn_profile_hujjat_off', fallback="📁 - 🟢 ON" if hujjat_on else "📁 - 🔴 OFF")
    o_btn = TextService.get_text('btn_profile_osish_on' if osish_on else 'btn_profile_osish_off', fallback="⚖️ - 🟢 ON" if osish_on else "⚖️ - 🔴 OFF")
    g_btn = TextService.get_text('btn_profile_geroy_h_on' if geroy_himoya_on else 'btn_profile_geroy_h_off', fallback="🔰 - 🟢 ON" if geroy_himoya_on else "🔰 - 🔴 OFF")
    v_btn = TextService.get_text('btn_profile_vaksina_on' if vaksina_on else 'btn_profile_vaksina_off', fallback="💉 - 🟢 ON" if vaksina_on else "💉 - 🔴 OFF")
    p_btn = TextService.get_text('btn_profile_dori_on' if dori_on else 'btn_profile_dori_off', fallback="💊 - 🟢 ON" if dori_on else "💊 - 🔴 OFF")
    s_btn = TextService.get_text('btn_profile_sirpanish_on' if sirpanish_on else 'btn_profile_sirpanish_off', fallback="⛸ - 🟢 ON" if sirpanish_on else "⛸ - 🔴 OFF")

    lbl_para = TextService.get_text('btn_profile_mypara', fallback="💍 Mening Param")
    lbl_shop = TextService.get_text('btn_profile_shop', fallback="🎒 Do'kon")
    lbl_dia = TextService.get_text('btn_profile_buy_dia', fallback="💎 Xarid qilish")
    lbl_money = TextService.get_text('btn_profile_buy_money', fallback="💶 Xarid qilish")
    lbl_hero = TextService.get_text('btn_profile_hero', fallback="🥷 Mening Geroyim")

    builder.row(
        InlineKeyboardButton(text=h_btn, callback_data="eco:toggle:himoya"),
        InlineKeyboardButton(text=d_btn, callback_data="eco:toggle:hujjat")
    )
    builder.row(
        InlineKeyboardButton(text=o_btn, callback_data="eco:toggle:osish"),
        InlineKeyboardButton(text=g_btn, callback_data="eco:toggle:geroy_h")
    )
    builder.row(
        InlineKeyboardButton(text=v_btn, callback_data="eco:toggle:vaksina"),
        InlineKeyboardButton(text=p_btn, callback_data="eco:toggle:dori_h")
    )
    builder.row(
        InlineKeyboardButton(text=s_btn, callback_data="eco:toggle:sirpanish_h"),
        InlineKeyboardButton(text=lbl_para, callback_data="eco:menu:mypara")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_shop, callback_data="eco:menu:shop")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_dia, callback_data="eco:menu:buy_dia"),
        InlineKeyboardButton(text=lbl_money, callback_data="eco:menu:buy_money")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_hero, callback_data="eco:menu:hero")
    )
    from apps.superadmin.services import SettingService, TextService
    base_url = SettingService.get('webapp_base_url', os.environ.get('WEBAPP_BASE_URL', 'https://16-171-175-23.sslip.io')).rstrip('/')
    webapp_url = f"{base_url}/webapp/profile/?tg_id={tg_id}"
    lbl_webapp = TextService.get_text('btn_profile_webapp', fallback="📱 Mini Appda ochish ↗")
    builder.row(
        InlineKeyboardButton(text=lbl_webapp, web_app=WebAppInfo(url=webapp_url))
    )
    return builder.as_markup()


def build_profile_keyboard() -> InlineKeyboardMarkup:
    """Alias for profile keyboard."""
    return build_profile_interactive_keyboard()


# ---------------------------------------------------------------------------
# Marketplace & Shop Submenus
# ---------------------------------------------------------------------------

def build_market_main_keyboard() -> InlineKeyboardMarkup:
    """Builds the main Do'kon (Shop) items keyboard with active hero items and dynamic TextService."""
    from apps.superadmin.services import SettingService, TextService
    p_him = SettingService.get_int('price_himoya', 300)
    p_osish = SettingService.get_int('price_osish_himoya', 1)
    p_huj = SettingService.get_int('price_hujjat', 200)
    p_vak = SettingService.get_int('price_vaksina', 150)
    p_dori = SettingService.get_int('price_dori_himoya', 130)
    p_sirp = SettingService.get_int('price_sirpanish_himoya', 150)
    p_geroy = SettingService.get_int('price_geroy', 80)
    p_geroy_h = SettingService.get_int('price_geroy_himoya', 3)
    p_vip = SettingService.get_int('price_vip_30', 30)

    lbl_him = TextService.get_text('btn_shop_himoya', fallback="🛡 Himoya ({price} 💶)").replace('{price}', str(p_him))
    lbl_osish = TextService.get_text('btn_shop_osish_himoya', fallback="⚖️ Ovozdan himoya ({price} 💎)").replace('{price}', str(p_osish))
    lbl_huj = TextService.get_text('btn_shop_hujjat', fallback="📁 Hujjatlar ({price} 💶)").replace('{price}', str(p_huj))
    lbl_vak = TextService.get_text('btn_shop_vaksina', fallback="💉 Zombi Vaksinasi ({price} 💶)").replace('{price}', str(p_vak))
    lbl_dori = TextService.get_text('btn_shop_dori_himoya', fallback="💊 Doridan himoya ({price} 💶)").replace('{price}', str(p_dori))
    lbl_sirp = TextService.get_text('btn_shop_sirpanish_himoya', fallback="⛸ Sirpanishdan himoya ({price} 💶)").replace('{price}', str(p_sirp))
    lbl_geroy = TextService.get_text('btn_shop_geroy', fallback="🥷 Shaxsiy Geroy ({price} 💎)").replace('{price}', str(p_geroy))
    lbl_geroy_h = TextService.get_text('btn_shop_geroy_himoya', fallback="🔰 Geroydan himoya ({price} 💎)").replace('{price}', str(p_geroy_h))
    lbl_act = TextService.get_text('btn_shop_active_role', fallback="🎭 Aktiv rol")
    lbl_vip = TextService.get_text('btn_shop_vip', fallback="⭐️ VIP ({price} 💎 dan)").replace('{price}', str(p_vip))
    lbl_back = TextService.get_text('btn_shop_back', fallback="🔙 Orqaga")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=lbl_him, callback_data="eco:buy:himoya"),
        InlineKeyboardButton(text=lbl_osish, callback_data="eco:buy:osish_himoya")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_huj, callback_data="eco:buy:hujjat"),
        InlineKeyboardButton(text=lbl_vak, callback_data="eco:buy:vaksina")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_dori, callback_data="eco:buy:dori_himoya"),
        InlineKeyboardButton(text=lbl_sirp, callback_data="eco:buy:sirpanish_himoya")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_geroy, callback_data="eco:menu:hero"),
        InlineKeyboardButton(text=lbl_geroy_h, callback_data="eco:buy:geroy_himoya")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_act, callback_data="eco:menu:active_role"),
        InlineKeyboardButton(text=lbl_vip, callback_data="eco:buy:vip_30")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_back, callback_data="eco:menu:profile")
    )
    return builder.as_markup()


def build_active_roles_market_keyboard() -> InlineKeyboardMarkup:
    """Builds active role purchase selection keyboard with sell option."""
    from apps.superadmin.services import SettingService, TextService
    p_don = SettingService.get_int('price_role_don', 2)
    p_kom = SettingService.get_int('price_role_komissar', 2)
    p_shif = SettingService.get_int('price_role_shifokor', 600)
    p_cit = SettingService.get_int('price_role_citizen', 100)
    p_sell = SettingService.get_int('price_sell_role', 65)

    lbl_don = TextService.get_text('btn_role_buy_don', fallback=f"Don - 💎 {p_don}").replace('{price}', str(p_don))
    lbl_kom = TextService.get_text('btn_role_buy_komissar', fallback=f"Komissar - 💎 {p_kom}").replace('{price}', str(p_kom))
    lbl_shif = TextService.get_text('btn_role_buy_shifokor', fallback=f"Shifokor - 💶 {p_shif}").replace('{price}', str(p_shif))
    lbl_cit = TextService.get_text('btn_role_buy_citizen', fallback=f"Tinch aholi - 💶 {p_cit}").replace('{price}', str(p_cit))
    lbl_sell = TextService.get_text('btn_profile_sell_roles', fallback=f"💰 Faol rolni sotish ({p_sell} 💶)").replace('{price}', str(p_sell))
    lbl_back = TextService.get_text('btn_father_back', fallback="🔙 Orqaga")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=lbl_don, callback_data="eco:buy:role_don"),
        InlineKeyboardButton(text=lbl_kom, callback_data="eco:buy:role_komissar")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_shif, callback_data="eco:buy:role_shifokor"),
        InlineKeyboardButton(text=lbl_cit, callback_data="eco:buy:role_citizen")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_sell, callback_data="eco:menu:sell_roles")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_back, callback_data="eco:menu:shop")
    )
    return builder.as_markup()


def build_sell_active_roles_keyboard() -> InlineKeyboardMarkup:
    """Builds keyboard to sell active roles for configured price."""
    from apps.superadmin.services import SettingService, TextService
    p_sell = SettingService.get_int('price_sell_role', 65)

    lbl_don = TextService.get_text('btn_role_sell_don', fallback=f"🤵🏻 Don ({p_sell} 💶)").replace('{price}', str(p_sell))
    lbl_kom = TextService.get_text('btn_role_sell_komissar', fallback=f"🕵🏻‍♂️ Komissar ({p_sell} 💶)").replace('{price}', str(p_sell))
    lbl_shif = TextService.get_text('btn_role_sell_shifokor', fallback=f"👨🏼‍⚕️ Shifokor ({p_sell} 💶)").replace('{price}', str(p_sell))
    lbl_cit = TextService.get_text('btn_role_sell_citizen', fallback=f"👨🏼 Tinch aholi ({p_sell} 💶)").replace('{price}', str(p_sell))
    lbl_back = TextService.get_text('btn_father_back', fallback="🔙 Orqaga")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=lbl_don, callback_data="eco:sell:role_don"),
        InlineKeyboardButton(text=lbl_kom, callback_data="eco:sell:role_komissar")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_shif, callback_data="eco:sell:role_shifokor"),
        InlineKeyboardButton(text=lbl_cit, callback_data="eco:sell:role_citizen")
    )
    builder.row(
        InlineKeyboardButton(text=lbl_back, callback_data="eco:menu:active_role")
    )
    return builder.as_markup()


def build_buy_diamonds_method_keyboard() -> InlineKeyboardMarkup:
    """Builds method selection keyboard for buying diamonds."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Karta orqali to'lash", url="https://t.me/ismoilo9")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Star orqali to'lash", callback_data="eco:menu:stars_packs")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="eco:menu:profile")
    )
    return builder.as_markup()


def build_buy_diamonds_stars_keyboard() -> InlineKeyboardMarkup:
    """Builds Telegram stars packs for buying diamonds."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="1💎 - 7 star", callback_data="eco:stars:1:7"),
        InlineKeyboardButton(text="10💎 - 70 star", callback_data="eco:stars:10:70")
    )
    builder.row(
        InlineKeyboardButton(text="30💎 - 200 star", callback_data="eco:stars:30:200"),
        InlineKeyboardButton(text="70💎 - 450 star", callback_data="eco:stars:70:450")
    )
    builder.row(
        InlineKeyboardButton(text="250💎 - 1500 star", callback_data="eco:stars:250:1500"),
        InlineKeyboardButton(text="1000💎 - 5500 star", callback_data="eco:stars:1000:5500")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="eco:menu:buy_dia")
    )
    return builder.as_markup()


def build_buy_dollars_keyboard() -> InlineKeyboardMarkup:
    """Builds dollar exchange menu (diamonds to dollars)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="250💶 - 1💎", callback_data="eco:ex:250:1"),
        InlineKeyboardButton(text="500💶 - 2💎", callback_data="eco:ex:500:2")
    )
    builder.row(
        InlineKeyboardButton(text="750💶 - 3💎", callback_data="eco:ex:750:3"),
        InlineKeyboardButton(text="1000💶 - 4💎", callback_data="eco:ex:1000:4")
    )
    builder.row(
        InlineKeyboardButton(text="5000💶 - 18💎", callback_data="eco:ex:5000:18"),
        InlineKeyboardButton(text="10000💶 - 30💎", callback_data="eco:ex:10000:30")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="eco:menu:profile")
    )
    return builder.as_markup()


def build_my_hero_keyboard(hero=None, recharge_cost: int = 10, tg_id: int = None) -> InlineKeyboardMarkup:
    """Builds full interactive keyboard for Mening Geroyim view."""
    from apps.superadmin.services import SettingService, TextService
    builder = InlineKeyboardBuilder()
    price_create = SettingService.get_int('price_hero_buy', 80)
    if not hero:
        lbl_create = TextService.get_text('btn_hero_create', fallback="🥷 Geroy Yaratish ({price} 💎)").replace('{price}', str(price_create))
        builder.row(
            InlineKeyboardButton(text=lbl_create, callback_data="hero:create_prompt")
        )
    else:
        recharge_amount = SettingService.get_int('hero_recharge_amount', 1)
        rename_cost = SettingService.get_int('price_hero_rename', 5)
        charge_lbl = f"+{recharge_amount}" if recharge_amount > 1 else "+1"
        lbl_recharge = TextService.get_text('btn_hero_recharge', fallback="🩸 Zaryadlash ({charge_lbl}) — {price} 💎").replace('{charge_lbl}', charge_lbl).replace('{price}', str(recharge_cost))
        lbl_rename = TextService.get_text('btn_hero_rename', fallback="✏️ Nomlash ({price} 💎)").replace('{price}', str(rename_cost))
        lbl_transfer = TextService.get_text('btn_hero_transfer', fallback="🎁 Boshqa o'yinchiga o'tkazish")
        lbl_status = TextService.get_text('btn_hero_status_on' if hero.is_active else 'btn_hero_status_off', fallback="Holat: 🟢 Faol" if hero.is_active else "Holat: 🔴 O'chirilgan")

        builder.row(
            InlineKeyboardButton(text=lbl_recharge, callback_data="hero:recharge")
        )
        builder.row(
            InlineKeyboardButton(text=lbl_status, callback_data="hero:toggle"),
            InlineKeyboardButton(text=lbl_rename, callback_data="hero:rename_prompt")
        )
        builder.row(
            InlineKeyboardButton(text=lbl_transfer, callback_data="hero:transfer_prompt")
        )

    target_tg_id = getattr(hero, 'telegram_id', None) or tg_id
    if target_tg_id:
        base_url = SettingService.get('webapp_base_url', os.environ.get('WEBAPP_BASE_URL', 'https://16-171-175-23.sslip.io')).rstrip('/')
        webapp_url = f"{base_url}/webapp/profile/?tg_id={target_tg_id}"
        lbl_webapp = TextService.get_text('btn_profile_webapp', fallback="📱 Mini Appda ochish ↗")
        builder.row(
            InlineKeyboardButton(text=lbl_webapp, web_app=WebAppInfo(url=webapp_url))
        )

    lbl_back = TextService.get_text('btn_father_back', fallback="🔙 Orqaga")
    builder.row(
        InlineKeyboardButton(text=lbl_back, callback_data="eco:menu:profile")
    )
    return builder.as_markup()


def build_star_pay_keyboard() -> InlineKeyboardMarkup:
    """Builds star payment action button."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ To'lash", url="https://t.me/ismoilo9")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="eco:menu:stars_packs")
    )
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Joker & Vaccine Keyboards
# ---------------------------------------------------------------------------

def build_joker_boxes_setup_keyboard(game_id: str, selected_boxes: list = None) -> InlineKeyboardMarkup:
    """Builds 4 boxes for Joker to plant bombs."""
    from apps.superadmin.services import TextService
    selected_boxes = selected_boxes or []
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    for num in range(1, 5):
        icon = "💣" if num in selected_boxes else "📦"
        builder.button(
            text=f"{icon} {num}-Quti",
            callback_data=f"jk_box:{gid}:{num}"
        )
    builder.adjust(2)
    lbl_send = TextService.get_text('btn_joker_send', fallback="🚀 Sovg'ani yuborish (Nishonni tanlash)")
    builder.row(
        InlineKeyboardButton(text=lbl_send, callback_data=f"jk_send:{gid}")
    )
    builder.row(
        InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"n_skip:{gid}")
    )
    return builder.as_markup()


def build_joker_guess_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Builds 4 boxes for Joker's victim to pick."""
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    for num in range(1, 5):
        builder.button(
            text=f"📦 {num}-Quti",
            callback_data=f"jk_pick:{gid}:{num}"
        )
    builder.adjust(2)
    return builder.as_markup()


def build_vaksina_prompt_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Prompts zombie-infected player whether to use Vaccine."""
    from apps.superadmin.services import TextService
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    lbl_use = TextService.get_text('btn_vaksina_use', fallback="💉 Vaksinani ishlatish")
    lbl_skip = TextService.get_text('btn_vaksina_skip', fallback="❌ Ishlatmaslik")
    builder.button(text=lbl_use, callback_data=f"vak_use:{gid}")
    builder.button(text=lbl_skip, callback_data=f"vak_skip:{gid}")
    builder.adjust(2)
    return builder.as_markup()


def build_konchi_mines_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Builds 1-10 mines selection keyboard for Konchi (Miner)."""
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    for i in range(1, 11):
        builder.button(text=f"⛏ {i}-kon", callback_data=f"kn:{gid}:{i}")
    builder.adjust(5, 5)
    builder.row(
        InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"n_skip:{gid}")
    )
    return builder.as_markup()


def build_hero_dawn_ask_keyboard(game_id: str, shooter_player_id: str) -> InlineKeyboardMarkup:
    """Builds Dawn prompt for Don/Komissar to decide whether to use their Hero."""
    from apps.superadmin.services import TextService
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    pid = _short(shooter_player_id)
    lbl_yes = TextService.get_text('btn_hero_dawn_yes', fallback="⚔️ Xa")
    lbl_no = TextService.get_text('btn_hero_dawn_no', fallback="❌ Yo'q")
    builder.row(
        InlineKeyboardButton(text=lbl_yes, callback_data=f"hero_dawn:yes:{gid}:{pid}"),
        InlineKeyboardButton(text=lbl_no, callback_data=f"hero_dawn:no:{gid}:{pid}")
    )
    return builder.as_markup()


def build_hero_dawn_targets_keyboard(game_id: str, shooter_player_id: str, living_players: list) -> InlineKeyboardMarkup:
    """Builds target selection keyboard for Hero strike at Dawn."""
    from apps.superadmin.services import TextService
    builder = InlineKeyboardBuilder()
    gid = _short(game_id)
    spid = _short(shooter_player_id)
    for p in living_players:
        if str(p.id) == str(shooter_player_id) or _short(str(p.id)) == spid:
            continue
        pid = _short(str(p.id))
        team_badge = _player_team_badge(p)
        name = p.display_name or p.username or f"O'yinchi {p.telegram_user_id}"
        builder.button(
            text=f"🎯 {team_badge}{name} ({p.health}% ❤️)",
            callback_data=f"hero_dawn:target:{gid}:{spid}:{pid}"
        )
    builder.adjust(1)
    lbl_cancel = TextService.get_text('btn_hero_cancel', fallback="⬅️ Bekor qilish")
    builder.row(
        InlineKeyboardButton(text=lbl_cancel, callback_data=f"hero_dawn:no:{gid}:{spid}")
    )
    return builder.as_markup()

