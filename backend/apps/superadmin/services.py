import os
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
import json
import logging
import requests
import urllib.request
import urllib.parse
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async

from apps.superadmin.models import BotSystemText, GameSetting, PromoCode, BroadcastMessage, AuditLog

logger = logging.getLogger(__name__)

DEFAULT_GAME_SETTINGS = [
    {
        'key': 'night_duration',
        'group': 'TIMINGS',
        'title': "Tun bosqichi davomiyligi",
        'value': '60',
        'unit': 'sekund',
        'description': "Tun bosqichida rollar o'z harakatlarini bajarishi uchun beriladigan vaqt."
    },
    {
        'key': 'voting_duration',
        'group': 'TIMINGS',
        'title': "Ovoz berish davomiyligi",
        'value': '20',
        'unit': 'sekund',
        'description': "Kunduzgi sud / ovoz berish uchun beriladigan vaqt."
    },
    {
        'key': 'dawn_wait_duration',
        'group': 'TIMINGS',
        'title': "Tonggi e'lonlarni ko'rish vaqti",
        'value': '15',
        'unit': 'sekund',
        'description': "Tong otganda natijalarni o'qish uchun kutish vaqti."
    },
    {
        'key': 'last_words_duration',
        'group': 'TIMINGS',
        'title': "So'ngi so'z aytish vaqti",
        'value': '50',
        'unit': 'sekund',
        'description': "O'ldirilgan o'yinchi bot lichkasiga so'ngi so'zini yozishi uchun beriladigan vaqt."
    },
    {
        'key': 'lobby_timeout_minutes',
        'group': 'TIMINGS',
        'title': "Lobby avto-bekor bo'lish vaqti",
        'value': '15',
        'unit': 'minut',
        'description': "Yetarlicha o'yinchi yig'ilmasa lobbini bekor qilish vaqti."
    },
    {
        'key': 'price_dori_himoya',
        'group': 'PRICES',
        'title': "💊 Doridan (Kezuvchidan) himoya narxi",
        'value': '130',
        'unit': '💶 Dollar',
        'description': "Kezuvchi dori berishidan va bloklashidan 1 marta asraydi."
    },
    {
        'key': 'price_himoya',
        'group': 'PRICES',
        'title': "🛡 Himoya qalqoni narxi",
        'value': '300',
        'unit': '💶 Dollar',
        'description': "Tungi hujumdan 1 marta asrab qoladi."
    },
    {
        'key': 'price_osish_himoya',
        'group': 'PRICES',
        'title': "⚖️ Osishdan himoya narxi",
        'value': '1',
        'unit': '💎 Olmos',
        'description': "Kunduzgi osilishdan 1 marta asraydi."
    },
    {
        'key': 'price_hujjat',
        'group': 'PRICES',
        'title': "📁 Soxta hujjat narxi",
        'value': '200',
        'unit': '💶 Dollar',
        'description': "Komissar tekshiruvida tinch fuqaro ko'rsatadi."
    },
    {
        'key': 'price_hero_buy',
        'group': 'HERO',
        'title': "🥷 Geroy sotib olish narxi",
        'value': '80',
        'unit': '💎 Olmos',
        'description': "Yangi shaxsiy Geroy yaratish / sotib olish narxi."
    },
    {
        'key': 'price_hero_recharge',
        'group': 'HERO',
        'title': "⚡️ Geroyni 1 ta zaryadlash narxi",
        'value': '1',
        'unit': '💎 Olmos',
        'description': "Geroyni 1 marta zaryadlash narxi."
    },
    {
        'key': 'hero_recharge_amount',
        'group': 'HERO',
        'title': "🔋 Har bir zaryadlashda beriladigan zaryad soni",
        'value': '1',
        'unit': 'ta zaryad',
        'description': "1 olmosga necha zaryad berilishi (Standart: +1 zaryad)."
    },
    {
        'key': 'hero_max_charges',
        'group': 'HERO',
        'title': "🔋 Geroy maksimal zaryad sig'imi",
        'value': '10',
        'unit': 'ta zaryad',
        'description': "Geroy to'play oladigan maksimal zaryadlar soni."
    },
    {
        'key': 'price_hero_rename',
        'group': 'HERO',
        'title': "✏️ Geroy nomini o'zgartirish narxi",
        'value': '5',
        'unit': '💎 Olmos',
        'description': "Mavjud Geroy nomini qayta nomlash narxi."
    },
    {
        'key': 'rank_legend_min_wins',
        'group': 'RANKS',
        'title': "🔥 'Mafiya Afsonasi' unvoni uchun minimal g'alabalar",
        'value': '50',
        'unit': "ta g'alaba",
        'description': "O'yinchiga 'Mafiya Afsonasi' (Legend) nishonini berish uchun kerakli g'alabalar soni."
    },
    {
        'key': 'rank_pro_min_wins',
        'group': 'RANKS',
        'title': "⚡️ 'PRO O'yinchi' unvoni uchun minimal g'alabalar",
        'value': '20',
        'unit': "ta g'alaba",
        'description': "O'yinchiga 'PRO O'yinchi' nishonini berish uchun kerakli g'alabalar soni."
    },
    {
        'key': 'rank_veteran_min_wins',
        'group': 'RANKS',
        'title': "🎖 'Tajribali Jangchi' unvoni uchun minimal g'alabalar",
        'value': '5',
        'unit': "ta g'alaba",
        'description': "O'yinchiga 'Tajribali Jangchi' (Veteran) nishonini berish uchun kerakli g'alabalar soni."
    },
    {
        'key': 'price_vip_30',
        'group': 'PRICES',
        'title': "👑 VIP 30 kunlik narxi",
        'value': '30',
        'unit': '💎 Olmos',
        'description': "30 kunlik VIP status va imtiyozlar."
    },
    {
        'key': 'price_role_don',
        'group': 'PRICES',
        'title': "🎭 Aktiv rol: Don narxi",
        'value': '2',
        'unit': '💎 Olmos',
        'description': "Don roli xarid qilish narxi."
    },
    {
        'key': 'price_role_komissar',
        'group': 'PRICES',
        'title': "🎭 Aktiv rol: Komissar narxi",
        'value': '2',
        'unit': '💎 Olmos',
        'description': "Komissar roli xarid qilish narxi."
    },
    {
        'key': 'price_role_shifokor',
        'group': 'PRICES',
        'title': "🎭 Aktiv rol: Shifokor narxi",
        'value': '600',
        'unit': '💶 Dollar',
        'description': "Shifokor roli xarid qilish narxi."
    },
    {
        'key': 'price_role_citizen',
        'group': 'PRICES',
        'title': "🎭 Aktiv rol: Tinch aholi narxi",
        'value': '100',
        'unit': '💶 Dollar',
        'description': "Tinch aholi roli narxi."
    },
    {
        'key': 'price_sell_role',
        'group': 'PRICES',
        'title': "💰 Faol rolni qaytarib sotish narxi",
        'value': '65',
        'unit': '💶 Dollar',
        'description': "O'yinchi o'z faol rolini sotganda oladigan dollar."
    },
    {
        'key': 'price_vaksina',
        'group': 'PRICES',
        'title': "💉 Zombi Vaksinasi narxi",
        'value': '150',
        'unit': '💶 Dollar',
        'description': "Zombi tishlaganda asil roliga qaytish uchun vaksina."
    },
    {
        'key': 'price_sirpanish_himoya',
        'group': 'PRICES',
        'title': "⛸ Sirpanishdan himoya narxi",
        'value': '150',
        'unit': '💶 Dollar',
        'description': "Kezuvchi sirpantirib yiqitishidan 1 marta asraydi."
    },
    {
        'key': 'afk_inaction_nights',
        'group': 'TIMINGS',
        'title': "⏱ AFK Harakatsizlik jazosi limiti",
        'value': '2',
        'unit': 'tun',
        'description': "Ketma-ket necha tun harakat qilmagan o'yinchi o'yindan chetlatilishi."
    },
    {
        'key': 'victory_reward_coins',
        'group': 'REWARDS',
        'title': "🏆 O'yin g'alabasida beriladigan Dollar mukofoti",
        'value': '50',
        'unit': '💶 Dollar',
        'description': "O'yinda g'alaba qozongan har bir o'yinchiga taqdim etiladigan pul (Standart: 50)."
    },
    {
        'key': 'victory_reward_diamonds',
        'group': 'REWARDS',
        'title': "💎 O'yin g'alabasida beriladigan Olmos mukofoti",
        'value': '0',
        'unit': '💎 Olmos',
        'description': "O'yinda g'alaba qozongan o'yinchiga beriladigan olmos (Standart: 0)."
    },
    {
        'key': 'participation_reward_coins',
        'group': 'REWARDS',
        'title': "🎮 O'yin ishtirokida beriladigan Dollar mukofoti",
        'value': '15',
        'unit': '💶 Dollar',
        'description': "Mag'lub bo'lgan yoki ishtirok etgan barcha o'yinchilarga beriladigan pul (Standart: 15)."
    },
    {
        'key': 'participation_reward_diamonds',
        'group': 'REWARDS',
        'title': "💎 O'yin ishtirokida beriladigan Olmos mukofoti",
        'value': '0',
        'unit': '💎 Olmos',
        'description': "Ishtirok etgan o'yinchiga beriladigan olmos (Standart: 0)."
    }
]


class SettingService:
    _cache: dict = {}
    _cache_loaded: bool = False

    @classmethod
    def reload_cache(cls):
        try:
            cls._cache = {
                item.key: item.value
                for item in GameSetting.objects.all()
            }
            cls._cache_loaded = True
        except Exception:
            pass

    @classmethod
    def seed_defaults(cls):
        for item in DEFAULT_GAME_SETTINGS:
            GameSetting.objects.get_or_create(
                key=item['key'],
                defaults={
                    'group': item['group'],
                    'title': item['title'],
                    'value': item['value'],
                    'unit': item['unit'],
                    'description': item['description'],
                }
            )
        cls.reload_cache()

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        try:
            obj = GameSetting.objects.filter(key=key).first()
            if obj and obj.value:
                return int(obj.value)
        except Exception:
            pass
        return default

    @classmethod
    def get(cls, key: str, default: str = '') -> str:
        return cls.get_str(key, default)

    @classmethod
    def set(cls, key: str, value: str):
        try:
            GameSetting.objects.update_or_create(
                key=key,
                defaults={'value': str(value)}
            )
            cls.reload_cache()
        except Exception:
            pass

    @classmethod
    def get_str(cls, key: str, default: str = '') -> str:
        try:
            obj = GameSetting.objects.filter(key=key).first()
            if obj and obj.value:
                return str(obj.value)
        except Exception:
            pass
        return default

    @classmethod
    def get_bot_timing_str(cls, bot_id: str, key: str, default: str = 'ALL') -> str:
        try:
            if bot_id:
                from apps.bots.models import Bot, BotConfiguration
                b = Bot.objects.filter(id=bot_id).first()
                if b:
                    cfg = BotConfiguration.objects.filter(bot=b).first()
                    if cfg and cfg.extra_settings and key in cfg.extra_settings:
                        return str(cfg.extra_settings[key])
        except Exception:
            pass
        return cls.get_str(key, default)

    @classmethod
    def get_group_or_bot_timing(cls, chat_id: int, bot_id: str, key: str, default: int) -> int:
        """Checks custom per-group settings first, then bot config, then global default."""
        try:
            if chat_id:
                from apps.bots.models import BotGroup
                bg = BotGroup.objects.filter(chat_id=chat_id).first()
                if bg and bg.group_settings and key in bg.group_settings:
                    return int(bg.group_settings[key])
        except Exception:
            pass
        return cls.get_bot_timing(bot_id, key, default)

    @classmethod
    def get_group_or_bot_timing_str(cls, chat_id: int, bot_id: str, key: str, default: str = 'ADMINS') -> str:
        """Checks custom per-group string settings first, then bot config, then global default."""
        try:
            if chat_id:
                from apps.bots.models import BotGroup
                bg = BotGroup.objects.filter(chat_id=chat_id).first()
                if bg and bg.group_settings and key in bg.group_settings:
                    return str(bg.group_settings[key])
        except Exception:
            pass
        return cls.get_bot_timing_str(bot_id, key, default)

    @classmethod
    def get_bot_timing(cls, bot_id: str, key: str, default: int) -> int:
        try:
            if bot_id:
                from apps.bots.models import Bot, BotConfiguration
                b = Bot.objects.filter(id=bot_id).first()
                if b:
                    cfg = BotConfiguration.objects.filter(bot=b).first()
                    if cfg:
                        if key == 'night_duration' and cfg.night_duration_seconds:
                            return int(cfg.night_duration_seconds)
                        elif key == 'voting_duration' and cfg.voting_duration_seconds:
                            return int(cfg.voting_duration_seconds)
                        elif cfg.extra_settings and key in cfg.extra_settings:
                            return int(cfg.extra_settings[key])
        except Exception:
            pass
        return cls.get_int(key, default)

    @classmethod
    def set_bot_timing(cls, bot_id: str, night_duration: int = 60, voting_duration: int = 20,
                       dawn_wait: int = 15, last_words: int = 50, lobby_timeout: int = 15,
                       night_silence_mode: str = 'DELETE_ALL', auto_pin_lobby: bool = True,
                       require_admin: bool = False, **kwargs):
        from apps.bots.models import Bot, BotConfiguration
        b = Bot.objects.filter(id=bot_id).first()
        if not b:
            return
        cfg, _ = BotConfiguration.objects.get_or_create(bot=b)
        cfg.night_duration_seconds = night_duration
        cfg.voting_duration_seconds = voting_duration
        if not cfg.extra_settings:
            cfg.extra_settings = {}
        cfg.extra_settings['dawn_wait_duration'] = dawn_wait
        cfg.extra_settings['last_words_duration'] = last_words
        cfg.extra_settings['lobby_timeout_minutes'] = lobby_timeout
        cfg.extra_settings['night_silence_mode'] = night_silence_mode
        cfg.extra_settings['auto_pin_lobby'] = auto_pin_lobby
        cfg.extra_settings['require_admin_to_play'] = require_admin
        for k, v in kwargs.items():
            cfg.extra_settings[k] = v
        cfg.save()

DEFAULT_BOT_TEXTS = [
    # DAWN (Tong & Voqealar)
    {'key': 'dawn_intro_text', 'category': 'DAWN', 'title': "Tong kirishi kirish xabari (GIF ostidagi matn)", 'content_uz': "🌅 <b>Tong otdi! Shahar uyg'ondi.</b>\nTundagi shovqinlarning sababini aniqlab tirik qolganlarni sanaymiz..."},
    {'key': 'dawn_nobody_died', 'category': 'DAWN', 'title': "Tunda hech kim o'lmaganda xabar", 'content_uz': "😴 <b>Bu tun tinch o'tdi.</b> Hech kim qurbon bo'lmadi."},
    {'key': 'dawn_doctor_saved', 'category': 'DAWN', 'title': "Shifokor qutqarganda xabar", 'content_uz': "🩺 <b>Ishonish qiyin!</b> Lekin, bu tunda hech kim o'lmadi...\nShifokor kimnidir o'limdan qutqardi!"},
    {'key': 'dawn_shield_saved', 'category': 'DAWN', 'title': "Tungi himoya qalqoni qutqarganda xabar", 'content_uz': "🛡 <b>Tunda kimdir shaxsiy himoya qalqoni tufayli o'limdan omon qoldi!</b>\nHech kim qurbon bo'lmadi."},
    {'key': 'dawn_living_players_format', 'category': 'DAWN', 'title': "Tirik o'yinchilar ro'yxati xabari", 'content_uz': "{players_list}\n\n<b>Ulardan:</b>\n{roles_list}\n\n<b>Jami:</b> {count}\n\nEndi kechaning natijalarini muhokama qilamiz...\nOvoz berishgacha ⏳ <b>20 sekund</b> qoldi"},
    {'key': 'dawn_death_mafia', 'category': 'DAWN', 'title': "Mafiya o'ldirganda e'lon", 'content_uz': "🩸 {target_name} Mafiyalar tomonidan vahshiylarcha o'ldirildi.\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_komissar', 'category': 'DAWN', 'title': "Komissar otib o'ldirganda e'lon", 'content_uz': "🔫 {target_name} Komissar tomonidan otib o'ldirildi.\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_qotil', 'category': 'DAWN', 'title': "Qotil (Maniac) o'ldirganda e'lon", 'content_uz': "🔪 {target_name} shafqatsiz Qotil tomonidan o'ldirildi.\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_tuzoq', 'category': 'DAWN', 'title': "Tuzoqchi tuzog'iga tushganda e'lon", 'content_uz': "🕸 {target_name} tuzoqqa ilinib halok bo'ldi!\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_afsungar', 'category': 'DAWN', 'title': "Afsungar la'natiga uchraganda e'lon", 'content_uz': "🧙🏼 Afsungarga hujum qilgan {target_name} o'z la'nati qurboni bo'ldi!\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_ubiytsa_retaliate', 'category': 'DAWN', 'title': "Ubiytsa Komissarga duch kelganda e'lon", 'content_uz': "🥷 Komissarga suiqasd qilmoqchi bo'lgan Ubiytsa {target_name} otib o'ldirildi!\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_kimyogar', 'category': 'DAWN', 'title': "Kimyogar zaharlaganda e'lon", 'content_uz': "🧪 {target_name} Kimyogarning zaharli eliksiridan halok bo'ldi!\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_death_axmoq', 'category': 'DAWN', 'title': "Axmoq kalla qo'yganda e'lon", 'content_uz': "🤪 {target_name} Axmoqning kalla zarbasidan halok bo'ldi!\nU: {role_icon} {role_name} edi."},
    {'key': 'dawn_don_succession', 'category': 'DAWN', 'title': "Yangi Don tayinlanganda e'lon", 'content_uz': "🤵🏻 <b>Mafialardan biri Don bo'ldi!</b>\nO'yin davom etadi..."},
    {'key': 'dawn_komissar_succession', 'category': 'DAWN', 'title': "Serjant Komissar bo'lganda e'lon", 'content_uz': "👮🏼‍♂️ <b>Serjant Komissar lavozimini egalladi!</b>"},
    {'key': 'dawn_doctor_succession', 'category': 'DAWN', 'title': "Hamshira Shifokor bo'lganda e'lon", 'content_uz': "👩🏼‍⚕️ <b>Hamshira Shifokor lavozimini egalladi!</b>"},

    # VOTING (Kun & Ovoz Berish)
    {'key': 'voting_start_announcement', 'category': 'VOTING', 'title': "Ovoz berish boshlanishi e'loni", 'content_uz': "⚖️ <b>Aybdorlarni aniqlash va jazolash vaqti keldi!</b>\n\nOvoz berish uchun <b>{duration} sekund</b> vaqtingiz bor.\nBotga o'tib, gumondor o'yinchini tanlang!"},
    {'key': 'voting_elimination_format', 'category': 'VOTING', 'title': "O'yinchi dorga osilganda e'lon", 'content_uz': "💀 {target_name} <b>dorga osildi!</b>\n\nOvoz berish: {kill_votes} 👍xa  |  {save_votes} 👎yo'q\n\n{target_name} edi: <b>{role_icon} {role_name}</b>"},
    {'key': 'voting_pardon_format', 'category': 'VOTING', 'title': "Aholi afv etganda e'lon", 'content_uz': "🕊️ <b>Aholi {target_name} ni afv etdi!</b>\n\nOvoz berish: {kill_votes} 👍xa  |  {save_votes} 👎yo'q\n\nHech kim osilmadi."},
    {'key': 'voting_shield_saved_format', 'category': 'VOTING', 'title': "Osishdan himoya ishlatilganda e'lon", 'content_uz': "⚖️ {target_name} <b>osishdan shaxsiy himoyasi evaziga dorga osilmadi va tirik qoldi!</b>\n\nOvoz berish: {kill_votes} 👍xa  |  {save_votes} 👎yo'q"},

    # NIGHT (Tun Bosqichi)
    {'key': 'night_start_announcement', 'category': 'NIGHT', 'title': "Tun boshlanishi e'loni", 'content_uz': "🌙 <b>Qorong'u va daxshatlarga to'la {round_num}-tun boshlandi.</b>\nKo'chaga yana zulmat tushdi. <b>60 sekund</b> davomida harakatlaringizni bajaring!\n\n👥 <b>Tirik o'yinchilar: ({count} ta)</b>\n{players_list}"},

    # LOBBY (Lobby & Guruh)
    {'key': 'lobby_join_text', 'category': 'LOBBY', 'title': "Guruhdagi o'yinga yig'ilish matni (/game)", 'content_uz': "<b>{bot_name}</b>               <code>BM Admin</code>\n<b>Ro'yxatdan o'tish davom etmoqda!</b>\n<b>Ro'yxatdan o'tganlar:</b>\n\n{player_names}\n\n<b>Jami: {total} ta</b>"},
    {'key': 'lobby_team_text', 'category': 'LOBBY', 'title': "Jamoaviy o'yinga yig'ilish matni (/team)", 'content_uz': "<b>{bot_name}</b>               <code>BM Admin</code>\n⚔️ <b>Jamoaviy o'yin ro'yxatdan o'tish davom etmoqda!</b>\n\n🔴 <b>Qizil jamoa ({red_count} ta):</b>\n{red_list}\n\n🔵 <b>Ko'k jamoa ({blue_count} ta):</b>\n{blue_list}\n\n<b>Jami: {total} ta</b>\n<i>Qo'shilish uchun jamoa tugmasini bosing!</i>"},

    # TRANSFERS & GIVEAWAYS (/change, /changemoney)
    {'key': 'transfer_money_format', 'category': 'TRANSFERS', 'title': "Dollar o'tkazmasi formati", 'content_uz': "{sender_name} ➔ {recipient_name}: 💶 {amount}"},
    {'key': 'transfer_diamond_format', 'category': 'TRANSFERS', 'title': "Olmos o'tkazmasi formati", 'content_uz': "{sender_name} ➔ {recipient_name}: 💎 {amount}"},
    {'key': 'transfer_money_usage', 'category': 'TRANSFERS', 'title': "Dollar o'tkazish qo'llanmasi (reply)", 'content_uz': "ℹ️ O'tkazmoqchi bo'lgan o'yinchining xabariga reply qilib <code>/money &lt;summa&gt;</code> yozing."},
    {'key': 'transfer_diamond_usage', 'category': 'TRANSFERS', 'title': "Olmos o'tkazish qo'llanmasi (reply)", 'content_uz': "ℹ️ O'tkazmoqchi bo'lgan o'yinchining xabariga reply qilib <code>/give &lt;olmos_soni&gt;</code> yozing."},
    {'key': 'transfer_insufficient_funds', 'category': 'TRANSFERS', 'title': "Mablag' yetarli emas xabari", 'content_uz': "❌ Hisobingizda mablag' yetarli emas."},
    {'key': 'transfer_self_error', 'category': 'TRANSFERS', 'title': "O'ziga o'tkazish taqiqi xabari", 'content_uz': "❌ O'z-o'zingizga o'tkaza olmaysiz."},
    {'key': 'transfer_invalid_amount', 'category': 'TRANSFERS', 'title': "Noto'g'ri summa xabari", 'content_uz': "❌ Noto'g'ri summa kiritildi."},
    {'key': 'giveaway_drop_msg', 'category': 'TRANSFERS', 'title': "Guruhga ulashuv xabari (/change, /changemoney)", 'content_uz': "🎁 {sender_mention} guruhga <b>{total} {curr_icon} {curr_label}</b> ulashdi!\n\nℹ️ <i>Har bir o'yinchi 1 donadan olishi mumkin!</i>\n\n{status_line}"},

    # GIF ANIMATSIYALARI
    {'key': 'gif_dawn', 'category': 'GIFS', 'title': "Tong animatsiyasi (GIF / URL / Telegram file_id)", 'content_uz': "https://i.gifer.com/1pb4.gif"},
    {'key': 'gif_night', 'category': 'GIFS', 'title': "Tun animatsiyasi (GIF / URL / Telegram file_id)", 'content_uz': "https://media.giphy.com/media/26hirEPeos6yugLDO/giphy.gif"},
    {'key': 'gif_victory', 'category': 'GIFS', 'title': "G'alaba animatsiyasi (GIF / URL / Telegram file_id)", 'content_uz': "https://i.gifer.com/38jO.gif"},
    {'key': 'gif_lobby', 'category': 'GIFS', 'title': "Lobby animatsiyasi (GIF / URL / Telegram file_id)", 'content_uz': "https://i.gifer.com/JGSn.gif"},

    # GENERAL & ROLES
    {'key': 'roles_guide_text', 'category': 'GENERAL', 'title': "Rollar to'liq qo'llanmasi (/roles)", 'content_uz': ""},

    # PARA & JUFTLIK
    {'key': 'para_proposal_text', 'category': 'GENERAL', 'title': "Para taklifi xabari", 'content_uz': "💍 {sender_name} sizga para bo'lish taklifini yubordi!\n\n{recipient_name}, para bo'lasizmi?"},
    {'key': 'para_success_text', 'category': 'GENERAL', 'title': "Para bo'lganda tabrik xabari", 'content_uz': "💑 <b>Tabriklaymiz!</b>\n{sender_name} va {recipient_name} endi rasman para bo'lishdi! 💍❤️"},
    {'key': 'para_rejected_text', 'category': 'GENERAL', 'title': "Para taklifi rad etilganda xabar", 'content_uz': "💔 {recipient_name} {sender_name} ning para taklifini rad etdi."},
    {'key': 'para_divorce_text', 'category': 'GENERAL', 'title': "Ajrashganda (/dpara) xabar", 'content_uz': "💔 {user_name} va {partner_name} endi para emaslar. Ular ajrashishdi!"},
    {'key': 'para_mypara_text', 'category': 'GENERAL', 'title': "Mening param (/mypara) xabari", 'content_uz': "💍 Sizning parangiz: {partner_name} ❤️"},
    {'key': 'para_no_partner_text', 'category': 'GENERAL', 'title': "Para yo'q bo'lganda xabar", 'content_uz': "💔 Sizda hozircha para yo'q.\nBiror foydalanuvchining xabariga reply qilib <code>/para</code> deb yozing!"},

    # PROFILE (Profil & Balans)
    {'key': 'profile_custom_card_format', 'category': 'PROFILE', 'title': "Foydalanuvchi profili matni formati (/profile)", 'content_uz': "👤 {name}\n\n💵 Dollar: {dollars}\n💎 Olmos: {diamonds}\n\n🛡️ Himoya: {himoya}\n📁 Hujjat: {hujjat}\n⚖️ Osishdan himoya: {osish_himoya}\n🔰 Geroydan himoya: {geroy_himoya}\n💉 Vaksina: {vaksina}\n💊 Doridan himoya: {dori_himoya}\n⛸ Sirpanishdan himoya: {sirpanish_himoya}\n\n🥷 Geroy: {hero_info}\n\n🎯 G'alaba: {wins}\n🎲 Barcha o'yinlar: {games}\n\n💍 Parangiz: {partner_info}\n🃏 Faol rollar: {active_role}"},
    {'key': 'profile_channel_bonus_note', 'category': 'PROFILE', 'title': "Profil ostidagi 2x kanalga obuna bo'lish taklifi", 'content_uz': "kanalga qo'shilsangiz hisobingiz 2x bo'ladi: https://t.me/MafiaBotFather"},
    {'key': 'game_finish_payout_winner_format', 'category': 'PROFILE', 'title': "O'yin yakunlanganda g'olib o'yinchi PM sarlavhasi", 'content_uz': "🎉 <b>O'yin yakunlandi! Siz {place_info}-o'rin bilan g'alaba qozondingiz!</b> 🥳\n🎁 <b>G'alaba mukofoti:</b> <code>{reward_str}</code> hisobingizga qo'shildi!\n\n"},
    {'key': 'game_finish_payout_loser_format', 'category': 'PROFILE', 'title': "O'yin yakunlanganda mag'lub o'yinchi PM sarlavhasi", 'content_uz': "💀 <b>O'yin yakunlandi! Siz mag'lub bo'ldingiz.</b>\n🎁 <b>Ishtirok mukofoti:</b> <code>+{reward_coins} 💶</code> hisobingizga qo'shildi!\n\n"},

    # LOBBY (Qo'shimcha)
    {'key': 'lobby_timeout_text', 'category': 'LOBBY', 'title': "Lobby vaqti tugaganda bekor bo'lish xabari", 'content_uz': "⚠️ <b>Vaqt cho'zilib ketdi!</b>\n<b>{minutes} daqiqa</b> ichida o'yin boshlanmaganligi sababli ro'yxatdan o'tish bekor qilindi.\n\nYangi o'yin boshlash uchun <code>/game</code> buyrug'ini yuboring."},

    # FATHER BOT BUTTONS
    {'key': 'btn_father_create_bot', 'category': 'FATHER_BUTTONS', 'title': "Father Bot: 'Bot yaratish' tugmasi", 'content_uz': "➕ Bot yaratish"},
    {'key': 'btn_father_my_bots', 'category': 'FATHER_BUTTONS', 'title': "Father Bot: 'Mening botlarim' tugmasi", 'content_uz': "🤖 Mening botlarim"},
    {'key': 'btn_father_pay', 'category': 'FATHER_BUTTONS', 'title': "Father Bot: 'Botga to'lov qilish' tugmasi", 'content_uz': "💳 Botga to'lov qilish"},
    {'key': 'btn_father_lang', 'category': 'FATHER_BUTTONS', 'title': "Father Bot: 'Tilni tanlash' tugmasi", 'content_uz': "🌐 Tilni tanlash"},
    {'key': 'btn_father_about', 'category': 'FATHER_BUTTONS', 'title': "Father Bot: 'Bot haqida' tugmasi", 'content_uz': "ℹ️ Bot haqida / Qo'llanma"},
    {'key': 'btn_father_back', 'category': 'FATHER_BUTTONS', 'title': "Father Bot: 'Orqaga' tugmasi", 'content_uz': "🔙 Orqaga"},

    # CHILD GAME BOT BUTTONS
    {'key': 'btn_join_game', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'Qo'shilish' tugmasi", 'content_uz': "➕ Qo'shilish"},
    {'key': 'btn_team_red', 'category': 'CHILD_BUTTONS', 'title': "Jamoaviy Lobby: 'Qizil jamoa' tugmasi", 'content_uz': "🔴 Qizil jamoa ({count})"},
    {'key': 'btn_team_blue', 'category': 'CHILD_BUTTONS', 'title': "Jamoaviy Lobby: 'Ko'k jamoa' tugmasi", 'content_uz': "🔵 Ko'k jamoa ({count})"},
    {'key': 'btn_start_game', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'O'yinni boshlash' tugmasi", 'content_uz': "▶️ O'yinni boshlash"},
    {'key': 'btn_leave_game', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'Chiqish' tugmasi", 'content_uz': "🚪 Chiqish"},
    {'key': 'btn_child_add_group', 'category': 'CHILD_BUTTONS', 'title': "Child Bot PM: 'Guruhga qo'shish' tugmasi", 'content_uz': "➕ O'yinni guruhingizga qo'shing ↗"},
    {'key': 'btn_child_lang', 'category': 'CHILD_BUTTONS', 'title': "Child Bot PM: 'Til' tugmasi", 'content_uz': "🌐 Til"},
    {'key': 'btn_child_news', 'category': 'CHILD_BUTTONS', 'title': "Child Bot PM: 'Yangiliklar' tugmasi", 'content_uz': "📢 Yangiliklar ↗"},
    {'key': 'btn_child_rules', 'category': 'CHILD_BUTTONS', 'title': "Child Bot PM: 'Qoidalar' tugmasi", 'content_uz': "🃏 Qoidalar"},
    {'key': 'btn_profile_market', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'Do'kon' tugmasi", 'content_uz': "🛒 Do'kon"},
    {'key': 'btn_profile_buy_money', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'Dollar xarid qilish' tugmasi", 'content_uz': "💶 Xarid qilish"},
    {'key': 'btn_profile_buy_diamonds', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'Olmos xarid qilish' tugmasi", 'content_uz': "💎 Olmos xarid qilish"},
    {'key': 'btn_profile_rules', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'O'yin qoidalari' tugmasi", 'content_uz': "📜 O'yin qoidalari"},
    {'key': 'btn_profile_leaderboard', 'category': 'CHILD_BUTTONS', 'title': "O'yin Boti: 'Top o'yinchilar' tugmasi", 'content_uz': "🏆 Top o'yinchilar"},
    {'key': 'btn_profile_webapp', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Mini Appda ochish' tugmasi", 'content_uz': "📱 Mini Appda ochish ↗"},

    # DO'KON (SHOP) BUTTONS
    {'key': 'btn_shop_himoya', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Himoya' xarid tugmasi", 'content_uz': "🛡 Himoya ({price} 💶)"},
    {'key': 'btn_shop_osish_himoya', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Ovozdan himoya' xarid tugmasi", 'content_uz': "⚖️ Ovozdan himoya ({price} 💎)"},
    {'key': 'btn_shop_hujjat', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Hujjatlar' xarid tugmasi", 'content_uz': "📁 Hujjatlar ({price} 💶)"},
    {'key': 'btn_shop_vaksina', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Zombi Vaksinasi' xarid tugmasi", 'content_uz': "💉 Zombi Vaksinasi ({price} 💶)"},
    {'key': 'btn_shop_dori_himoya', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Doridan himoya' xarid tugmasi", 'content_uz': "💊 Doridan himoya ({price} 💶)"},
    {'key': 'btn_shop_sirpanish_himoya', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Sirpanishdan himoya' xarid tugmasi", 'content_uz': "⛸ Sirpanishdan himoya ({price} 💶)"},
    {'key': 'btn_shop_geroy', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Geroy' tugmasi", 'content_uz': "🥷 Shaxsiy Geroy ({price} 💎)"},
    {'key': 'btn_shop_geroy_himoya', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Geroydan himoya' tugmasi", 'content_uz': "🔰 Geroydan himoya ({price} 💎)"},

    {'key': 'btn_shop_active_role', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Aktiv rol' menyu tugmasi", 'content_uz': "🎭 Aktiv rol"},
    {'key': 'btn_shop_vip', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'VIP' xarid tugmasi", 'content_uz': "⭐️ VIP ({price} 💎 dan)"},
    {'key': 'btn_shop_back', 'category': 'CHILD_BUTTONS', 'title': "Do'kon: 'Orqaga' tugmasi", 'content_uz': "🔙 Orqaga"},

    # PROFIL (/profile) TOGGLE VA MENYU BUTTONS
    {'key': 'btn_profile_himoya_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Himoya YOQILGAN' tugmasi", 'content_uz': "🛡 - 🟢 ON"},
    {'key': 'btn_profile_himoya_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Himoya O'CHIRILGAN' tugmasi", 'content_uz': "🛡 - 🔴 OFF"},
    {'key': 'btn_profile_osish_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Ovozdan himoya YOQILGAN' tugmasi", 'content_uz': "⚖️ - 🟢 ON"},
    {'key': 'btn_profile_osish_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Ovozdan himoya O'CHIRILGAN' tugmasi", 'content_uz': "⚖️ - 🔴 OFF"},
    {'key': 'btn_profile_hujjat_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Hujjat YOQILGAN' tugmasi", 'content_uz': "📁 - 🟢 ON"},
    {'key': 'btn_profile_hujjat_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Hujjat O'CHIRILGAN' tugmasi", 'content_uz': "📁 - 🔴 OFF"},
    {'key': 'btn_profile_geroy_h_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Geroydan himoya YOQILGAN' tugmasi", 'content_uz': "🔰 - 🟢 ON"},
    {'key': 'btn_profile_geroy_h_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Geroydan himoya O'CHIRILGAN' tugmasi", 'content_uz': "🔰 - 🔴 OFF"},
    {'key': 'btn_profile_vaksina_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Vaksina YOQILGAN' tugmasi", 'content_uz': "💉 - 🟢 ON"},
    {'key': 'btn_profile_vaksina_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Vaksina O'CHIRILGAN' tugmasi", 'content_uz': "💉 - 🔴 OFF"},
    {'key': 'btn_profile_dori_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Doridan himoya YOQILGAN' tugmasi", 'content_uz': "💊 - 🟢 ON"},
    {'key': 'btn_profile_dori_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Doridan himoya O'CHIRILGAN' tugmasi", 'content_uz': "💊 - 🔴 OFF"},
    {'key': 'btn_profile_sirpanish_on', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Sirpanishdan himoya YOQILGAN' tugmasi", 'content_uz': "⛸ - 🟢 ON"},
    {'key': 'btn_profile_sirpanish_off', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Sirpanishdan himoya O'CHIRILGAN' tugmasi", 'content_uz': "⛸ - 🔴 OFF"},
    {'key': 'btn_profile_mypara', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Mening Param' tugmasi", 'content_uz': "💍 Mening Param"},
    {'key': 'btn_profile_shop', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Do'kon' ochish tugmasi", 'content_uz': "🎒 Do'kon"},
    {'key': 'btn_profile_buy_dia', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Olmos Xarid qilish' tugmasi", 'content_uz': "💎 Xarid qilish"},
    {'key': 'btn_profile_buy_money', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Dollar Xarid qilish' tugmasi", 'content_uz': "💶 Xarid qilish"},
    {'key': 'btn_profile_hero', 'category': 'CHILD_BUTTONS', 'title': "Profil: 'Mening Geroyim' tugmasi", 'content_uz': "🥷 Mening Geroyim"},

    # HERO MANAGE BUTTONS (Mening Geroyim)
    {'key': 'btn_hero_create', 'category': 'CHILD_BUTTONS', 'title': "Mening Geroyim: 'Geroy Yaratish' tugmasi", 'content_uz': "🥷 Geroy Yaratish ({price} 💎)"},
    {'key': 'btn_hero_recharge', 'category': 'CHILD_BUTTONS', 'title': "Mening Geroyim: 'Zaryadlash' tugmasi", 'content_uz': "🩸 Zaryadlash ({charge_lbl}) — {price} 💎"},
    {'key': 'btn_hero_rename', 'category': 'CHILD_BUTTONS', 'title': "Mening Geroyim: 'Nomlash' tugmasi", 'content_uz': "✏️ Nomlash ({price} 💎)"},
    {'key': 'btn_hero_transfer', 'category': 'CHILD_BUTTONS', 'title': "Mening Geroyim: 'Boshqa o'yinchiga o'tkazish' tugmasi", 'content_uz': "🎁 Boshqa o'yinchiga o'tkazish"},
    {'key': 'btn_hero_status_on', 'category': 'CHILD_BUTTONS', 'title': "Mening Geroyim: 'Holat Faol' tugmasi", 'content_uz': "Holat: 🟢 Faol"},
    {'key': 'btn_hero_status_off', 'category': 'CHILD_BUTTONS', 'title': "Mening Geroyim: 'Holat O'chirilgan' tugmasi", 'content_uz': "Holat: 🔴 O'chirilgan"},

    # AKTIV ROLLAR DO'KONI VA SOTISH BUTTONS
    {'key': 'btn_role_buy_don', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Don sotib olish' tugmasi", 'content_uz': "Don - 💎 {price}"},
    {'key': 'btn_role_buy_komissar', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Komissar sotib olish' tugmasi", 'content_uz': "Komissar - 💎 {price}"},
    {'key': 'btn_role_buy_shifokor', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Shifokor sotib olish' tugmasi", 'content_uz': "Shifokor - 💶 {price}"},
    {'key': 'btn_role_buy_citizen', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Tinch aholi sotib olish' tugmasi", 'content_uz': "Tinch aholi - 💶 {price}"},
    {'key': 'btn_profile_sell_roles', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Faol rolni sotish' menyu tugmasi", 'content_uz': "💰 Faol rolni sotish ({price} 💶)"},
    {'key': 'btn_role_sell_don', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Don rolini sotish' tugmasi", 'content_uz': "🤵🏻 Don ({price} 💶)"},
    {'key': 'btn_role_sell_komissar', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Komissar rolini sotish' tugmasi", 'content_uz': "🕵🏻‍♂️ Komissar ({price} 💶)"},
    {'key': 'btn_role_sell_shifokor', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Shifokor rolini sotish' tugmasi", 'content_uz': "👨🏼‍⚕️ Shifokor ({price} 💶)"},
    {'key': 'btn_role_sell_citizen', 'category': 'CHILD_BUTTONS', 'title': "Aktiv Rol: 'Tinch aholi rolini sotish' tugmasi", 'content_uz': "👨🏼 Tinch aholi ({price} 💶)"},

    # HERO & GEROY ZARBALARI
    {'key': 'hero_group_strike_hit', 'category': 'HERO', 'title': "Geroy zarbasi guruhga (Omon qolganda)", 'content_uz': "💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga {damage}% shikast yetkazdi!\n🩸 <b>{target_name}</b> ning qolgan joni: <b>{remaining_hp}% ❤️</b>"},
    {'key': 'hero_group_strike_kill_part1', 'category': 'HERO', 'title': "Geroy zarbasi guruhga (O'ldirganda 1-xabar)", 'content_uz': "💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga {damage}% shikast yetkazdi!"},
    {'key': 'hero_group_strike_kill_part2', 'category': 'HERO', 'title': "Geroy zarbasi guruhga (O'ldirganda 2-xabar)", 'content_uz': "☠️ <b>{target_name}</b> Geroy tomonidan o'ldirildi! (U: {role_icon} <b>{role_name}</b> edi)"},
    {'key': 'hero_group_strike_blocked', 'category': 'HERO', 'title': "Geroy zarbasi guruhga (Himoya qaytarganda)", 'content_uz': "💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga zarba berdi!\n\n🔰 <b>{target_name}</b> ning <b>Geroydan Himoyasi</b> zarbani to'liq qaytardi va uning hayotini saqlab qoldi!"},

    # NIGHT & MAFIA CHAT / VOTE RELAYS
    {'key': 'night_mafia_vote_relay', 'category': 'NIGHT', 'title': "Mafiya sheriklariga nishon tanlanganda xabar", 'content_uz': "🤵🏼 <b>[MAFIYA OV]</b> <b>{actor_name}</b> ({actor_role}) quyidagi o'yinchini nishonga oldi:\n🎯 <b>{target_name}</b>"},
    {'key': 'night_mafia_chat_relay', 'category': 'NIGHT', 'title': "Mafiya tunda o'zaro yozishganda format", 'content_uz': "💬 <b>[MAFIYA CHAT]</b> {role_icon} <b>{sender_name} ({role_label}):</b>\n{text}"},
    {'key': 'night_police_chat_relay', 'category': 'NIGHT', 'title': "Politsiya tunda o'zaro yozishganda format", 'content_uz': "💬 <b>[POLITSIYA CHAT]</b> {role_icon} <b>{sender_name} ({role_label}):</b>\n{text}"},

    # LOBBY GREETINGS & NOTIFICATIONS
    {'key': 'lobby_pm_start_greeting', 'category': 'LOBBY', 'title': "Bot PM /start salomlashish xabari", 'content_uz': "Salom, <b>{first_name}</b>! 🎭\n\nMen <b>Mafia Bot</b>man. Men guruhlarda do'stlaringiz bilan birga afsonaviy Mafiya o'yinini o'ynash uchun xizmat qilaman!\n\nGuruhda yangi o'yin ochish uchun <code>/game</code> buyrug'ini yuboring.\n\n💬 <i>Savol va takliflaringiz bo'lsa @ismoilo9 ga murojaat qiling.</i>"},
    {'key': 'lobby_game_started_text', 'category': 'LOBBY', 'title': "O'yin boshlanganda guruh xabari", 'content_uz': "🎮 <b>O'yin boshlandi!</b>\n\nRollar taqsimlanmoqda... Botga o'tib rolingizni ko'ring!"},

    # HARAKAT VA O'YIN ICHIDAGI BUTTONS
    {'key': 'btn_action_hang', 'category': 'ACTION_BUTTONS', 'title': "Ovoz berish: '👍 Xa (O'ldirish)' tugmasi", 'content_uz': "👍 Xa (O'ldirish)"},
    {'key': 'btn_action_save', 'category': 'ACTION_BUTTONS', 'title': "Ovoz berish: '👎 Yo'q (Afv etish)' tugmasi", 'content_uz': "👎 Yo'q (Afv etish)"},
    {'key': 'btn_hanging_kill', 'category': 'ACTION_BUTTONS', 'title': "Dorga osish: '👍 {count}' tugmasi", 'content_uz': "👍 {count}"},
    {'key': 'btn_hanging_save', 'category': 'ACTION_BUTTONS', 'title': "Dorga osish: '👎 {count}' tugmasi", 'content_uz': "👎 {count}"},
    {'key': 'btn_action_investigate', 'category': 'ACTION_BUTTONS', 'title': "Komissar: '🔍 Tekshirish' tugmasi", 'content_uz': "🔍 Tekshirish"},
    {'key': 'btn_action_shoot', 'category': 'ACTION_BUTTONS', 'title': "Komissar: '🔫 Otish' tugmasi", 'content_uz': "🔫 Otish"},
    {'key': 'btn_bot_pm', 'category': 'ACTION_BUTTONS', 'title': "Xabarlar: 'Botga o'tish ↗' tugmasi", 'content_uz': "Botga o'tish ↗"},
    {'key': 'btn_back_group', 'category': 'ACTION_BUTTONS', 'title': "Xabarlar: 'Guruhga o'tish ↗' tugmasi", 'content_uz': "Guruhga o'tish ↗"},
    {'key': 'btn_force_cancel', 'category': 'ACTION_BUTTONS', 'title': "O'yin: '🛑 O'yinni to'xtatish va yangi ochish' tugmasi", 'content_uz': "🛑 O'yinni to'xtatish va yangi ochish"},
    {'key': 'btn_giveaway_claim', 'category': 'ACTION_BUTTONS', 'title': "Ulashuv: 'Olish' tugmasi", 'content_uz': "{curr_icon} {curr_label} olish ({remaining}/{total})"},
    {'key': 'btn_giveaway_finished', 'category': 'ACTION_BUTTONS', 'title': "Ulashuv: 'Barchasi olindi' tugmasi", 'content_uz': "✅ Barchasi olindi! (0/{total})"},
    {'key': 'btn_hero_dawn_yes', 'category': 'ACTION_BUTTONS', 'title': "Tonggi Geroy Zarbasi: 'Xa' tugmasi", 'content_uz': "⚔️ Xa"},
    {'key': 'btn_hero_dawn_no', 'category': 'ACTION_BUTTONS', 'title': "Tonggi Geroy Zarbasi: 'Yo'q' tugmasi", 'content_uz': "❌ Yo'q"},
    {'key': 'btn_hero_cancel', 'category': 'ACTION_BUTTONS', 'title': "Tonggi Geroy Zarbasi: 'Bekor qilish' tugmasi", 'content_uz': "⬅️ Bekor qilish"},
    {'key': 'btn_joker_send', 'category': 'ACTION_BUTTONS', 'title': "Joker: 'Sovg'ani yuborish' tugmasi", 'content_uz': "🚀 Sovg'ani yuborish (Nishonni tanlash)"},
    {'key': 'btn_vaksina_use', 'category': 'ACTION_BUTTONS', 'title': "Vaksina: 'Ishlatish' tugmasi", 'content_uz': "💉 Vaksinani ishlatish"},
    {'key': 'btn_vaksina_skip', 'category': 'ACTION_BUTTONS', 'title': "Vaksina: 'Ishlatmaslik' tugmasi", 'content_uz': "❌ Ishlatmaslik"},
]


class TextService:
    _cache: dict = {}
    _cache_loaded: bool = False

    @classmethod
    def reload_cache(cls):
        try:
            cls._cache = {
                item.key: item.content_uz
                for item in BotSystemText.objects.filter(is_active=True)
            }
            cls._cache_loaded = True
        except Exception:
            pass

    @classmethod
    def seed_defaults(cls):
        for item in DEFAULT_BOT_TEXTS:
            BotSystemText.objects.get_or_create(
                key=item['key'],
                defaults={
                    'category': item['category'],
                    'title': item['title'],
                    'content_uz': item['content_uz'],
                    'is_active': True
                }
            )
        cls.reload_cache()

    @classmethod
    def get_text(cls, key: str, lang: str = 'uz', fallback: str = '') -> str:
        try:
            obj = BotSystemText.objects.filter(key=key, is_active=True).first()
            if obj and obj.content_uz is not None and obj.content_uz != '':
                return obj.content_uz
        except Exception as e:
            logger.debug(f"Error fetching live text {key}: {e}")
        return fallback

    @classmethod
    async def get_text_async(cls, key: str, lang: str = 'uz', fallback: str = '') -> str:
        return cls.get_text(key, lang, fallback)


class PlayerInventoryService:
    @classmethod
    def get_full_inventory(cls, telegram_id: int) -> dict:
        from apps.economy.models import Inventory
        invs = Inventory.objects.filter(telegram_id=telegram_id).select_related('item')
        data = {
            'himoya': 0,
            'osish_himoya': 0,
            'hujjat': 0,
            'geroy_himoya': 0,
            'vaksina': 0,
            'dori_himoya': 0,
            'sirpanish_himoya': 0,
            'geroy': 0,
            'active_role': '',
        }
        for inv in invs:
            code = inv.item.code if inv.item else ''
            if code in data:
                data[code] = inv.quantity
            elif code.startswith('role_') and inv.quantity > 0:
                data['active_role'] = code
        return data

    @classmethod
    def set_full_inventory(cls, telegram_id: int, himoya: int = 0, osish_himoya: int = 0,
                           hujjat: int = 0, geroy_himoya: int = 0, vaksina: int = 0,
                           dori_himoya: int = 0, sirpanish_himoya: int = 0,
                           geroy: int = 0, active_role: str = ''):
        from apps.economy.models import Inventory, MarketplaceItem, MarketplaceCategory, MarketplaceItemType
        cat, _ = MarketplaceCategory.objects.get_or_create(code='game_items', defaults={'name': "O'yin buyumlari"})

        items_map = {
            'himoya': ("🛡 Himoya", himoya),
            'osish_himoya': ("⚖️ Osishdan himoya", osish_himoya),
            'hujjat': ("📁 Soxta hujjat", hujjat),
            'geroy_himoya': ("🔰 Geroydan himoya", geroy_himoya),
            'vaksina': ("💉 Zombi Vaksinasi", vaksina),
            'dori_himoya': ("💊 Doridan himoya", dori_himoya),
            'sirpanish_himoya': ("⛸ Sirpanishdan himoya", sirpanish_himoya),
            'geroy': ("🥷 Geroy", geroy),
        }
        for code, (name, qty) in items_map.items():
            item, _ = MarketplaceItem.objects.get_or_create(
                code=code,
                defaults={'name': name, 'category': cat, 'item_type': MarketplaceItemType.BONUS}
            )
            inv, created = Inventory.objects.get_or_create(telegram_id=telegram_id, item=item, defaults={'quantity': 0, 'is_active': True})
            inv.quantity = max(0, qty)
            if created:
                inv.is_active = True
            inv.save()

        roles = ['role_don', 'role_komissar', 'role_shifokor', 'role_citizen']
        for rcode in roles:
            item, _ = MarketplaceItem.objects.get_or_create(
                code=rcode,
                defaults={'name': rcode, 'category': cat, 'item_type': MarketplaceItemType.ROLE}
            )
            inv, _ = Inventory.objects.get_or_create(telegram_id=telegram_id, item=item, defaults={'quantity': 0})
            if active_role == rcode:
                inv.quantity = 1
                inv.is_active = True
            else:
                inv.quantity = 0
                inv.is_active = False
            inv.save()


class PromoCodeService:
    @classmethod
    def redeem(cls, telegram_id: int, code_str: str) -> tuple[bool, str]:
        from apps.economy.models import Wallet, VIPSubscription, VIPLevel
        code_clean = code_str.strip().upper()
        promo = PromoCode.objects.filter(code__iexact=code_clean, is_active=True).first()
        if not promo:
            return False, "❌ Promokod topilmadi yoki muddati tugagan!"

        if promo.expires_at and promo.expires_at < timezone.now():
            return False, "❌ Promokodning amal qilish muddati tugagan!"

        if promo.used_count >= promo.max_uses:
            return False, "❌ Promokoddan foydalanishlar soni tugagan!"

        used_by = list(promo.used_by or [])
        if telegram_id in used_by:
            return False, "⚠️ Siz bu promokoddan allaqachon foydalangansiz!"

        wallet, _ = Wallet.objects.get_or_create(telegram_id=telegram_id)

        if promo.reward_type == 'COINS':
            wallet.coins += promo.reward_amount
            wallet.save(update_fields=['coins'])
            msg = f"🎉 Tabriklaymiz! Sizga {promo.reward_amount} 💶 Dollar taqdim etildi!"
        elif promo.reward_type == 'DIAMONDS':
            wallet.diamonds += promo.reward_amount
            wallet.save(update_fields=['diamonds'])
            msg = f"🎉 Tabriklaymiz! Sizga {promo.reward_amount} 💎 Olmos taqdim etildi!"
        elif promo.reward_type == 'VIP_DAYS':
            now = timezone.now()
            vip, _ = VIPSubscription.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    'vip_level': VIPLevel.GOLD,
                    'starts_at': now,
                    'expires_at': now + timedelta(days=promo.reward_amount),
                    'is_active': True,
                }
            )
            if vip.expires_at and vip.expires_at > now:
                vip.expires_at += timedelta(days=promo.reward_amount)
            else:
                vip.starts_at = now
                vip.expires_at = now + timedelta(days=promo.reward_amount)
            vip.is_active = True
            vip.save()
            msg = f"🎉 Tabriklaymiz! Sizga {promo.reward_amount} kunlik 👑 VIP status berildi!"
        elif promo.reward_type in ['HIMOYA', 'OSISH_HIMOYA', 'HUJJAT', 'GEROY_HIMOYA', 'GEROY']:
            item_key = promo.reward_type.lower()
            current_inv = PlayerInventoryService.get_full_inventory(telegram_id)
            new_qty = current_inv.get(item_key, 0) + promo.reward_amount
            kwargs = {item_key: new_qty}
            PlayerInventoryService.set_full_inventory(telegram_id, **kwargs)
            msg = f"🎉 Tabriklaymiz! Sizga {promo.reward_amount} ta {promo.get_reward_type_display()} taqdim etildi!"
        elif promo.reward_type in ['ROLE_DON', 'ROLE_KOMISSAR', 'ROLE_SHIFOKOR', 'ROLE_CITIZEN']:
            role_code = promo.reward_type.lower()
            PlayerInventoryService.set_full_inventory(telegram_id, active_role=role_code)
            msg = f"🎉 Tabriklaymiz! Sizga {promo.get_reward_type_display()} faollashtirildi!"
        else:
            msg = "✅ Promokod muvaffaqiyatli faollashtirildi!"

        used_by.append(telegram_id)
        promo.used_by = used_by
        promo.used_count += 1
        if promo.used_count >= promo.max_uses:
            promo.is_active = False
        promo.save(update_fields=['used_by', 'used_count', 'is_active'])

        AuditLog.log(action="PROMO_REDEEMED", actor=f"TG:{telegram_id}", target=promo.code, details=msg)
        return True, msg


class BroadcastService:
    @classmethod
    def execute_broadcast(cls, broadcast_id) -> bool:
        """
        Processes and sends broadcast message asynchronously.
        Accepts either broadcast UUID/str or BroadcastMessage model instance.
        """
        if isinstance(broadcast_id, BroadcastMessage):
            broadcast = broadcast_id
            broadcast_id = str(broadcast.id)
        else:
            broadcast = BroadcastMessage.objects.filter(id=broadcast_id).first()
        if not broadcast:
            return False

        broadcast.status = 'IN_PROGRESS'
        broadcast.save(update_fields=['status'])

        import os
        import time
        import requests
        from django.conf import settings
        from apps.stats.models import PlayerProfile
        from apps.bots.models import Bot as BotModel, BotCredential
        from apps.superadmin.models import AuditLog

        reply_markup = None
        if broadcast.button_text and broadcast.button_url:
            reply_markup = {
                'inline_keyboard': [[
                    {'text': broadcast.button_text, 'url': broadcast.button_url}
                ]]
            }

        success = 0
        failed = 0

        from apps.superadmin.models import UserNotification
        from apps.bots.models import BotUser, BotGroup
        from apps.games.models import Player
        from apps.users.models import User
        from django.db.models import Q

        def _send_tg(token: str, chat_id) -> bool:
            try:
                import json
                is_local_file = False
                if broadcast.photo_url and os.path.exists(broadcast.photo_url):
                    is_local_file = True

                if is_local_file:
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    data = {'chat_id': chat_id, 'caption': broadcast.content, 'parse_mode': 'HTML'}
                    if reply_markup:
                        data['reply_markup'] = json.dumps(reply_markup)
                    with open(broadcast.photo_url, 'rb') as f:
                        resp = requests.post(url, data=data, files={'photo': f}, timeout=15)
                    if resp.status_code == 200 and resp.json().get('ok'):
                        return True
                    # If HTML parsing failed, retry plain text
                    err_desc = str(resp.json().get('description', '')).lower()
                    if 'entity' in err_desc or "can't parse" in err_desc:
                        data = {'chat_id': chat_id, 'caption': broadcast.content}
                        if reply_markup:
                            data['reply_markup'] = json.dumps(reply_markup)
                        with open(broadcast.photo_url, 'rb') as f:
                            r2 = requests.post(url, data=data, files={'photo': f}, timeout=15)
                        if r2.status_code == 200 and r2.json().get('ok'):
                            return True
                elif broadcast.photo_url:
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    payload = {'chat_id': chat_id, 'photo': broadcast.photo_url, 'caption': broadcast.content, 'parse_mode': 'HTML'}
                    if reply_markup:
                        payload['reply_markup'] = reply_markup
                    resp = requests.post(url, json=payload, timeout=10)
                    if resp.status_code == 200 and resp.json().get('ok'):
                        return True
                    err_desc = str(resp.json().get('description', '')).lower()
                    if 'entity' in err_desc or "can't parse" in err_desc:
                        payload = {'chat_id': chat_id, 'photo': broadcast.photo_url, 'caption': broadcast.content}
                        if reply_markup:
                            payload['reply_markup'] = reply_markup
                        r2 = requests.post(url, json=payload, timeout=10)
                        if r2.status_code == 200 and r2.json().get('ok'):
                            return True
                else:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = {'chat_id': chat_id, 'text': broadcast.content, 'parse_mode': 'HTML'}
                    if reply_markup:
                        payload['reply_markup'] = reply_markup
                    resp = requests.post(url, json=payload, timeout=7)
                    if resp.status_code == 200 and resp.json().get('ok'):
                        return True
                    err_desc = str(resp.json().get('description', '')).lower()
                    if 'entity' in err_desc or "can't parse" in err_desc:
                        payload = {'chat_id': chat_id, 'text': broadcast.content}
                        if reply_markup:
                            payload['reply_markup'] = reply_markup
                        r2 = requests.post(url, json=payload, timeout=7)
                        if r2.status_code == 200 and r2.json().get('ok'):
                            return True
            except Exception as ex:
                logger.warning(f"Error sending broadcast to {chat_id}: {ex}")
            return False

        if broadcast.target_audience in ['CHANNEL', 'SPECIFIC_CHANNEL']:
            channel_target = "@MafiaBotFather" if broadcast.target_audience == 'CHANNEL' else broadcast.target_user_id.strip()
            if not channel_target.startswith('@') and not channel_target.startswith('-'):
                channel_target = f"@{channel_target}"

            broadcast.total_recipients = 1
            broadcast.save(update_fields=['total_recipients'])

            master_token = (
                os.environ.get('MASTER_BOT_TOKEN') or
                os.environ.get('TELEGRAM_BOT_TOKEN') or
                '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
            )

            tokens_to_try = []
            if broadcast.target_bot:
                try:
                    cred = getattr(broadcast.target_bot, 'credential', None)
                    if cred and cred.get_token():
                        tokens_to_try.append(cred.get_token())
                except Exception:
                    pass

            if master_token not in tokens_to_try:
                tokens_to_try.append(master_token)

            for cred in BotCredential.objects.select_related('bot').filter(bot__status='ACTIVE'):
                try:
                    t = cred.get_token()
                    if t and t not in tokens_to_try:
                        tokens_to_try.append(t)
                except Exception:
                    pass

            delivered = False
            for token in tokens_to_try:
                if _send_tg(token, channel_target):
                    delivered = True
                    break

            if delivered:
                success += 1
            else:
                failed += 1

        elif broadcast.target_audience == 'SPECIFIC_USER':
            raw_target = str(broadcast.target_user_id).strip()
            clean_u = raw_target.lstrip('@').strip()
            tg_id = None

            if clean_u.isdigit():
                tg_id = int(clean_u)
            if not tg_id:
                prof = PlayerProfile.objects.filter(
                    Q(telegram_username__iexact=clean_u) | Q(telegram_username__iexact=f"@{clean_u}")
                ).first()
                if prof:
                    tg_id = prof.telegram_id
            if not tg_id:
                bu = BotUser.objects.filter(
                    Q(username__iexact=clean_u) | Q(username__iexact=f"@{clean_u}")
                ).first()
                if bu:
                    tg_id = bu.telegram_id
            if not tg_id:
                u_obj = User.objects.filter(
                    Q(username__iexact=clean_u) | Q(username__iexact=f"@{clean_u}")
                ).first()
                if u_obj and u_obj.telegram_id:
                    tg_id = u_obj.telegram_id
            if not tg_id:
                pl_obj = Player.objects.filter(
                    Q(username__iexact=clean_u) | Q(username__iexact=f"@{clean_u}")
                ).first()
                if pl_obj and pl_obj.telegram_user_id:
                    tg_id = pl_obj.telegram_user_id
            if not tg_id:
                bg = BotGroup.objects.filter(
                    Q(owner_username__iexact=clean_u) | Q(owner_username__iexact=f"@{clean_u}")
                ).first()
                if bg and bg.owner_telegram_id:
                    tg_id = bg.owner_telegram_id

            target_ids = [tg_id] if tg_id else []
            broadcast.total_recipients = len(target_ids)
            broadcast.save(update_fields=['total_recipients'])

            master_token = (
                os.environ.get('MASTER_BOT_TOKEN') or
                os.environ.get('TELEGRAM_BOT_TOKEN') or
                '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
            )

            # Determine tokens to try
            tokens_to_try = []

            # 1. If a specific bot was chosen by SuperAdmin
            if broadcast.target_bot:
                try:
                    cred = getattr(broadcast.target_bot, 'credential', None)
                    if cred:
                        t = cred.get_token()
                        if t:
                            tokens_to_try.append(t)
                except Exception:
                    pass

            # 2. If sender_bot_type is MASTER_BOT
            elif broadcast.sender_bot_type == 'MASTER_BOT':
                tokens_to_try.append(master_token)

            # 3. If ALL_USER_BOTS or AUTO -> Prioritize user's known bots, then fallback
            else:
                # User's known child bots
                if tg_id:
                    user_bot_ids = set(BotUser.objects.filter(telegram_id=tg_id, bot__isnull=False).values_list('bot_id', flat=True))
                    user_bot_ids.update(Player.objects.filter(telegram_user_id=tg_id).values_list('game__bot_id', flat=True))
                    for b_id in user_bot_ids:
                        try:
                            cred = BotCredential.objects.filter(bot_id=b_id).first()
                            if cred:
                                t = cred.get_token()
                                if t and t not in tokens_to_try:
                                    tokens_to_try.append(t)
                        except Exception:
                            pass

                # Append master token & all active child bot tokens as fallback
                if master_token not in tokens_to_try:
                    tokens_to_try.append(master_token)
                for cred in BotCredential.objects.select_related('bot').filter(bot__status='ACTIVE'):
                    try:
                        t = cred.get_token()
                        if t and t not in tokens_to_try:
                            tokens_to_try.append(t)
                    except Exception:
                        pass

            for uid in target_ids:
                delivered = False
                for token in tokens_to_try:
                    if _send_tg(token, uid):
                        delivered = True
                        break

                if delivered:
                    success += 1
                else:
                    failed += 1

                # In-App Notification
                UserNotification.objects.create(
                    telegram_id=uid,
                    title=broadcast.title,
                    message=broadcast.content,
                    notification_type='ADMIN'
                )

        elif broadcast.target_audience == 'BOT_OWNERS':
            # Target is Bot Owners -> Send from Master Bot Father
            target_ids = set(BotModel.objects.filter(owner__telegram_id__isnull=False).values_list('owner__telegram_id', flat=True))
            broadcast.total_recipients = len(target_ids)
            broadcast.save(update_fields=['total_recipients'])

            master_token = (
                os.environ.get('MASTER_BOT_TOKEN') or
                os.environ.get('TELEGRAM_BOT_TOKEN') or
                '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
            )

            for tg_id in target_ids:
                try:
                    if broadcast.photo_url:
                        url = f"https://api.telegram.org/bot{master_token}/sendPhoto"
                        payload = {
                            'chat_id': tg_id,
                            'photo': broadcast.photo_url,
                            'caption': broadcast.content,
                            'parse_mode': 'HTML'
                        }
                    else:
                        url = f"https://api.telegram.org/bot{master_token}/sendMessage"
                        payload = {
                            'chat_id': tg_id,
                            'text': broadcast.content,
                            'parse_mode': 'HTML'
                        }
                    if reply_markup:
                        payload['reply_markup'] = reply_markup
                    resp = requests.post(url, json=payload, timeout=6)
                    if resp.status_code == 200 and resp.json().get('ok'):
                        success += 1
                        UserNotification.objects.create(telegram_id=tg_id, title=broadcast.title, message=broadcast.content, notification_type='ADMIN')
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                time.sleep(0.04)

        else:
            # Target is ALL_PLAYERS -> Send strictly from all Child Game Bots (Mafia bots)
            child_bots = []
            for cred in BotCredential.objects.select_related('bot').all():
                try:
                    t = cred.get_token()
                    if t:
                        child_bots.append((cred.bot, t))
                except Exception:
                    pass

            target_ids = set(PlayerProfile.objects.filter(telegram_id__gte=100000000).values_list('telegram_id', flat=True))
            broadcast.total_recipients = len(target_ids)
            broadcast.save(update_fields=['total_recipients'])

            for tg_id in target_ids:
                user_delivered = False
                # Try sending from each child bot
                for bot_obj, token in child_bots:
                    try:
                        if broadcast.photo_url:
                            url = f"https://api.telegram.org/bot{token}/sendPhoto"
                            payload = {
                                'chat_id': tg_id,
                                'photo': broadcast.photo_url,
                                'caption': broadcast.content,
                                'parse_mode': 'HTML'
                            }
                        else:
                            url = f"https://api.telegram.org/bot{token}/sendMessage"
                            payload = {
                                'chat_id': tg_id,
                                'text': broadcast.content,
                                'parse_mode': 'HTML'
                            }
                        if reply_markup:
                            payload['reply_markup'] = reply_markup

                        resp = requests.post(url, json=payload, timeout=6)
                        if resp.status_code == 200 and resp.json().get('ok'):
                            user_delivered = True
                            break
                    except Exception:
                        pass
                    time.sleep(0.02)

                if user_delivered:
                    success += 1
                else:
                    failed += 1
                time.sleep(0.04)

        broadcast.sent_success = success
        broadcast.sent_failed = failed
        broadcast.status = 'COMPLETED'
        broadcast.save(update_fields=['sent_success', 'sent_failed', 'status'])
        AuditLog.log(action="BROADCAST_COMPLETED", actor="System", target=broadcast.title, details=f"Muvaffaqiyatli: {success}, Xato: {failed}")
        return True
