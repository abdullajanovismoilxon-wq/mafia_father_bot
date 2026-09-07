from typing import Dict, Any, Optional, List
import random
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.games.models import (
    Game, Player, NightAction, NightActionType, Vote, RoleTeam, RoleType, Role
)
from apps.economy.models import Inventory, Wallet, WalletTransaction, TransactionType, CurrencyType
from apps.superadmin.models import GameSetting
from apps.superadmin.services import SettingService


class GameResolutionService:
    """
    Deterministic resolution engine for Night Actions and Day Votes across all 38 Mafia roles.
    """

    @classmethod
    def resolve_night_phase(cls, game: Game) -> Dict[str, Any]:
        """
        Processes night actions in deterministic priority order across all 38 roles.
        """
        with transaction.atomic():
            actions = list(NightAction.objects.filter(
                game=game, round=game.round_number
            ).select_related('actor', 'target', 'target__role', 'actor__role'))

            alive_players = list(Player.objects.filter(game=game, is_alive=True).select_related('role'))
            alive_player_map = {p.id: p for p in alive_players}

            # -------------------------------------------------------------
            # 1. Blockers & Role Alterations (Kezuvchi, Aferist, Oshpaz)
            # -------------------------------------------------------------
            blocked_actor_ids = set()
            kezuvchi_blocked_players = []
            dori_shield_saved_players = []

            # Kezuvchi
            kezuvchi_actions = [a for a in actions if a.action_type == NightActionType.KEZUVCHI_VISIT and a.target]
            for ka in kezuvchi_actions:
                if ka.target_id in alive_player_map:
                    target_p = alive_player_map[ka.target_id]
                    if not target_p.metadata:
                        target_p.metadata = {}

                    # Check Dori himoya (strict 1-use per game)
                    if not target_p.metadata.get('used_dori_himoya'):
                        dori_inv = Inventory.objects.filter(
                            telegram_id=target_p.telegram_user_id,
                            item__code='dori_himoya',
                            is_active=True,
                            quantity__gt=0
                        ).first()
                        if dori_inv:
                            dori_inv.quantity -= 1
                            if dori_inv.quantity <= 0:
                                dori_inv.is_active = False
                            dori_inv.save(update_fields=['quantity', 'is_active'])
                            target_p.metadata['used_dori_himoya'] = True
                            target_p.save(update_fields=['metadata'])
                            dori_shield_saved_players.append(target_p)
                            continue

                    blocked_actor_ids.add(target_p.id)
                    target_p.metadata['blocked_voting_round'] = game.round_number
                    target_p.save(update_fields=['metadata'])
                    kezuvchi_blocked_players.append(target_p)

            # Aferist (Steals vote for tomorrow)
            aferist_actions = [a for a in actions if a.action_type == NightActionType.AFERIST_STEAL and a.target]
            for aa in aferist_actions:
                if aa.target_id in alive_player_map:
                    target_p = alive_player_map[aa.target_id]
                    if not target_p.metadata:
                        target_p.metadata = {}
                    target_p.metadata['blocked_voting_round'] = game.round_number
                    target_p.metadata['aferist_proxy_voter_id'] = str(aa.actor_id)
                    target_p.save(update_fields=['metadata'])

            # Oshpaz (Dizzy meal -> scrambles vote tomorrow)
            oshpaz_actions = [a for a in actions if a.action_type == NightActionType.OSHPAZ_FEED and a.target]
            for oa in oshpaz_actions:
                if oa.target_id in alive_player_map:
                    target_p = alive_player_map[oa.target_id]
                    if not target_p.metadata:
                        target_p.metadata = {}
                    target_p.metadata['dizzy_voting_round'] = game.round_number
                    target_p.save(update_fields=['metadata'])

            valid_actions = [a for a in actions if a.actor_id not in blocked_actor_ids]

            # -------------------------------------------------------------
            # 2. Economy & Gifting (Qaroqchi, Rais, Qorbobo)
            # -------------------------------------------------------------
            robbery_logs = []
            qaroqchi_actions = [a for a in valid_actions if a.action_type == NightActionType.QAROQCHI_ROB and a.target]
            for qa in qaroqchi_actions:
                if qa.target_id in alive_player_map:
                    target_p = alive_player_map[qa.target_id]
                    t_wallet = Wallet.objects.filter(telegram_id=target_p.telegram_user_id).first()
                    q_wallet = Wallet.objects.filter(telegram_id=qa.actor.telegram_user_id).first()

                    if t_wallet and t_wallet.money > Decimal('0.00') and q_wallet:
                        stolen = min(t_wallet.money, Decimal(str(random.randint(10, 50))))
                        t_wallet.money -= stolen
                        q_wallet.money += stolen
                        t_wallet.save(update_fields=['money'])
                        q_wallet.save(update_fields=['money'])
                        robbery_logs.append(f"⚔️ Qaroqchi {target_p.display_name} dan ${stolen} o'mardi!")
                    else:
                        # No money -> beat up (50% HP loss)
                        if not target_p.metadata:
                            target_p.metadata = {}
                        current_hp = target_p.metadata.get('hp', 100) - 50
                        target_p.metadata['hp'] = current_hp
                        target_p.save(update_fields=['metadata'])
                        robbery_logs.append(f"⚔️ Qaroqchi {target_p.display_name} ni do'pposlab ketdi (Joni: {current_hp}%)!")

            # Rais ($ gift)
            rais_actions = [a for a in valid_actions if a.action_type == NightActionType.RAIS_GIFT and a.target]
            for ra in rais_actions:
                if ra.target_id in alive_player_map:
                    target_p = alive_player_map[ra.target_id]
                    gift_amount = Decimal(str(random.randint(1, 100)))
                    t_wallet, _ = Wallet.objects.get_or_create(telegram_id=target_p.telegram_user_id)
                    t_wallet.money += gift_amount
                    t_wallet.save(update_fields=['money'])

            # Qorbobo (Gift random item)
            qorbobo_actions = [a for a in valid_actions if a.action_type == NightActionType.QORBOBO_GIFT and a.target]
            for qba in qorbobo_actions:
                if qba.target_id in alive_player_map:
                    target_p = alive_player_map[qba.target_id]
                    from apps.economy.models import MarketplaceItem
                    gift_codes = ['himoya', 'osish_himoya', 'hujjat', 'dori_himoya', 'sirpanish_himoya']
                    picked_code = random.choice(gift_codes)
                    item = MarketplaceItem.objects.filter(code=picked_code).first()
                    if item:
                        inv, _ = Inventory.objects.get_or_create(
                            telegram_id=target_p.telegram_user_id, item=item,
                            defaults={'quantity': 0, 'is_active': True}
                        )
                        inv.quantity += 1
                        inv.is_active = True
                        inv.save(update_fields=['quantity', 'is_active'])

            # -------------------------------------------------------------
            # 3. Traps & Shields / Protections (Doctor, Laborant, Advokat, Tuzoqchi)
            # -------------------------------------------------------------
            advokat_actions = [a for a in valid_actions if a.action_type == NightActionType.ADVOKAT_PROTECT and a.target]
            advokat_protected_ids = {a.target_id for a in advokat_actions}

            tuzoqchi_actions = [a for a in valid_actions if a.action_type == NightActionType.TUZOQCHI_TRAP and a.target]
            trapped_player_ids = {a.target_id: a.actor for a in tuzoqchi_actions}

            doctor_protects = [a for a in valid_actions if a.action_type == NightActionType.DOCTOR_PROTECT and a.target]
            protected_target_ids = {p.target_id for p in doctor_protects}

            # Laborant (Protects Mafia teammates, poisons others)
            laborant_kills = []
            laborant_actions = [a for a in valid_actions if a.action_type == NightActionType.LABORANT_ACTION and a.target]
            for la in laborant_actions:
                if la.target and la.target.role and la.target.role.team == RoleTeam.MAFIA:
                    protected_target_ids.add(la.target_id)
                elif la.target:
                    laborant_kills.append(la)

            # Kimyogar (Heals or Kills)
            kimyogar_actions = [a for a in valid_actions if a.action_type == NightActionType.KIMYOGAR_POTION and a.target]
            kimyogar_kills = []
            for kma in kimyogar_actions:
                # If meta says heal or target is mafia
                if kma.metadata and kma.metadata.get('choice') == 'heal':
                    protected_target_ids.add(kma.target_id)
                else:
                    kimyogar_kills.append(kma)

            # G'azabkor marks
            gazabkor_actions = [a for a in valid_actions if a.action_type == NightActionType.GAZABKOR_MARK and a.target]
            for ga in gazabkor_actions:
                if not ga.actor.metadata:
                    ga.actor.metadata = {}
                marks = ga.actor.metadata.get('gazabkor_marked_ids', [])
                if str(ga.target_id) not in marks:
                    marks.append(str(ga.target_id))
                ga.actor.metadata['gazabkor_marked_ids'] = marks
                ga.actor.save(update_fields=['metadata'])

            # -------------------------------------------------------------
            # 4. Lethal Attack Targets Gathering
            # -------------------------------------------------------------
            lethal_hits: List[Dict[str, Any]] = []

            # Mafia / Don kill
            mafia_kills = [a for a in valid_actions if a.action_type == NightActionType.MAFIA_KILL and a.target]
            if mafia_kills:
                don_kills = [k for k in mafia_kills if k.actor.role and k.actor.role.name == 'DON']
                target_counts: Dict[str, int] = {}
                for k in mafia_kills:
                    tid = k.target_id
                    target_counts[tid] = target_counts.get(tid, 0) + 1
                max_votes = max(target_counts.values())
                top_targets = [tid for tid, cnt in target_counts.items() if cnt == max_votes]

                target_id = don_kills[0].target_id if don_kills else top_targets[0]
                actor = don_kills[0].actor if don_kills else mafia_kills[0].actor
                lethal_hits.append({'target_id': target_id, 'actor': actor, 'source': 'MAFIA'})

            # Detective / Komissar shoot
            for a in [x for x in valid_actions if x.action_type == NightActionType.DETECTIVE_SHOOT and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'KOMISSAR'})

            # Qotil kill
            for a in [x for x in valid_actions if x.action_type == NightActionType.QOTIL_KILL and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'QOTIL'})

            # Ubiytsa kill
            for a in [x for x in valid_actions if x.action_type == NightActionType.UBIYTSA_KILL and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'UBIYTSA'})

            # Robin Gud shoot
            for a in [x for x in valid_actions if x.action_type == NightActionType.ROBINGUD_SHOOT and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'ROBINGUD'})

            # Laborant poison
            for a in laborant_kills:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'LABORANT'})

            # Kimyogar poison
            for a in kimyogar_kills:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'KIMYOGAR'})

            # Axmoq headbutt (if target is Mafia -> target dies; if town -> saved)
            for a in [x for x in valid_actions if x.action_type == NightActionType.AXMOQ_VISIT and x.target]:
                if a.target.role and a.target.role.team == RoleTeam.MAFIA:
                    lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'AXMOQ'})

            # -------------------------------------------------------------
            # 5. Konchi (Miner) Mining Results
            # -------------------------------------------------------------
            konchi_actions = [a for a in valid_actions if a.action_type == NightActionType.KONCHI_MINE]
            konchi_dead = set()
            for ka in konchi_actions:
                picked_mine = (ka.metadata or {}).get('mine_index', random.randint(1, 10))
                # 3 deadly mines (1, 4, 7), 2 diamonds (2, 5), 5 dollars (3, 6, 8, 9, 10)
                if picked_mine in (1, 4, 7):
                    # Check 'sirpanish_himoya' in inventory
                    if not ka.actor.metadata:
                        ka.actor.metadata = {}
                    if not ka.actor.metadata.get('used_sirpanish_himoya'):
                        s_inv = Inventory.objects.filter(
                            telegram_id=ka.actor.telegram_user_id, item__code='sirpanish_himoya', is_active=True, quantity__gt=0
                        ).first()
                        if s_inv:
                            s_inv.quantity -= 1
                            if s_inv.quantity <= 0:
                                s_inv.is_active = False
                            s_inv.save(update_fields=['quantity', 'is_active'])
                            ka.actor.metadata['used_sirpanish_himoya'] = True
                            ka.actor.save(update_fields=['metadata'])
                            continue  # Saved by slip shield!
                    konchi_dead.add(ka.actor_id)
                elif picked_mine in (2, 5):
                    w, _ = Wallet.objects.get_or_create(telegram_id=ka.actor.telegram_user_id)
                    w.diamonds += 1
                    w.save(update_fields=['diamonds'])
                else:
                    w, _ = Wallet.objects.get_or_create(telegram_id=ka.actor.telegram_user_id)
                    w.money += Decimal(str(random.randint(20, 100)))
                    w.save(update_fields=['money'])

            # -------------------------------------------------------------
            # 6. Lethal Hits Resolution & Protections / Specials
            # -------------------------------------------------------------
            eliminated_player_ids = set()
            eliminated_players = []
            shield_saved_players = []
            omadli_saved_players = []
            sehrgar_spared_actions = []
            wolf_conversions = []

            # Check if Admiral has active Komissar/Serjant shield
            admiral_protected = any(
                p.is_alive and p.role and p.role.name in ['DETECTIVE', 'KOMISSAR', 'SERJANT']
                for p in alive_players
            )

            for hit in lethal_hits:
                tid = hit['target_id']
                if tid not in alive_player_map or tid in eliminated_player_ids:
                    continue

                target_p = alive_player_map[tid]
                actor_p = hit['actor']
                source = hit['source']

                # Doctor / Healer protected
                if tid in protected_target_ids:
                    continue

                # Admiral immunity
                if target_p.role and target_p.role.name == 'ADMIRAL' and admiral_protected:
                    continue

                # Omadli (50% random chance to survive)
                if target_p.role and target_p.role.name == 'OMADLI':
                    if random.random() < 0.5:
                        omadli_saved_players.append(target_p)
                        continue

                # Bo'ri (Wolf conversion)
                if target_p.role and target_p.role.name == 'BORI':
                    if source == 'MAFIA':
                        wolf_conversions.append((target_p, 'MAFIA'))
                        continue
                    elif source == 'KOMISSAR':
                        wolf_conversions.append((target_p, 'SERJANT'))
                        continue

                # Sehrgar (Cannot be killed by Don, Komissar, or Qotil)
                if target_p.role and target_p.role.name == 'SEHRGAR':
                    if source in ['MAFIA', 'KOMISSAR', 'QOTIL']:
                        sehrgar_spared_actions.append((target_p, actor_p))
                        continue

                # Personal Night Shield (STRICT: MAX 1 USE PER GAME)
                if not target_p.metadata:
                    target_p.metadata = {}
                if not target_p.metadata.get('used_night_shield'):
                    shield_inv = Inventory.objects.filter(
                        telegram_id=target_p.telegram_user_id, item__code='himoya', is_active=True, quantity__gt=0
                    ).first()
                    if shield_inv:
                        shield_inv.quantity -= 1
                        if shield_inv.quantity <= 0:
                            shield_inv.is_active = False
                        shield_inv.save(update_fields=['quantity', 'is_active'])
                        target_p.metadata['used_night_shield'] = True
                        target_p.save(update_fields=['metadata'])
                        shield_saved_players.append(target_p)
                        continue

                # Robin Gud shooting civilians penalty check
                if source == 'ROBINGUD' and target_p.role and target_p.role.team == RoleTeam.CIVILIAN:
                    if not actor_p.metadata:
                        actor_p.metadata = {}
                    civ_kills = actor_p.metadata.get('robin_civ_kills', 0) + 1
                    actor_p.metadata['robin_civ_kills'] = civ_kills
                    actor_p.save(update_fields=['metadata'])
                    if civ_kills >= 2:
                        # Mob stones Robin Gud to death!
                        eliminated_player_ids.add(actor_p.id)
                        eliminated_players.append(actor_p)

                # Qaroqchi 0% HP death check
                if target_p.metadata and target_p.metadata.get('hp', 100) <= 0:
                    eliminated_player_ids.add(tid)
                    eliminated_players.append(target_p)
                else:
                    eliminated_player_ids.add(tid)
                    eliminated_players.append(target_p)

            # Konchi deaths
            for kid in konchi_dead:
                if kid in alive_player_map and kid not in eliminated_player_ids:
                    p = alive_player_map[kid]
                    eliminated_player_ids.add(kid)
                    eliminated_players.append(p)

            # -------------------------------------------------------------
            # 7. G'azabkor Chain Deaths
            # -------------------------------------------------------------
            gazabkor_players = [p for p in alive_players if p.role and p.role.name == 'GAZABKOR']
            for gp in gazabkor_players:
                # If G'azabkor is dead or targeted self
                marks = (gp.metadata or {}).get('gazabkor_marked_ids', [])
                if gp.id in eliminated_player_ids or str(gp.id) in marks:
                    eliminated_player_ids.add(gp.id)
                    if gp not in eliminated_players:
                        eliminated_players.append(gp)
                    for mid in marks:
                        try:
                            mid_int = int(mid)
                            if mid_int in alive_player_map and mid_int not in eliminated_player_ids:
                                mp = alive_player_map[mid_int]
                                eliminated_player_ids.add(mid_int)
                                eliminated_players.append(mp)
                        except Exception:
                            pass

            # Mark all eliminated players as dead
            for ep in eliminated_players:
                ep.is_alive = False
                ep.save(update_fields=['is_alive'])

            # -------------------------------------------------------------
            # 8. Role Conversions & Successions
            # -------------------------------------------------------------
            # Wolf conversions
            for wp, target_role_name in wolf_conversions:
                r = Role.objects.filter(name=target_role_name).first()
                if r:
                    wp.role = r
                    wp.save(update_fields=['role'])

            # Admiral promotion (if Komissar & Serjant both dead)
            kom_alive = any(p.is_alive and p.role and p.role.name == 'DETECTIVE' for p in alive_players if p.id not in eliminated_player_ids)
            ser_alive = any(p.is_alive and p.role and p.role.name == 'SERJANT' for p in alive_players if p.id not in eliminated_player_ids)
            if not kom_alive and not ser_alive:
                admiral_p = next((p for p in alive_players if p.is_alive and p.role and p.role.name == 'ADMIRAL' and p.id not in eliminated_player_ids), None)
                if admiral_p:
                    kom_role = Role.objects.filter(name='DETECTIVE').first()
                    if kom_role:
                        admiral_p.role = kom_role
                        admiral_p.save(update_fields=['role'])

            # -------------------------------------------------------------
            # 9. Intelligence & Witness Logs (Sotqin, Fotoparatchi, Jurnalist, Aygoqchi, Daydi)
            # -------------------------------------------------------------
            sotqin_snitches = []
            sotqin_actions = [a for a in valid_actions if a.action_type == NightActionType.SOTQIN_CHECK and a.target]
            for sa in sotqin_actions:
                if sa.target and sa.target.role and (sa.target.role.team == RoleTeam.MAFIA or sa.target.role.name in ['DON', 'MAFIA', 'QOTIL', 'UBIYTSA']):
                    sotqin_snitches.append(sa.target)

            fotoparatchi_snaps = []
            fotoparatchi_actions = [a for a in valid_actions if a.action_type == NightActionType.FOTOPARATCHI_SNAP and a.target]
            for fa in fotoparatchi_actions:
                # Find if target made an action
                target_acts = [x for x in actions if x.actor_id == fa.target_id and x.target_id]
                if target_acts:
                    fotoparatchi_snaps.append((fa.target, target_acts[0].target))

            daydi_witnesses = []
            daydi_actions = [a for a in valid_actions if a.action_type == NightActionType.DAYDI_VISIT and a.target]
            for da in daydi_actions:
                if da.target_id in eliminated_player_ids:
                    # Find who killed this target
                    killers = [h['actor'] for h in lethal_hits if h['target_id'] == da.target_id]
                    if killers:
                        daydi_witnesses.append((da.actor, da.target, killers[0]))

            # -------------------------------------------------------------
            # 10. AFK Inactivity Check (Exempt passive roles)
            # -------------------------------------------------------------
            # Passive roles with no active night action: OMADLI, JANOB, BORI, SEHRGAR, ADMIRAL, CITIZEN
            PASSIVE_ROLES = {'CITIZEN', 'OMADLI', 'JANOB', 'BORI', 'SEHRGAR', 'ADMIRAL', 'HAMSHIRA', 'SUIDSID'}
            afk_eliminated = []
            acted_actor_ids = {a.actor_id for a in actions}

            for p in alive_players:
                if p.id in eliminated_player_ids:
                    continue
                rname = p.role.name if p.role else 'CITIZEN'
                if rname in PASSIVE_ROLES:
                    continue  # EXEMPT from AFK penalty!

                if p.id not in acted_actor_ids:
                    if not p.metadata:
                        p.metadata = {}
                    strikes = p.metadata.get('afk_strikes', 0) + 1
                    p.metadata['afk_strikes'] = strikes
                    p.save(update_fields=['metadata'])
                    if strikes >= 2:
                        p.is_alive = False
                        p.save(update_fields=['is_alive'])
                        afk_eliminated.append(p)
                else:
                    if p.metadata and 'afk_strikes' in p.metadata:
                        p.metadata['afk_strikes'] = 0
                        p.save(update_fields=['metadata'])

            return {
                'eliminated_players': eliminated_players,
                'shield_saved_players': shield_saved_players,
                'omadli_saved_players': omadli_saved_players,
                'sotqin_snitches': sotqin_snitches,
                'fotoparatchi_snaps': fotoparatchi_snaps,
                'daydi_witnesses': daydi_witnesses,
                'robbery_logs': robbery_logs,
                'afk_eliminated': afk_eliminated,
            }
