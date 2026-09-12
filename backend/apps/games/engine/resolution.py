from typing import Dict, Any, Optional, List
import random
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.games.models import (
    Game, Player, NightAction, NightActionType, Vote, RoleTeam, RoleType, Role
)
from apps.economy.models import Inventory, Wallet, WalletTransaction, TransactionType, CurrencyType, PlayerHero
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
            alive_player_map.update({str(p.id): p for p in alive_players})

            # -------------------------------------------------------------
            # 1. Blockers & Role Alterations (Kezuvchi, Aferist, Oshpaz)
            # -------------------------------------------------------------
            blocked_actor_ids = set()
            kezuvchi_blocked_players = []
            kezuvchi_visited_players = []
            dori_shield_saved_players = []

            # Kezuvchi
            kezuvchi_actions = [a for a in actions if a.action_type == NightActionType.KEZUVCHI_VISIT and a.target]
            for ka in kezuvchi_actions:
                if ka.target_id in alive_player_map:
                    target_p = alive_player_map[ka.target_id]
                    kezuvchi_visited_players.append(target_p)
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
            aferist_stolen_players = []
            for aa in aferist_actions:
                if aa.target_id in alive_player_map:
                    target_p = alive_player_map[aa.target_id]
                    if not target_p.metadata:
                        target_p.metadata = {}
                    target_p.metadata['blocked_voting_round'] = game.round_number
                    target_p.metadata['aferist_proxy_voter_id'] = str(aa.actor_id)
                    target_p.save(update_fields=['metadata'])
                    aferist_stolen_players.append(target_p)

            # Oshpaz (Dizzy meal -> scrambles vote tomorrow)
            oshpaz_actions = [a for a in actions if a.action_type == NightActionType.OSHPAZ_FEED and a.target]
            oshpaz_feed_players = []
            for oa in oshpaz_actions:
                if oa.target_id in alive_player_map:
                    target_p = alive_player_map[oa.target_id]
                    if not target_p.metadata:
                        target_p.metadata = {}
                    target_p.metadata['dizzy_voting_round'] = game.round_number
                    target_p.save(update_fields=['metadata'])
                    oshpaz_feed_players.append(target_p)

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
            rais_gifts = []
            for ra in rais_actions:
                if ra.target_id in alive_player_map:
                    target_p = alive_player_map[ra.target_id]
                    gift_amount = Decimal(str(random.randint(1, 100)))
                    t_wallet, _ = Wallet.objects.get_or_create(telegram_id=target_p.telegram_user_id)
                    t_wallet.money += gift_amount
                    t_wallet.save(update_fields=['money'])
                    rais_gifts.append({
                        'target_user_id': target_p.telegram_user_id,
                        'coins': int(gift_amount),
                        'diamonds': 0,
                    })

            # Qorbobo (Gift random item)
            qorbobo_actions = [a for a in valid_actions if a.action_type == NightActionType.QORBOBO_GIFT and a.target]
            qorbobo_gifts = []
            for qba in qorbobo_actions:
                if qba.target_id in alive_player_map:
                    target_p = alive_player_map[qba.target_id]
                    from apps.economy.models import MarketplaceItem
                    gift_codes = ['himoya', 'osish_himoya', 'hujjat', 'dori_himoya', 'sirpanish_himoya']
                    picked_code = random.choice(gift_codes)
                    item = MarketplaceItem.objects.filter(code=picked_code).first()
                    item_title = item.name if item else "Tungi himoya"
                    if item:
                        inv, _ = Inventory.objects.get_or_create(
                            telegram_id=target_p.telegram_user_id, item=item,
                            defaults={'quantity': 0, 'is_active': True}
                        )
                        inv.quantity += 1
                        inv.is_active = True
                        inv.save(update_fields=['quantity', 'is_active'])
                    qorbobo_gifts.append({
                        'actor_user_id': qba.actor.telegram_user_id,
                        'target': target_p,
                        'target_user_id': target_p.telegram_user_id,
                        'target_name': target_p.display_name,
                        'item_name': item_title,
                        'item_code': picked_code,
                    })

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
            kimyogar_healed_players = []
            for kma in kimyogar_actions:
                if kma.metadata and kma.metadata.get('choice') == 'heal':
                    protected_target_ids.add(kma.target_id)
                    if kma.target_id in alive_player_map:
                        kimyogar_healed_players.append(alive_player_map[kma.target_id])
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
            # 4. Detective / Komissar Investigations
            # -------------------------------------------------------------
            investigation_results = []
            hujjat_used_players = []
            detective_checks = [a for a in valid_actions if a.action_type == NightActionType.DETECTIVE_INVESTIGATE and a.target]
            for dc in detective_checks:
                if dc.target_id in alive_player_map:
                    target_p = alive_player_map[dc.target_id]
                    # Check if target has Hujjat (fake document)
                    has_fake_doc = False
                    if not target_p.metadata:
                        target_p.metadata = {}
                    if not target_p.metadata.get('used_hujjat'):
                        hujjat_inv = Inventory.objects.filter(
                            telegram_id=target_p.telegram_user_id, item__code='hujjat', is_active=True, quantity__gt=0
                        ).first()
                        if hujjat_inv:
                            hujjat_inv.quantity -= 1
                            if hujjat_inv.quantity <= 0:
                                hujjat_inv.is_active = False
                            hujjat_inv.save(update_fields=['quantity', 'is_active'])
                            target_p.metadata['used_hujjat'] = True
                            target_p.save(update_fields=['metadata'])
                            has_fake_doc = True
                            hujjat_used_players.append(target_p)

                    # Target appears innocent if DON, protected by ADVOKAT, or has fake document
                    is_mafia_role = (
                        target_p.role and target_p.role.team == RoleTeam.MAFIA
                        and target_p.role.name not in ['DON']
                        and target_p.id not in advokat_protected_ids
                        and not has_fake_doc
                    )
                    role_to_show = 'CITIZEN' if (has_fake_doc or target_p.id in advokat_protected_ids) else (target_p.role.name if target_p.role else 'CITIZEN')
                    investigation_results.append({
                        'actor_id': dc.actor_id,
                        'detective_user_id': dc.actor.telegram_user_id,
                        'target_id': target_p.id,
                        'target_display_name': target_p.display_name,
                        'is_mafia': is_mafia_role,
                        'role_name': role_to_show,
                    })

            # -------------------------------------------------------------
            # 5. Lethal Attack Targets Gathering
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
                lethal_hits.append({'target_id': target_id, 'actor': actor, 'source': 'MAFIA', 'killer_type': 'mafia'})

            # Detective / Komissar shoot
            for a in [x for x in valid_actions if x.action_type == NightActionType.DETECTIVE_SHOOT and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'KOMISSAR', 'killer_type': 'komissar'})

            # Qotil kill
            for a in [x for x in valid_actions if x.action_type == NightActionType.QOTIL_KILL and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'QOTIL', 'killer_type': 'qotil'})

            # Ubiytsa kill
            for a in [x for x in valid_actions if x.action_type == NightActionType.UBIYTSA_KILL and x.target]:
                # If target is Komissar, Ubiytsa dies instead!
                if a.target and a.target.role and a.target.role.name in ['DETECTIVE', 'KOMISSAR']:
                    lethal_hits.append({'target_id': a.actor_id, 'actor': a.target, 'source': 'KOMISSAR', 'killer_type': 'komissar_retaliate'})
                else:
                    lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'UBIYTSA', 'killer_type': 'ubiytsa'})

            # Robin Gud shoot
            for a in [x for x in valid_actions if x.action_type == NightActionType.ROBINGUD_SHOOT and x.target]:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'ROBINGUD', 'killer_type': 'robingud'})

            # Laborant poison
            for a in laborant_kills:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'LABORANT', 'killer_type': 'laborant'})

            # Kimyogar poison
            for a in kimyogar_kills:
                lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'KIMYOGAR', 'killer_type': 'kimyogar_poison'})

            # Axmoq headbutt (if target is Mafia -> target dies; if town -> saved)
            for a in [x for x in valid_actions if x.action_type == NightActionType.AXMOQ_VISIT and x.target]:
                if a.target and a.target.role and a.target.role.team == RoleTeam.MAFIA:
                    lethal_hits.append({'target_id': a.target_id, 'actor': a.actor, 'source': 'AXMOQ', 'killer_type': 'axmoq_headbutt'})

            # Tuzoqchi: anyone visiting a trapped player gets caught
            for act in valid_actions:
                if act.target_id in trapped_player_ids and act.actor_id != trapped_player_ids[act.target_id].id:
                    lethal_hits.append({'target_id': act.actor_id, 'actor': trapped_player_ids[act.target_id], 'source': 'TUZOQCHI', 'killer_type': 'tuzoqchi'})

            # -------------------------------------------------------------
            # 6. Konchi (Miner) Mining Results
            # -------------------------------------------------------------
            konchi_actions = [a for a in valid_actions if a.action_type == NightActionType.KONCHI_MINE]
            konchi_dead = set()
            konchi_results = []
            for ka in konchi_actions:
                picked_mine = (ka.metadata or {}).get('mine_index', random.randint(1, 10))
                if picked_mine in (1, 4, 7):
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
                            konchi_results.append({
                                'actor': ka.actor,
                                'user_id': ka.actor.telegram_user_id,
                                'mine': picked_mine,
                                'status': 'saved_by_slip_shield',
                            })
                            continue  # Saved by slip shield!
                    konchi_dead.add(ka.actor_id)
                    konchi_results.append({
                        'actor': ka.actor,
                        'user_id': ka.actor.telegram_user_id,
                        'mine': picked_mine,
                        'status': 'died',
                    })
                elif picked_mine in (2, 5):
                    w, _ = Wallet.objects.get_or_create(telegram_id=ka.actor.telegram_user_id)
                    w.diamonds += 1
                    w.save(update_fields=['diamonds'])
                    konchi_results.append({
                        'actor': ka.actor,
                        'user_id': ka.actor.telegram_user_id,
                        'mine': picked_mine,
                        'status': 'diamond',
                        'diamonds': 1,
                    })
                else:
                    coins_gained = random.randint(20, 100)
                    w, _ = Wallet.objects.get_or_create(telegram_id=ka.actor.telegram_user_id)
                    w.money += Decimal(str(coins_gained))
                    w.save(update_fields=['money'])
                    konchi_results.append({
                        'actor': ka.actor,
                        'user_id': ka.actor.telegram_user_id,
                        'mine': picked_mine,
                        'status': 'money',
                        'coins': coins_gained,
                    })

            # -------------------------------------------------------------
            # 7. Lethal Hits Resolution & Protections / Specials
            # -------------------------------------------------------------
            eliminated_player_ids = set()
            eliminated_dict_list: List[Dict[str, Any]] = []
            protected_hits_set = set()
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
                ktype = hit.get('killer_type', 'mafia')

                # Doctor / Healer protected
                if tid in protected_target_ids:
                    protected_hits_set.add(tid)
                    continue

                # Afsungar counter-attack (attacker dies instead)
                if target_p.role and target_p.role.name == 'AFSUNGAR' and actor_p and actor_p.id != target_p.id:
                    if actor_p.id not in eliminated_player_ids:
                        eliminated_player_ids.add(actor_p.id)
                        eliminated_dict_list.append({
                            'player': actor_p,
                            'role_name': actor_p.role.name if actor_p.role else 'CITIZEN',
                            'killer_type': 'afsungar'
                        })
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

                # Universal 🖤 Himoya (Player's Hero Defense Points)
                hero = PlayerHero.objects.filter(telegram_id=target_p.telegram_user_id, is_active=True).first()
                if hero and hero.current_defense > 0:
                    hero.current_defense -= 1
                    hero.save(update_fields=['current_defense'])
                    shield_saved_players.append(target_p)
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
                        eliminated_player_ids.add(actor_p.id)
                        eliminated_dict_list.append({
                            'player': actor_p,
                            'role_name': actor_p.role.name if actor_p.role else 'CITIZEN',
                            'killer_type': 'town_stoned'
                        })

                # Target eliminated
                eliminated_player_ids.add(tid)
                eliminated_dict_list.append({
                    'player': target_p,
                    'role_name': target_p.role.name if target_p.role else 'CITIZEN',
                    'killer_type': ktype
                })

            # Konchi deaths
            for kid in konchi_dead:
                if kid in alive_player_map and kid not in eliminated_player_ids:
                    p = alive_player_map[kid]
                    eliminated_player_ids.add(kid)
                    eliminated_dict_list.append({
                        'player': p,
                        'role_name': p.role.name if p.role else 'KONCHI',
                        'killer_type': 'mine_explosion'
                    })

            # -------------------------------------------------------------
            # 8. G'azabkor Chain Deaths
            # -------------------------------------------------------------
            gazabkor_players = [p for p in alive_players if p.role and p.role.name == 'GAZABKOR']
            for gp in gazabkor_players:
                marks = (gp.metadata or {}).get('gazabkor_marked_ids', [])
                if gp.id in eliminated_player_ids or str(gp.id) in marks:
                    if gp.id not in eliminated_player_ids:
                        eliminated_player_ids.add(gp.id)
                        eliminated_dict_list.append({
                            'player': gp,
                            'role_name': gp.role.name if gp.role else 'GAZABKOR',
                            'killer_type': 'gazabkor'
                        })
                    for mid in marks:
                        try:
                            mid_key = mid if mid in alive_player_map else str(mid)
                            if mid_key in alive_player_map:
                                mp = alive_player_map[mid_key]
                                if mp.id not in eliminated_player_ids and str(mp.id) not in eliminated_player_ids:
                                    eliminated_player_ids.add(mp.id)
                                    eliminated_player_ids.add(str(mp.id))
                                    eliminated_dict_list.append({
                                        'player': mp,
                                        'role_name': mp.role.name if mp.role else 'CITIZEN',
                                        'killer_type': 'gazabkor_chain'
                                    })
                        except Exception:
                            pass

            # Mark all eliminated players as dead
            for item in eliminated_dict_list:
                ep = item['player']
                ep.is_alive = False
                ep.save(update_fields=['is_alive'])

            # -------------------------------------------------------------
            # 9. Role Conversions & Successions
            # -------------------------------------------------------------
            # Wolf conversions
            for wp, target_role_name in wolf_conversions:
                r = Role.objects.filter(name=target_role_name).first()
                if r:
                    wp.role = r
                    wp.save(update_fields=['role'])

            # Successions
            new_don = None
            don_alive = any(p.is_alive and p.role and p.role.name == 'DON' for p in alive_players if p.id not in eliminated_player_ids)
            if not don_alive:
                living_mafias = [p for p in alive_players if p.is_alive and p.id not in eliminated_player_ids and p.role and p.role.name == 'MAFIA']
                if living_mafias:
                    chosen_mafia = random.choice(living_mafias)
                    don_role = Role.objects.filter(name='DON').first()
                    if don_role:
                        chosen_mafia.role = don_role
                        chosen_mafia.save(update_fields=['role'])
                        new_don = chosen_mafia

            new_komissar = None
            kom_alive = any(p.is_alive and p.role and p.role.name in ['DETECTIVE', 'KOMISSAR'] for p in alive_players if p.id not in eliminated_player_ids)
            if not kom_alive:
                ser_p = next((p for p in alive_players if p.is_alive and p.id not in eliminated_player_ids and p.role and p.role.name == 'SERJANT'), None)
                if not ser_p:
                    ser_p = next((p for p in alive_players if p.is_alive and p.id not in eliminated_player_ids and p.role and p.role.name == 'ADMIRAL'), None)
                if ser_p:
                    kom_role = Role.objects.filter(name='DETECTIVE').first()
                    if kom_role:
                        ser_p.role = kom_role
                        ser_p.save(update_fields=['role'])
                        new_komissar = ser_p

            new_doctor = None
            doc_alive = any(p.is_alive and p.role and p.role.name in ['DOCTOR', 'SHIFOKOR'] for p in alive_players if p.id not in eliminated_player_ids)
            if not doc_alive:
                ham_p = next((p for p in alive_players if p.is_alive and p.id not in eliminated_player_ids and p.role and p.role.name == 'HAMSHIRA'), None)
                if ham_p:
                    doc_role = Role.objects.filter(name='DOCTOR').first()
                    if doc_role:
                        ham_p.role = doc_role
                        ham_p.save(update_fields=['role'])
                        new_doctor = ham_p

            # -------------------------------------------------------------
            # 10. Intelligence & Witness Logs (Sotqin, Fotoparatchi, Daydi)
            # -------------------------------------------------------------
            sotqin_snitches = []
            sotqin_actions = [a for a in valid_actions if a.action_type == NightActionType.SOTQIN_CHECK and a.target]
            for sa in sotqin_actions:
                if sa.target and sa.target.role and (sa.target.role.team == RoleTeam.MAFIA or sa.target.role.name in ['DON', 'MAFIA', 'QOTIL', 'UBIYTSA']):
                    sotqin_snitches.append(sa.target)

            fotoparatchi_snaps = []
            fotoparatchi_actions = [a for a in valid_actions if a.action_type == NightActionType.FOTOPARATCHI_SNAP and a.target]
            for fa in fotoparatchi_actions:
                target_acts = [x for x in actions if x.actor_id == fa.target_id and x.target_id]
                if target_acts:
                    fotoparatchi_snaps.append((fa.target, target_acts[0].target))

            daydi_witnesses = []
            daydi_results = []
            daydi_visited_players = []
            daydi_actions = [a for a in valid_actions if a.action_type == NightActionType.DAYDI_VISIT and a.target]
            for da in daydi_actions:
                if da.target_id in alive_player_map:
                    daydi_visited_players.append(alive_player_map[da.target_id])
                if da.target_id in eliminated_player_ids:
                    killers = [h['actor'] for h in lethal_hits if h['target_id'] == da.target_id]
                    if killers:
                        daydi_witnesses.append((da.actor, da.target, killers[0]))
                        daydi_results.append({
                            'daydi_user_id': da.actor.telegram_user_id,
                            'message': f"🍾 <b>Daydi guvohligi:</b> Siz borgan xonadonda {html.escape(da.target.display_name)} o'ldirildi. Qotil: {html.escape(killers[0].display_name)}!",
                        })

            aygoqchi_spies = []
            aygoqchi_actions = [a for a in valid_actions if a.action_type == NightActionType.AYGOQCHI_SPY and a.target]
            for aa in aygoqchi_actions:
                if aa.target:
                    rname = aa.target.role.name if aa.target.role else 'CITIZEN'
                    aygoqchi_spies.append({
                        'actor_user_id': aa.actor.telegram_user_id,
                        'target': aa.target,
                        'target_user_id': aa.target.telegram_user_id,
                        'target_name': aa.target.display_name,
                        'role_name': rname,
                    })

            jurnalist_reports = []
            jurnalist_actions = [a for a in valid_actions if a.action_type == NightActionType.JURNALIST_INVESTIGATE and a.target]
            for ja in jurnalist_actions:
                if ja.target:
                    visitors = [x.actor for x in actions if x.target_id == ja.target_id and x.actor_id != ja.actor_id]
                    jurnalist_reports.append({
                        'actor_user_id': ja.actor.telegram_user_id,
                        'target': ja.target,
                        'target_name': ja.target.display_name,
                        'visitors': visitors,
                    })

            # -------------------------------------------------------------
            # 11. Zombie Infections & Joker
            # -------------------------------------------------------------
            infected_players = []
            zombi_actions = [a for a in valid_actions if a.action_type == NightActionType.ZOMBI_BITE and a.target]
            for za in zombi_actions:
                if za.target_id in alive_player_map and za.target_id not in eliminated_player_ids:
                    infected_p = alive_player_map[za.target_id]
                    z_role = Role.objects.filter(name='ZOMBI').first()
                    if z_role:
                        infected_p.role = z_role
                        infected_p.save(update_fields=['role'])
                        infected_players.append(infected_p)

            joker_deliveries = []
            joker_actions = [a for a in valid_actions if a.action_type == NightActionType.JOKER_BOXES and a.target]
            for ja in joker_actions:
                if ja.target_id in alive_player_map and ja.target_id not in eliminated_player_ids:
                    joker_deliveries.append({'target_user_id': ja.target.telegram_user_id})

            # -------------------------------------------------------------
            # 12. AFK Inactivity Check (Exempt passive roles & Mafia when Don is alive)
            # -------------------------------------------------------------
            PASSIVE_ROLES = {'CITIZEN', 'OMADLI', 'JANOB', 'BORI', 'SEHRGAR', 'ADMIRAL', 'HAMSHIRA', 'SUIDSID'}
            afk_eliminated = []
            acted_actor_ids = {a.actor_id for a in actions}
            don_alive_in_game = any(p.is_alive and p.role and p.role.name == 'DON' for p in alive_players if p.id not in eliminated_player_ids)

            for p in alive_players:
                if p.id in eliminated_player_ids:
                    continue
                rname = p.role.name if p.role else 'CITIZEN'
                if rname in PASSIVE_ROLES:
                    continue  # EXEMPT from AFK penalty

                # Regular MAFIA is exempt from AFK penalty as long as DON is alive
                if rname == 'MAFIA' and don_alive_in_game:
                    continue

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
                'eliminated_players': eliminated_dict_list,
                'eliminated_player': eliminated_dict_list[0]['player'] if eliminated_dict_list else None,
                'eliminated_role_name': eliminated_dict_list[0]['role_name'] if eliminated_dict_list else None,
                'saved_by_doctor': len(protected_hits_set) > 0,
                'shield_saved_players': shield_saved_players,
                'omadli_saved_players': omadli_saved_players,
                'doctor_saved_players': [alive_player_map[tid] for tid in protected_hits_set if tid in alive_player_map],
                'doctor_visited_players': [alive_player_map[a.target_id] for a in doctor_protects if a.target_id in alive_player_map],
                'kezuvchi_visited_players': kezuvchi_visited_players,
                'daydi_visited_players': daydi_visited_players,
                'advokat_visited_players': [alive_player_map[a.target_id] for a in advokat_actions if a.target_id in alive_player_map],
                'kimyogar_healed_players': kimyogar_healed_players,
                'dori_shield_saved_players': dori_shield_saved_players,
                'hujjat_used_players': hujjat_used_players,
                'investigation_results': investigation_results,
                'daydi_results': daydi_results,
                'rais_gifts': rais_gifts,
                'qorbobo_gifts': qorbobo_gifts,
                'konchi_results': konchi_results,
                'aferist_stolen_players': aferist_stolen_players,
                'oshpaz_feed_players': oshpaz_feed_players,
                'aygoqchi_spies': aygoqchi_spies,
                'jurnalist_reports': jurnalist_reports,
                'joker_deliveries': joker_deliveries,
                'infected_players': infected_players,
                'new_don': new_don,
                'new_komissar': new_komissar,
                'new_doctor': new_doctor,
                'sotqin_snitches': sotqin_snitches,
                'fotoparatchi_snaps': fotoparatchi_snaps,
                'daydi_witnesses': daydi_witnesses,
                'robbery_logs': robbery_logs,
                'afk_eliminated_players': afk_eliminated,
                'afk_eliminated': afk_eliminated,
                'doctor_actions_results': [
                    {
                        'doctor_user_id': a.actor.telegram_user_id,
                        'target_id': a.target_id,
                        'target_name': a.target.display_name if a.target else "O'yinchi",
                        'is_saved': a.target_id in protected_hits_set
                    }
                    for a in doctor_protects if a.actor and a.target
                ],
            }

    @classmethod
    def resolve_voting_phase(cls, game: Game) -> Dict[str, Any]:
        """
        Resolves voting phase for the current round:
        Counts votes, handles ties, Janob weight, Aferist proxies, shields, and eliminates suspect.
        """
        with transaction.atomic():
            votes = list(Vote.objects.filter(game=game, round=game.round_number).select_related('voter', 'target', 'target__role', 'voter__role'))
            alive_players = list(Player.objects.filter(game=game, is_alive=True).select_related('role'))
            alive_map = {p.id: p for p in alive_players}

            vote_counts: Dict[Any, int] = {}
            for v in votes:
                if v.voter_id not in alive_map or v.target_id not in alive_map:
                    continue
                # Weight Janob vote as 2
                weight = 2 if v.voter.role and v.voter.role.name == 'JANOB' else 1
                vote_counts[v.target_id] = vote_counts.get(v.target_id, 0) + weight

            if not vote_counts:
                return {
                    'eliminated_player': None,
                    'eliminated_role_name': None,
                    'is_tie': True,
                    'vote_counts': vote_counts,
                }

            max_votes = max(vote_counts.values())
            top_targets = [tid for tid, cnt in vote_counts.items() if cnt == max_votes]

            if len(top_targets) > 1:
                return {
                    'eliminated_player': None,
                    'eliminated_role_name': None,
                    'is_tie': True,
                    'vote_counts': vote_counts,
                }

            elim_id = top_targets[0]
            elim_player = alive_map[elim_id]

            # Check universal 🖤 Himoya (PlayerHero current_defense)
            hero = PlayerHero.objects.filter(telegram_id=elim_player.telegram_user_id, is_active=True).first()
            if hero and hero.current_defense > 0:

                hero.current_defense -= 1
                hero.save(update_fields=['current_defense'])
                return {
                    'eliminated_player': None,
                    'eliminated_role_name': None,
                    'saved_by_shield': True,
                    'saved_by_hero_defense': True,
                    'is_tie': False,
                    'vote_counts': vote_counts,
                }

            # Check 'osish_himoya' item in Inventory
            if not elim_player.metadata:
                elim_player.metadata = {}
            saved_by_shield = False
            if not elim_player.metadata.get('used_osish_himoya'):
                shield_inv = Inventory.objects.filter(
                    telegram_id=elim_player.telegram_user_id, item__code='osish_himoya', is_active=True, quantity__gt=0
                ).first()
                if shield_inv:
                    shield_inv.quantity -= 1
                    if shield_inv.quantity <= 0:
                        shield_inv.is_active = False
                    shield_inv.save(update_fields=['quantity', 'is_active'])
                    elim_player.metadata['used_osish_himoya'] = True
                    elim_player.save(update_fields=['metadata'])
                    saved_by_shield = True

            if saved_by_shield:
                return {
                    'eliminated_player': None,
                    'eliminated_role_name': None,
                    'saved_by_shield': True,
                    'is_tie': False,
                    'vote_counts': vote_counts,
                }


            suicide_won = bool(elim_player.role and elim_player.role.name in ['SUIDSID', 'SUITSID'])
            if suicide_won:
                if not elim_player.metadata:
                    elim_player.metadata = {}
                elim_player.metadata['hanged_as_suicide'] = True
                elim_player.save(update_fields=['metadata'])

            elim_player.is_alive = False
            elim_player.save(update_fields=['is_alive'])

            # Don lynched -> promotion to living Mafia
            if elim_player.role and elim_player.role.name == 'DON':
                living_mafias = [p for p in alive_players if p.id != elim_player.id and p.is_alive and p.role and p.role.name == 'MAFIA']
                if living_mafias:
                    chosen_mafia = random.choice(living_mafias)
                    don_role = Role.objects.filter(name='DON').first()
                    if don_role:
                        chosen_mafia.role = don_role
                        chosen_mafia.save(update_fields=['role'])

            return {
                'eliminated_player': elim_player,
                'eliminated_role_name': elim_player.role.name if elim_player.role else 'CITIZEN',
                'is_tie': False,
                'suicide_won': suicide_won,
                'vote_counts': vote_counts,
            }
