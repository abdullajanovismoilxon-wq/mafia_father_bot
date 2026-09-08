"""
Configuration-driven Role Distribution Service with 38 Platform Roles.
Accurately calibrated balance based on player counts from 4 to 30+ players.
"""
import random
import logging
from typing import List, Dict, Optional, Tuple
from apps.games.models import Role, RoleType, RoleTeam, Player

logger = logging.getLogger(__name__)

ROLE_DEFINITIONS = [
    # ─── 1. TINCH AHOLI (CIVILIAN - 14 ROLES) ──────────────────────────────────
    {"code": "citizen", "name": "CITIZEN", "team": RoleTeam.CIVILIAN, "title": "👨🏼 Tinch aholi", "priority": 100, "desc": "Kunduzgi muhokama va ovoz berishda faol qatnashib, Mafiyalarni fosh etadi."},
    {"code": "doctor", "name": "DOCTOR", "team": RoleTeam.CIVILIAN, "title": "👨🏼‍⚕️ Shifokor", "priority": 2, "desc": "Har tunda bir fuqaroni davolab, o'limdan qutqarib qoladi."},
    {"code": "detective", "name": "DETECTIVE", "team": RoleTeam.CIVILIAN, "title": "🕵🏻‍♂️ Komissar", "priority": 3, "desc": "Tunda gumondorlarni tekshirib mafiyani fosh etadi yoki otib o'ldiradi."},
    {"code": "serjant", "name": "SERJANT", "team": RoleTeam.CIVILIAN, "title": "👮🏼‍♂️ Serjant", "priority": 6, "desc": "Komissarning o'ng qo'li. Komissar halok bo'lsa, uning o'rnini egallaydi."},
    {"code": "hamshira", "name": "HAMSHIRA", "team": RoleTeam.CIVILIAN, "title": "👩🏼‍⚕️ Hamshira", "priority": 19, "desc": "Shifokorning yordamchisi. Shifokor halok bo'lsa, yangi Shifokorga aylanadi."},
    {"code": "omadli", "name": "OMADLI", "team": RoleTeam.CIVILIAN, "title": "🤞🏼 Omadli", "priority": 21, "desc": "Omadli fuqaro. Tungi hujum vaqtida omadi kulsa (50%) omon qoladi. Tunda vazifasi yo'qligi sababli AFK jazosi yo'q."},
    {"code": "janob", "name": "JANOB", "team": RoleTeam.CIVILIAN, "title": "🎖 Janob", "priority": 22, "desc": "Kunduzgi ovoz berishda ovozi 2 kishinikiga teng va ovozlar ro'yxatida shaxsi sir qoladi. AFK jazosi yo'q."},
    {"code": "sotqin", "name": "SOTQIN", "team": RoleTeam.CIVILIAN, "title": "🤓 Sotqin", "priority": 23, "desc": "Tunda bir o'yinchini tekshiradi: agar u Mafia, Don yoki Qotil bo'lsa, tongda shaxsini sir tutib shaharga jar soladi."},
    {"code": "admiral", "name": "ADMIRAL", "team": RoleTeam.CIVILIAN, "title": "🧑🏻‍✈️ Admiral", "priority": 24, "desc": "Komissar va Serjant tirik ekan, hech kim o'ldirolmaydi. Ular halok bo'lsa, Admiral yangi Komissar bo'ladi."},
    {"code": "robingud", "name": "ROBINGUD", "team": RoleTeam.CIVILIAN, "title": "🏹 Robin Gud", "priority": 25, "desc": "Har tunda 1 kishini o'ldira oladi. Agar bitta o'yinda 2 ta tinch aholini o'ldirsa, aholi uni toshbo'ron qilib o'ldiradi."},
    {"code": "fotoparatchi", "name": "FOTOPARATCHI", "team": RoleTeam.CIVILIAN, "title": "📸 Fotoparatchi", "priority": 26, "desc": "Tunda kimnidir tanlaydi: agar u tunda mehmonga borgan bo'lsa, kimnikiga borganini rasmga olib shaharga ma'lum qiladi."},
    {"code": "daydi", "name": "DAYDI", "team": RoleTeam.CIVILIAN, "title": "🍾 Daydi", "priority": 7, "desc": "Tunda ichkilik so'rab mehmonga boradi. Agar borgan joyi o'ldirilsa, qotilni fosh qiladi."},
    {"code": "kezuvchi", "name": "KEZUVCHI", "team": RoleTeam.CIVILIAN, "title": "💃 Kezuvchi", "priority": 5, "desc": "Tunda tanlagan odamining tungi harakatini va kunduzgi ovoz berish huquqini bloklaydi."},

    # ─── 2. MAFIA (7 ROLES) ──────────────────────────────────────────────────
    {"code": "don", "name": "DON", "team": RoleTeam.MAFIA, "title": "🤵🏻 Don", "priority": 1, "desc": "Mafialar sardori. Tunda kim o'lishini hal qiladi va Komissar tekshiruvida begunoh ko'rinadi."},
    {"code": "mafia", "name": "MAFIA", "team": RoleTeam.MAFIA, "title": "🤵🏼 Mafia", "priority": 10, "desc": "Don bilan birgalikda shahar aholisini yo'q qiladi. Don o'lsa yangi Don bo'ladi."},
    {"code": "advokat", "name": "ADVOKAT", "team": RoleTeam.MAFIA, "title": "💼 Advokat", "priority": 8, "desc": "Tunda tanlagan hamkorini Komissar tekshiruvidan himoyalaydi (tinch aholi bo'lib ko'rsatadi)."},
    {"code": "ubiytsa", "name": "UBIYTSA", "team": RoleTeam.MAFIA, "title": "🥷 Ubiytsa", "priority": 11, "desc": "Mafiya yollanma qotili. Har tunda 1 kishini o'ldiradi. Komissarga duch kelsa o'zi o'ladi."},
    {"code": "jurnalist", "name": "JURNALIST", "team": RoleTeam.MAFIA, "title": "👩🏼‍💻 Jurnalist", "priority": 27, "desc": "Mafialar agenti. Tunda intervyu bahonasida borgan xonadoniga kimlar kelganini kuzatib, Mafiyaga xabar beradi."},
    {"code": "aygoqchi", "name": "AYGOQCHI", "team": RoleTeam.MAFIA, "title": "🦇 Ayg'oqchi", "priority": 28, "desc": "Tunda xohlagan bitta o'yinchining rolini aniqlab, uni Mafiya guruhiga oshkor qiladi."},
    {"code": "laborant", "name": "LABORANT", "team": RoleTeam.MAFIA, "title": "👩‍⚕️ Laborant", "priority": 29, "desc": "Tunda Mafia a'zosini tanlasa himoyalaydi, Mafia bo'lmagan boshqa o'yinchilarni esa zaharlab o'ldiradi."},

    # ─── 3. YAKKA ROLLAR (SOLO - 16 ROLES) ──────────────────────────────────
    {"code": "kimyogar", "name": "KIMYOGAR", "team": RoleTeam.SOLO, "title": "👨‍🔬 Kimyogar", "priority": 15, "desc": "Erkin rol. Tunda istasa birovni davolaydi, istasa zahar berib o'ldiradi. Omon qolsa g'alaba qozonadi."},
    {"code": "rais", "name": "RAIS", "team": RoleTeam.SOLO, "title": "💰 Rais", "priority": 18, "desc": "Erkin boyvachcha. Har tunda kimgadir 1-100 $ dollar tarqatadi. Omon qolsa g'alaba qozonadi."},
    {"code": "bori", "name": "BORI", "team": RoleTeam.SOLO, "title": "🐺 Bo'ri", "priority": 30, "desc": "Agar Mafia/Don o'ldirsa — keyingi tunda Mafiyaga aylanadi. Komissar o'ldirsa — Serjantga aylanadi. Boshqalar o'ldirsa — o'ladi."},
    {"code": "aferist", "name": "AFERIST", "team": RoleTeam.SOLO, "title": "🤹🏻 Aferist", "priority": 31, "desc": "Tunda kimningdir ovozini o'g'irlaydi. Ertasi kuni jabrlanuvchi ovoz berolmaydi, Aferist uning nomidan ovoz beradi."},
    {"code": "gazabkor", "name": "GAZABKOR", "team": RoleTeam.SOLO, "title": "🧌 G'azabkor", "priority": 32, "desc": "Har tunda 1 kishini belgilaydi. O'zi o'lganida barcha belgilanganlar birga halok bo'ladi. Kamida 3 kishini belgilab o'lsa yutadi."},
    {"code": "sehrgar", "name": "SEHRGAR", "team": RoleTeam.SOLO, "title": "🧙 Sehrgar", "priority": 33, "desc": "Don, Qotil, Komissar hujum qilsa o'lmaydi va ularga rahm qilish yoki o'ldirish tanlovi beriladi. Osilsa yoki Afsungar/Ovchi o'ldirsa o'ladi."},
    {"code": "qotil", "name": "QOTIL", "team": RoleTeam.SOLO, "title": "🔪 Qotil", "priority": 4, "desc": "Yakka o'ynaydi. Har tunda 1 kishini o'ldiradi. Shaharda yolg'iz qolsa yutadi."},
    {"code": "konchi", "name": "KONCHI", "team": RoleTeam.SOLO, "title": "👷🏻‍♂️ Konchi", "priority": 34, "desc": "Tunda 10 ta kondan birini tanlaydi (3 ta o'lim, 2 ta 💎, 5 ta 💵). Sirpanishdan himoya bo'lsa o'limdan omon qoladi."},
    {"code": "qaroqchi", "name": "QAROQCHI", "team": RoleTeam.SOLO, "title": "⚔️ Qaroqchi", "priority": 35, "desc": "Tunda kimningdir pulini o'g'irlaydi. Pul topolmasa 50% HP jarohatlaydi. 0% HP bo'lgan o'yinchi halok bo'ladi."},
    {"code": "qorbobo", "name": "QORBOBO", "team": RoleTeam.SOLO, "title": "🎅🏻 Qorbobo", "priority": 36, "desc": "Har tunda o'yinchilarga do'kondagi qurollar yoki faol rollarni sovg'a qiladi. Omon qolsa yutadi."},
    {"code": "oshpaz", "name": "OSHPAZ", "team": RoleTeam.SOLO, "title": "👨🏼‍🍳 Oshpaz", "priority": 37, "desc": "Tunda maxsus taomini beradi. Ertasi kuni jabrlanuvchining boshi aylanib, ovozi tasodifiy boshqa o'yinchiga ketadi."},
    {"code": "afsungar", "name": "AFSUNGAR", "team": RoleTeam.SOLO, "title": "🧙🏼 Afsungar", "priority": 12, "desc": "Uni tunda o'ldirgan qotilning o'zi o'ladi. Kunduzi osilsa 1 kishini o'zi bilan olib ketadi."},
    {"code": "tuzoqchi", "name": "TUZOQCHI", "team": RoleTeam.SOLO, "title": "🕸 Tuzoqchi", "priority": 13, "desc": "1 kishiga tuzoq qo'yadi. Unga borgan har qanday boshqa mehmon o'ladi."},
    {"code": "axmoq", "name": "AXMOQ", "team": RoleTeam.SOLO, "title": "🤪 Axmoq", "priority": 16, "desc": "Tinch aholini tanlasa osilishdan himoyalanadi, Mafiyani tanlasa kalla qo'yib o'ldiradi."},
    {"code": "buqalamun", "name": "BUQALAMUN", "team": RoleTeam.SOLO, "title": "🦎 Buqalamun", "priority": 17, "desc": "1-tunda tanlagan odamining roliga aylanadi."},
    {"code": "joker", "name": "JOKER", "team": RoleTeam.SOLO, "title": "🃏 Joker", "priority": 20, "desc": "4 ta qutiga bomba joylaydi. O'yinchi bombani tanlasa o'ladi."},
    {"code": "suidsid", "name": "SUIDSID", "team": RoleTeam.SOLO, "title": "🤡 Suidsid", "priority": 9, "desc": "Agar uni kunduzi osib o'ldirishsa — u bir o'zi g'alaba qozonadi!"},

    # ─── 4. ZOMBI (1 ROLE) ───────────────────────────────────────────────────
    {"code": "zombi", "name": "ZOMBI", "team": RoleTeam.ZOMBIE, "title": "🧟 Zombi", "priority": 14, "desc": "Har tunda 1 kishini tishlab Zombiga aylantiradi. Barcha tiriklar Zombi bo'lsa g'alaba qozonadi."},
]


class RoleDistributionService:
    @classmethod
    def get_or_create_base_roles(cls, all_roles: bool = False) -> Dict[str, Role]:
        roles = {}
        for item in ROLE_DEFINITIONS:
            r, _ = Role.objects.update_or_create(
                code=item["code"],
                owner=None,
                defaults={
                    "name": item["name"],
                    "team": item["team"],
                    "description": item["desc"],
                    "is_system": True,
                    "priority": item["priority"]
                }
            )
            roles[item["name"]] = r

        if not all_roles:
            base_keys = [RoleType.CITIZEN, RoleType.MAFIA, RoleType.DON, RoleType.DOCTOR, RoleType.DETECTIVE]
            return {k: roles[k] for k in base_keys if k in roles}

        return roles

    @classmethod
    def get_or_create_all_roles(cls) -> Dict[str, Role]:
        return cls.get_or_create_base_roles(all_roles=True)

    @classmethod
    def calculate_role_list(cls, player_count: int) -> List[str]:
        if player_count < 4:
            raise ValueError("Minimum player count is 4")

        if player_count == 4:
            return [RoleType.MAFIA, RoleType.DOCTOR, RoleType.CITIZEN, RoleType.CITIZEN]

        if player_count == 5:
            return [RoleType.MAFIA, RoleType.DOCTOR, RoleType.DETECTIVE, RoleType.CITIZEN, RoleType.CITIZEN]

        if player_count == 6:
            return [RoleType.DON, RoleType.MAFIA, RoleType.DOCTOR, RoleType.DETECTIVE, RoleType.CITIZEN, RoleType.CITIZEN]

        inactive_role_names = set()
        try:
            inactive_role_names = set(Role.objects.filter(is_active=False).values_list('name', flat=True))
        except Exception:
            pass

        def pick_active(choices: List[str], fallback: str = "CITIZEN") -> str:
            valid = [c for c in choices if c not in inactive_role_names]
            return random.choice(valid) if valid else fallback

        def pick_multiple_active(choices: List[str], count: int) -> List[str]:
            valid = [c for c in choices if c not in inactive_role_names]
            random.shuffle(valid)
            return valid[:count]

        roles: List[str] = [RoleType.DON, RoleType.MAFIA, RoleType.DOCTOR, RoleType.DETECTIVE]

        town_pool = ["OMADLI", "JANOB", "SOTQIN", "ADMIRAL", "ROBINGUD", "FOTOPARATCHI", "KEZUVCHI", "DAYDI", "SERJANT", "HAMSHIRA"]
        mafia_pool = ["ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"]
        solo_pool = ["KIMYOGAR", "RAIS", "BORI", "AFERIST", "GAZABKOR", "SEHRGAR", "QOTIL", "KONCHI", "QAROQCHI", "QORBOBO", "OSHPAZ", "AFSUNGAR", "TUZOQCHI", "AXMOQ", "BUQALAMUN", "JOKER", "SUIDSID", "ZOMBI"]

        if player_count == 7:
            sp = pick_active(town_pool + solo_pool, "CITIZEN")
            roles.extend([sp, RoleType.CITIZEN, RoleType.CITIZEN])
            return roles[:player_count]

        if player_count == 8:
            t1 = pick_active(town_pool, "SERJANT")
            t2 = pick_active(town_pool, "OMADLI")
            s1 = pick_active(solo_pool, "QOTIL")
            roles.extend([t1, t2, s1, RoleType.CITIZEN])
            return roles[:player_count]

        if player_count in (9, 10):
            m_picks = pick_multiple_active(mafia_pool, 1)
            roles.extend(m_picks)
            roles.append(pick_active(town_pool, "SERJANT"))
            roles.append(pick_active(town_pool, "JANOB"))
            roles.append(pick_active(solo_pool, "QOTIL"))

            while len(roles) < player_count:
                roles.append(RoleType.CITIZEN)
            return roles[:player_count]

        if player_count in (11, 12):
            m_picks = pick_multiple_active(mafia_pool, 1)
            roles.extend(m_picks)
            roles.extend(pick_multiple_active(town_pool, 3))
            roles.extend(pick_multiple_active(solo_pool, 2))

            while len(roles) < player_count:
                roles.append(RoleType.CITIZEN)
            return roles[:player_count]

        if player_count >= 13:
            maf_count = min(5, max(3, player_count // 4))
            m_list = pick_multiple_active(mafia_pool, maf_count - 2)
            roles.extend(m_list)

            town_picks = pick_multiple_active(town_pool, min(len(town_pool), player_count // 3))
            roles.extend(town_picks)

            solo_picks = pick_multiple_active(solo_pool, min(len(solo_pool), player_count // 4))
            roles.extend(solo_picks)

            while len(roles) < player_count:
                roles.append(RoleType.CITIZEN)
            return roles[:player_count]

        return roles

    @classmethod
    def calculate_role_list_from_configuration(cls, player_count: int, configuration=None, seed: Optional[int] = None) -> List[str]:
        if player_count < 4:
            raise ValueError("Minimum player count is 4")

        if configuration is None or not hasattr(configuration, 'distribution_rules') or not configuration.distribution_rules.exists():
            return cls.calculate_role_list(player_count)

        from apps.games.models import DistributionType
        rules = list(configuration.distribution_rules.select_related('role').order_by('-priority', 'role__name'))

        roles: List[str] = []
        rng = random.Random(seed) if seed is not None else random

        for rule in rules:
            if not rule.role:
                continue
            rname = rule.role.name
            if rule.distribution_type == DistributionType.EXACT:
                count = rule.min_count
            elif rule.distribution_type == DistributionType.RANGE:
                count = rng.randint(rule.min_count, rule.max_count)
            elif rule.distribution_type == DistributionType.PERCENTAGE:
                count = max(1, round(player_count * rule.percentage / 100))
            else:
                count = rule.min_count

            roles.extend([rname] * count)
            if len(roles) >= player_count:
                break

        while len(roles) < player_count:
            roles.append(RoleType.CITIZEN)

        return roles[:player_count]

    @classmethod
    def assign_roles_to_players(cls, players: List[Player], configuration=None, seed: Optional[int] = None) -> List[Tuple[Player, Role]]:
        """
        Assigns roles to a list of players.
        Considers inventory active roles (purchased in shop/profile), then fills remaining roles using calculate_role_list.
        """
        all_roles_dict = cls.get_or_create_base_roles(all_roles=True)
        player_count = len(players)

        if configuration:
            needed_role_names = cls.calculate_role_list_from_configuration(player_count, configuration, seed=seed)
        else:
            needed_role_names = cls.calculate_role_list(player_count)

        rng = random.Random(seed) if seed is not None else random

        player_list = list(players)
        if seed is not None:
            player_list.sort(key=lambda p: (p.telegram_user_id or 0, str(p.id)))

        role_pool = list(needed_role_names)
        rng.shuffle(role_pool)
        rng.shuffle(player_list)

        from apps.economy.models import Inventory

        assignments: List[Tuple[Player, Role]] = []
        unassigned_players: List[Player] = []

        # 1. First priority: Check purchased active role items in inventory (if not in deterministic seed test)
        for p in player_list:
            active_role_inv = None
            if seed is None:
                active_role_inv = Inventory.objects.filter(
                    telegram_id=p.telegram_user_id,
                    item__code__startswith='role_',
                    is_active=True,
                    quantity__gt=0
                ).select_related('item').first()

            if active_role_inv:
                role_code = active_role_inv.item.code.replace('role_', '').lower()
                matched_role = None
                for r_name, r_obj in all_roles_dict.items():
                    if r_obj.code.lower() == role_code:
                        matched_role = r_obj
                        break

                if matched_role:
                    p.role = matched_role
                    p.save(update_fields=['role'])
                    assignments.append((p, matched_role))
                    if matched_role.name in role_pool:
                        role_pool.remove(matched_role.name)
                    active_role_inv.quantity -= 1
                    if active_role_inv.quantity <= 0:
                        active_role_inv.is_active = False
                    active_role_inv.save(update_fields=['quantity', 'is_active'])
                    continue

            unassigned_players.append(p)

        # 2. Assign remaining roles from role_pool
        for p in unassigned_players:
            if role_pool:
                r_name = role_pool.pop(0)
            else:
                r_name = "CITIZEN"

            r_obj = all_roles_dict.get(r_name) or all_roles_dict.get("CITIZEN")
            p.role = r_obj
            p.save(update_fields=['role'])
            assignments.append((p, r_obj))

        return assignments
