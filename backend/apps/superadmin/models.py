from django.db import models
from apps.common.models import BaseEntityModel


class BotSystemText(BaseEntityModel):
    """
    Dynamic in-game messages, alerts, and button labels configurable via SuperAdmin.
    """
    CATEGORY_CHOICES = [
        ('FATHER_BUTTONS', "Father Bot Tugmalari"),
        ('CHILD_BUTTONS', "O'yin Boti Tugmalari"),
        ('ACTION_BUTTONS', "Harakat Tugmalari (Tun/Kun/Ovoz)"),
        ('LOBBY', "Lobby & O'yin Yaratish"),
        ('NIGHT', "Tun Bosqichi & Rollar"),
        ('HERO', "Geroy & Zarbalar"),
        ('DAWN', "Tong & O'lim E'loni"),
        ('VOTING', "Kun & Ovoz Berish"),
        ('PROFILE', "Profil & Balans"),
        ('SHOP', "Do'kon & Xaridlar"),
        ('GIFS', "GIF Animatsiyalari"),
        ('TRANSFERS', "O'tkazmalar (Pul & Olmos)"),
        ('GENERAL', "Umumiy Xabarlar"),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True, help_text="Texnik kalit")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='GENERAL', db_index=True)
    title = models.CharField(max_length=200, help_text="Admin uchun tushunarli nom")
    content_uz = models.TextField(help_text="O'zbek tilidagi matn yoki tugma yozuvi")
    content_ru = models.TextField(blank=True, default='', help_text="Rus tilidagi matn (ixtiyoriy)")
    content_en = models.TextField(blank=True, default='', help_text="Ingliz tilidagi matn (ixtiyoriy)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'key']
        verbose_name = "Bot Tizim Matni"
        verbose_name_plural = "Bot Tizim Matnlari"

    def __str__(self):
        return f"[{self.category}] {self.title} ({self.key})"


class GameSetting(BaseEntityModel):
    """
    Global gameplay parameters, durations, pricing, and rewards editable in SuperAdmin.
    """
    GROUP_CHOICES = [
        ('TIMINGS', "O'yin Vaqtlari (Durations)"),
        ('PRICES', "Do'kon Mahsulotlari Narxlari"),
        ('HERO', "Geroy Sozlamalari"),
        ('RANKS', "Unvonlar & Darajalar"),
        ('REWARDS', "Mukofotlar & Bonuslar"),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True)
    group = models.CharField(max_length=30, choices=GROUP_CHOICES, default='TIMINGS', db_index=True)
    title = models.CharField(max_length=200)
    value = models.CharField(max_length=100, help_text="Qiymat (masalan: 60, 300, 2)")
    unit = models.CharField(max_length=50, blank=True, default='', help_text="Birlik (sekund, 💶, 💎)")
    description = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['group', 'key']
        verbose_name = "O'yin Sozlamasi"
        verbose_name_plural = "O'yin Sozlamalari"

    def __str__(self):
        return f"[{self.group}] {self.title} = {self.value} {self.unit}"

    def int_value(self, default: int = 0) -> int:
        try:
            return int(self.value)
        except Exception:
            return default


class PromoCode(BaseEntityModel):
    """
    Gift promo codes created by SuperAdmin redeemable by players.
    """
    REWARD_TYPE_CHOICES = [
        ('COINS', '💶 Dollar'),
        ('DIAMONDS', '💎 Olmos'),
        ('VIP_DAYS', '👑 VIP Kunlar'),
        ('HIMOYA', '🛡 Himoya qalqoni'),
        ('OSISH_HIMOYA', '⚖️ Osishdan himoya'),
        ('HUJJAT', '📁 Soxta hujjat'),
        ('VAKSINA', '💉 Zombi Vaksinasi'),
        ('GEROY_HIMOYA', '🔰 Geroydan himoya'),
        ('GEROY', '🥷 Geroy'),
        ('ROLE_DON', '🎭 Faol Rol: Don'),
        ('ROLE_KOMISSAR', '🎭 Faol Rol: Komissar'),
        ('ROLE_SHIFOKOR', '🎭 Faol Rol: Shifokor'),
        ('ROLE_CITIZEN', '🎭 Faol Rol: Tinch aholi'),
        ('ROLE_QOTIL', '🔪 Faol Rol: Qotil'),
        ('ROLE_KEZUVCHI', '💃 Faol Rol: Kezuvchi'),
        ('ROLE_SERJANT', '👮🏼‍♂️ Faol Rol: Serjant'),
        ('ROLE_DAYDI', '🍾 Faol Rol: Daydi'),
        ('ROLE_ADVOKAT', '💼 Faol Rol: Advokat'),
        ('ROLE_SUIDSID', '🤡 Faol Rol: Suidsid'),
        ('ROLE_UBIYTSA', '🥷 Faol Rol: Ubiytsa'),
        ('ROLE_AFSUNGAR', '🧙🏼 Faol Rol: Afsungar'),
        ('ROLE_TUZOQCHI', '🕸 Faol Rol: Tuzoqchi'),
        ('ROLE_ZOMBI', '🧟 Faol Rol: Zombi'),
        ('ROLE_KIMYOGAR', '🧪 Faol Rol: Kimyogar'),
        ('ROLE_AXMOQ', '🤪 Faol Rol: Axmoq'),
        ('ROLE_BUQALAMUN', '🦎 Faol Rol: Buqalamun'),
        ('ROLE_RAIS', '🏛 Faol Rol: Rais'),
        ('ROLE_HAMSHIRA', '👩🏼‍⚕️ Faol Rol: Hamshira'),
        ('ROLE_JOKER', '🃏 Faol Rol: Joker'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    reward_type = models.CharField(max_length=30, choices=REWARD_TYPE_CHOICES, default='COINS')
    reward_amount = models.PositiveIntegerField(default=100)
    max_uses = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)
    used_by = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Promokod"
        verbose_name_plural = "Promokodlar"

    def __str__(self):
        return f"Promo: {self.code} ({self.reward_amount} {self.get_reward_type_display()}) [{self.used_count}/{self.max_uses}]"


class BroadcastMessage(BaseEntityModel):
    """
    Broadcast announcements sent to all players or bot owners.
    """
    TARGET_CHOICES = [
        ('ALL_PLAYERS', "Barcha botlarning barcha o'yinchilariga"),
        ('BOT_OWNERS', "Faqat botlarning haqiqiy egalariga"),
        ('SPECIFIC_USER', "Alohida bitta foydalanuvchiga"),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Kutilmoqda'),
        ('IN_PROGRESS', 'Yuborilmoqda'),
        ('COMPLETED', 'Yakunlandi'),
        ('FAILED', 'Xatolik'),
    ]

    title = models.CharField(max_length=200, help_text="E'lon sarlavhasi")
    content = models.TextField(help_text="Xabar matni (HTML teglari qo'llab-quvvatlanadi)")
    target_audience = models.CharField(max_length=30, choices=TARGET_CHOICES, default='ALL_PLAYERS')
    target_user_id = models.CharField(max_length=100, blank=True, default='', help_text="Alohida foydalanuvchi Telegram ID yoki @username")
    target_bot = models.ForeignKey('bots.Bot', on_delete=models.SET_NULL, null=True, blank=True, related_name='broadcasts', help_text="Yuborish uchun tanlangan aniq bot")
    sender_bot_type = models.CharField(max_length=50, default='AUTO', blank=True, help_text="Yuboruvchi bot turi: AUTO, MASTER_BOT, ALL_USER_BOTS, SPECIFIC_BOT, ALL_ACTIVE_BOTS")
    photo_url = models.URLField(max_length=500, blank=True, default='')
    button_text = models.CharField(max_length=100, blank=True, default='')
    button_url = models.URLField(max_length=500, blank=True, default='')
    
    total_recipients = models.PositiveIntegerField(default=0)
    sent_success = models.PositiveIntegerField(default=0)
    sent_failed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"

    def __str__(self):
        return f"{self.title} ({self.get_target_audience_display()}) - {self.status}"


class AuditLog(BaseEntityModel):
    """
    Platform-wide audit and activity logs capped at latest 200 items.
    """
    action = models.CharField(max_length=100, db_index=True)
    actor = models.CharField(max_length=150, default='SuperAdmin')
    target = models.CharField(max_length=200, blank=True, default='')
    details = models.TextField(blank=True, default='')
    ip_address = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Loglar"

    def __str__(self):
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {self.action} by {self.actor}"

    @classmethod
    def log(cls, action: str, actor: str = 'SuperAdmin', target: str = '', details: str = '', ip: str = ''):
        """Creates an audit entry and prunes older records beyond 200 items."""
        entry = cls.objects.create(
            action=action,
            actor=actor,
            target=target,
            details=details,
            ip_address=ip
        )
        total_count = cls.objects.count()
        if total_count > 200:
            keep_ids = list(cls.objects.order_by('-created_at')[:200].values_list('id', flat=True))
            cls.objects.exclude(id__in=keep_ids).delete()
        return entry


class UserNotification(BaseEntityModel):
    """
    In-app notifications displayed inside the WebApp and delivered via Bot.
    """
    TYPE_CHOICES = [
        ('SYSTEM', 'Tizim xabari'),
        ('ADMIN', "Admin e'loni"),
        ('PERSONAL', 'Shaxsiy xabar'),
        ('TRANSFER', "O'tkazma bildirishnomasi"),
    ]

    telegram_id = models.BigIntegerField(db_index=True, null=True, blank=True, help_text="NULL bo'lsa barcha foydalanuvchilarga ko'rinadi")
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='SYSTEM')
    is_read = models.BooleanField(default=False)
    created_by = models.CharField(max_length=150, default='SuperAdmin')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Foydalanuvchi Bildirishnomasi"
        verbose_name_plural = "Foydalanuvchi Bildirishnomalari"

    def __str__(self):
        return f"[{self.notification_type}] {self.title} (TG: {self.telegram_id or 'Hammasi'})"


class FeedbackMessage(BaseEntityModel):
    """
    User questions & suggestions sent via /start -> 'Savol va taklif'.
    """
    telegram_id = models.BigIntegerField(db_index=True)
    telegram_username = models.CharField(max_length=150, blank=True, null=True)
    user_display_name = models.CharField(max_length=200, blank=True, default='')
    message_text = models.TextField()
    is_replied = models.BooleanField(default=False)
    admin_reply = models.TextField(blank=True, default='')
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Savol va Taklif"
        verbose_name_plural = "Savollar va Takliflar"

    def __str__(self):
        return f"Feedback from {self.user_display_name} (@{self.telegram_username or self.telegram_id}): {self.message_text[:30]}..."
