"""
MAFIA BOT FATHER — Voting Phase Handlers (Full Game Loop)
==========================================================
- PM-based voting (each player gets keyboard in DM)
- Group shows live vote log
- auto_close_voting(): called after 20s, processes results
- "Rostdan ham X ni osmoqchimisiz?" confirmation in GROUP (20s)
- End-game: winner announced + PM to each player

CALLBACK DATA (under 64 bytes):
  Vote:     v:{game12}:{player12}
  Hanging:  hg:{game12}:kill:{player12}  /  hg:{game12}:save:{player12}
"""
import html
import asyncio
import random
import logging
from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.games.models import Game, Player, GamePhase, RoleTeam
from apps.games.engine.voting import VotingService, VoteValidationError
from apps.games.engine.game_service import GameService
from apps.games.engine.win_conditions import WinConditionService
from apps.superadmin.services import TextService
from bot_runtime.manager import safe_send_message
from bot_runtime.keyboards.inline import (
    build_night_target_keyboard,
    build_hanging_keyboard,
    build_bot_pm_keyboard,
    build_komissar_action_keyboard,
    _player_team_badge,
    _player_health_badge,
    _short,
)

logger = logging.getLogger(__name__)
router = Router(name="voting_router")

# In-memory hanging confirmation
# HANGING_VOTES[game_id] = {kill, save, voters, target, message}
HANGING_VOTES: dict = {}
HANGING_TASKS: dict = {}
CLOSING_VOTING_GAMES: set = set()


# ---------------------------------------------------------------------------
# Helpers: reverse UUID lookup (shared with night.py)
# ---------------------------------------------------------------------------

async def _resolve_game(short_gid: str) -> Game:
    """Resolve 12-char game prefix to Game object."""
    from bot_runtime.handlers.night import GAME_ID_MAP, _resolve_game_id
    full_gid = await _resolve_game_id(short_gid)
    return await sync_to_async(Game.objects.select_related('bot').get)(id=full_gid)


async def _resolve_player(game: Game, short_pid: str) -> Player:
    """Resolve 12-char player prefix to Player object."""
    from bot_runtime.handlers.night import _resolve_player_id
    full_pid = await _resolve_player_id(game, short_pid)
    return await sync_to_async(Player.objects.select_related('role').get)(game=game, id=full_pid)


# ---------------------------------------------------------------------------
# Vote callback (prefix: v:{game12}:{player12})
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and c.data.startswith("v:"))
async def handle_vote_callback(callback: CallbackQuery, bot: Bot):
    """Handles PM voting button clicks."""
    parts = callback.data.split(":")
    short_gid = parts[1]
    short_pid = parts[2]

    try:
        game = await _resolve_game(short_gid)
        if game.phase != GamePhase.VOTING:
            await callback.answer("⚖️ Ovoz berish bosqichi yopiq.", show_alert=True)
            return

        voter = await sync_to_async(
            lambda: Player.objects.get(game=game, telegram_user_id=callback.from_user.id)
        )()
        if not voter.is_alive:
            await callback.answer("❌ O'yindan chiqqanlar ovoz bera olmaydi.", show_alert=True)
            return

        # Check if voter's vote was stolen by Aferist or blocked by Kezuvchi
        if voter.metadata and voter.metadata.get('blocked_voting_round') == game.round_number:
            if voter.metadata.get('aferist_proxy_voter_id'):
                await callback.answer("❌ Aferist sizning ovozingizni o'g'irlagan! Bugun ovoz bera olmaysiz.", show_alert=True)
            else:
                await callback.answer("❌ Siz bu raundda ovoz bera olmaysiz (Dori/Blok ta'sirida).", show_alert=True)
            return

        target = await _resolve_player(game, short_pid)
        if not target.is_alive:
            await callback.answer("❌ Bu o'yinchi allaqachon tirik emas.", show_alert=True)
            return

        # Check Oshpaz dizzy effect (randomly redirect to another player)
        actual_target = target
        is_dizzy = False
        if voter.metadata and voter.metadata.get('dizzy_voting_round') == game.round_number:
            alive_other = await sync_to_async(lambda: list(game.players.filter(is_alive=True).exclude(id=voter.id)))()
            if alive_other:
                actual_target = random.choice(alive_other)
                is_dizzy = True

        await sync_to_async(VotingService.submit_vote)(game, voter, actual_target)

        voter_mention = f'{_player_team_badge(voter)}<a href="tg://user?id={voter.telegram_user_id}">{html.escape(voter.display_name)}</a>{_player_health_badge(voter)}'
        target_mention = f'{_player_team_badge(actual_target)}<a href="tg://user?id={actual_target.telegram_user_id}">{html.escape(actual_target.display_name)}</a>{_player_health_badge(actual_target)}'

        if is_dizzy:
            await callback.answer("😵 Boshingiz aylanib, boshqa odamga ovoz ketdi!", show_alert=True)
        else:
            await callback.answer(f"✅ {_player_team_badge(actual_target)}{actual_target.display_name} ga ovoz berdingiz!")

        try:
            await callback.message.edit_text(
                f"✅ <b>Ovozingiz qabul qilindi!</b>\n\n"
                f"Siz <b>{_player_team_badge(actual_target)}{html.escape(actual_target.display_name)}</b> ga ovoz berdingiz.\n"
                f"Natijani kuting...",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Live vote log in group (Janob has hidden identity)
        group_voter_label = voter_mention
        if voter.role and voter.role.name == 'JANOB':
            group_voter_label = f"🎖 {_player_team_badge(voter)}<b>Janob</b>"

        try:
            await bot.send_message(
                game.chat_id,
                f"⚖️ {group_voter_label} ➡️ {target_mention} ga ovoz berdi!",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Check if all voted → close early
        living_count = await sync_to_async(lambda: game.players.filter(is_alive=True).count())()
        cast_count = await sync_to_async(lambda: game.votes.filter(round=game.round_number).count())()

        if cast_count >= living_count:
            logger.info(f"All {living_count} voted in game {game.id}. Closing early.")
            from bot_runtime.handlers.night import VOTING_TASKS
            task = VOTING_TASKS.pop(str(game.id), None) or HANGING_TASKS.pop(f"vote_{game.id}", None)
            if task and not task.done():
                task.cancel()
            await auto_close_voting(game, bot)

    except (Game.DoesNotExist, Player.DoesNotExist):
        await callback.answer("O'yin yoki o'yinchi topilmadi.", show_alert=True)
    except VoteValidationError as ve:
        await callback.answer(str(ve), show_alert=True)
    except Exception as e:
        logger.exception("Error in vote callback:")
        await callback.answer(f"Xatolik: {str(e)}", show_alert=True)


# ---------------------------------------------------------------------------
# Hanging confirmation callback (prefix: hg:{game12}:kill:{player12})
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and c.data.startswith("hg:"))
async def handle_hanging_callback(callback: CallbackQuery, bot: Bot):
    """Handles hanging confirmation (Xa/Yo'q) in group."""
    parts = callback.data.split(":")
    short_gid = parts[1]
    choice = parts[2]       # 'kill' or 'save'
    short_pid = parts[3]

    game_id_key = None
    h_data = None

    for gid_str, data in HANGING_VOTES.items():
        if _short(gid_str) == short_gid or gid_str.startswith(short_gid):
            game_id_key = gid_str
            h_data = data
            break

    if not h_data:
        await callback.answer("⚖️ Tasdiqlash bosqichi yakunlangan.", show_alert=True)
        return

    voter_id = callback.from_user.id
    suspect = h_data['target']

    if voter_id == suspect.telegram_user_id:
        await callback.answer("❌ Siz o'zingizni osish bo'yicha ovoz bera olmaysiz!", show_alert=True)
        return

    try:
        voter = await sync_to_async(
            lambda: Player.objects.get(game__id=game_id_key, telegram_user_id=voter_id, is_alive=True)
        )()
    except Player.DoesNotExist:
        await callback.answer("❌ Siz tirik o'yinchi emassiz.", show_alert=True)
        return

    if voter_id in h_data['voters']:
        await callback.answer("⚠️ Siz allaqachon ovoz berdingiz!", show_alert=True)
        return

    h_data['voters'].add(voter_id)
    if choice == 'kill':
        h_data['kill'] += 1
        await callback.answer("🩸 Osish uchun ovoz berdingiz!")
    else:
        h_data['save'] += 1
        await callback.answer("🕊️ Afv etish uchun ovoz berdingiz!")

    kill_c = h_data['kill']
    save_c = h_data['save']
    suspect_mention = f'{_player_team_badge(suspect)}<a href="tg://user?id={suspect.telegram_user_id}">{html.escape(suspect.display_name)}</a>'

    try:
        bot_info = await bot.get_me()
        prompt_tpl = await sync_to_async(TextService.get_text)(
            'hanging_prompt_text',
            fallback="<b>{bot_name}</b>               <code>BM Admin</code>\n<b>Rostdan ham {target_name}ni osmoqchimisiz?</b>"
        )
        prompt_text = (
            prompt_tpl.replace('{bot_name}', html.escape(bot_info.first_name))
            .replace('{target_name}', suspect_mention)
        )
        await callback.message.edit_text(
            prompt_text,
            reply_markup=build_hanging_keyboard(game_id_key, str(suspect.id), kill_count=kill_c, save_count=save_c),
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        total_living = await sync_to_async(
            lambda: Player.objects.filter(game__id=game_id_key, is_alive=True).count()
        )()
        if len(h_data['voters']) >= max(1, total_living - 1):
            task = HANGING_TASKS.pop(game_id_key, None)
            if task and not task.done():
                task.cancel()
            game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id_key)
            await resolve_hanging(game, bot, callback.message)
    except Exception as e:
        logger.warning(f"Error checking hanging count: {e}")


# ---------------------------------------------------------------------------
# Core: auto_close_voting
# ---------------------------------------------------------------------------

async def auto_close_voting(game: Game, bot: Bot):
    """Tallies votes, announces result, starts hanging confirmation."""
    game_id = str(game.id)
    if game_id in CLOSING_VOTING_GAMES or game_id in HANGING_VOTES:
        logger.info(f"Game {game_id} is already closing voting or hanging prompt is active.")
        return
    CLOSING_VOTING_GAMES.add(game_id)
    try:
        from bot_runtime.manager import BotRuntimeManager
        bot = BotRuntimeManager.get_bot_for_game(game, bot)

        from bot_runtime.handlers.night import VOTING_TASKS
        task = VOTING_TASKS.pop(game_id, None) or HANGING_TASKS.pop(f"vote_{game.id}", None)
        if task and not task.done():
            task.cancel()

        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game.id)
        if game.phase != GamePhase.VOTING:
            return

        votes = await sync_to_async(
            lambda: list(game.votes.filter(round=game.round_number).select_related('voter', 'target'))
        )()

        counts: dict = {}
        target_map: dict = {}
        for v in votes:
            tid = str(v.target_id)
            counts[tid] = counts.get(tid, 0) + 1
            target_map[tid] = v.target

        tally_lines = [
            f'• {_player_team_badge(target_map[tid])}<a href="tg://user?id={target_map[tid].telegram_user_id}">{html.escape(target_map[tid].display_name)}</a>{_player_health_badge(target_map[tid])} — {count} ovoz'
            for tid, count in sorted(counts.items(), key=lambda x: -x[1])
        ]
        tally_text = "\n".join(tally_lines) if tally_lines else "<i>Hech kim ovoz bermadi</i>"

        if not counts:
            await _advance_to_next_night(game, bot, reason="no_votes")
            return

        max_votes = max(counts.values())
        top_targets = [tid for tid, count in counts.items() if count == max_votes]

        if len(top_targets) > 1:
            # Tie
            announcement = (
                f"📊 <b>Ovoz berish natijalari:</b>\n\n"
                f"{tally_text}\n\n"
                f"⚖️ <b>Ovozlar teng keldi!</b>\n"
                f"Aholi bir qarorga kela olmadi. Hech kim osilmadi."
            )
            try:
                await bot.send_message(game.chat_id, announcement, parse_mode="HTML")
            except Exception:
                pass
            await _advance_to_next_night(game, bot, reason="tie")
            return

        # Single top target → hanging confirmation
        suspect = target_map[top_targets[0]]
        suspect_mention = f'{_player_team_badge(suspect)}<a href="tg://user?id={suspect.telegram_user_id}">{html.escape(suspect.display_name)}</a>{_player_health_badge(suspect)}'

        HANGING_VOTES[game_id] = {
            'kill': 0, 'save': 0, 'voters': set(), 'target': suspect, 'message': None
        }

        bot_first_name = "Mafia Bot"
        try:
            bot_info = await bot.get_me()
            bot_first_name = bot_info.first_name
        except Exception:
            pass

        prompt_tpl = await sync_to_async(TextService.get_text)(
            'hanging_prompt_text',
            fallback="<b>{bot_name}</b>               <code>BM Admin</code>\n<b>Rostdan ham {target_name}ni osmoqchimisiz?</b>"
        )
        announcement = (
            prompt_tpl.replace('{bot_name}', html.escape(bot_first_name))
            .replace('{target_name}', suspect_mention)
        )
        kb = build_hanging_keyboard(game_id, str(suspect.id), kill_count=0, save_count=0)
        try:
            sent = await bot.send_message(
                game.chat_id, announcement, reply_markup=kb, parse_mode="HTML"
            )
            HANGING_VOTES[game_id]['message'] = sent
        except Exception as e:
            logger.warning(f"Could not send hanging confirmation: {e}")
            HANGING_VOTES.pop(game_id, None)
            await _advance_to_next_night(game, bot, reason="error")
            return

        task = asyncio.create_task(_hanging_timer(game_id, bot, HANGING_VOTES[game_id].get('message')))
        HANGING_TASKS[game_id] = task

    except Exception as e:
        logger.exception(f"Error in auto_close_voting: {e}")
        try:
            g = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
            if g.phase == GamePhase.VOTING and g.status not in ['FINISHED', 'CANCELED']:
                await _advance_to_next_night(g, bot, reason="auto_close_error_fallback")
        except Exception as fb_err:
            logger.error(f"Fallback advance to next night failed: {fb_err}")
    finally:
        CLOSING_VOTING_GAMES.discard(game_id)


async def _hanging_timer(game_id: str, bot: Bot, original_msg=None):
    """20-second timer before resolving hanging."""
    try:
        await asyncio.sleep(20)
        if game_id in HANGING_VOTES:
            game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
            if game.phase == GamePhase.VOTING and game.status not in ['FINISHED', 'CANCELED']:
                await resolve_hanging(game, bot, original_msg)
    except asyncio.CancelledError:
        logger.info(f"Hanging timer cancelled for game {game_id}.")
    except Exception as e:
        logger.exception(f"Error in hanging timer: {e}")
        try:
            game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
            if game.phase == GamePhase.VOTING and game.status not in ['FINISHED', 'CANCELED']:
                await _advance_to_next_night(game, bot, reason="hanging_timer_error")
        except Exception:
            pass
    finally:
        HANGING_TASKS.pop(game_id, None)


async def resolve_hanging(game: Game, bot: Bot, original_msg=None):
    """Resolves hanging: eliminates or saves, then win-check → next night."""
    game_id = str(game.id)
    try:
        from bot_runtime.manager import BotRuntimeManager
        bot = BotRuntimeManager.get_bot_for_game(game, bot)

        h_data = HANGING_VOTES.pop(game_id, None)
        if not h_data:
            return

        suspect = h_data['target']
        kill_votes = h_data['kill']
        save_votes = h_data['save']
        suspect_mention = f'{_player_team_badge(suspect)}<a href="tg://user?id={suspect.telegram_user_id}">{html.escape(suspect.display_name)}</a>{_player_health_badge(suspect)}'

        if kill_votes > save_votes:
            # Check osish_himoya inventory shield (STRICT: MAX 1 PER GAME)
            from apps.economy.models import Inventory
            if not suspect.metadata:
                suspect.metadata = {}

            osish_inv = None
            if not suspect.metadata.get('used_osish_himoya'):
                osish_inv = await sync_to_async(
                    lambda: Inventory.objects.filter(
                        telegram_id=suspect.telegram_user_id,
                        item__code='osish_himoya',
                        is_active=True,
                        quantity__gt=0
                    ).first()
                )()

            if osish_inv:
                osish_inv.quantity -= 1
                if osish_inv.quantity <= 0:
                    osish_inv.is_active = False
                await sync_to_async(osish_inv.save)(update_fields=['quantity', 'is_active'])
                suspect.metadata['used_osish_himoya'] = True
                await sync_to_async(suspect.save)(update_fields=['metadata'])
                try:
                    await bot.send_message(
                        suspect.telegram_user_id,
                        "🛡 <b>Inventaringizdagi 'Osishdan himoya' ishlatildi!</b>\n\n"
                        "Shahar aholisi sizni osishga ovoz berdi, ammo inventaringizdagi himoya qalqoni sizni dordan asrab qoldi va siz tirik qoldingiz!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                result_text = (
                    f"⚖️ {suspect_mention} <b>osishdan shaxsiy himoyasi evaziga dorga osilmadi va tirik qoldi!</b>\n\n"
                    f"Ovoz berish: {kill_votes} 👍xa  |  {save_votes} 👎yo'q"
                )
            else:
                await sync_to_async(
                    lambda: Player.objects.filter(id=suspect.id).update(is_alive=False)
                )()

                rname = suspect.role.name if suspect.role else "CITIZEN"
                from bot_runtime.handlers.night import role_icon, role_label
                icon = role_icon(rname)
                label = role_label(rname)

                from apps.superadmin.services import TextService
                tpl = await sync_to_async(TextService.get_text)(
                    'voting_elimination_format',
                    fallback="<b>Ovoz berish natijalari:</b>\n<b>{kill_votes} 👍 | {save_votes} 👎</b>\n\n<b>{target_name} kunduzgi yig'ilishda osildi!</b>\n<b>U edi  {role_icon} {role_name}.</b>"
                )
                result_text = (
                    tpl.replace('{target_name}', suspect_mention)
                    .replace('{kill_votes}', str(kill_votes))
                    .replace('{save_votes}', str(save_votes))
                    .replace('{role_icon}', icon)
                    .replace('{role_name}', label)
                )

                # Send PM notification to hanged suspect
                try:
                    await bot.send_message(
                        suspect.telegram_user_id,
                        "⚖️ <b>Kunduzgi ovoz berishda aholi sizga qarshi ovoz berdi va siz dorga osildingiz!</b>\n"
                        "<i>Siz o'yindan chetlatildingiz. O'yinni kuzatishda davom etishingiz mumkin.</i>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

                # Suidsid mark if hanged
                if rname in ["SUIDSID", "SUITSID"]:
                    if not suspect.metadata:
                        suspect.metadata = {}
                    suspect.metadata['hanged_as_suicide'] = True
                    await sync_to_async(suspect.save)(update_fields=['metadata'])

                # Don succession if hanged Don had Mafia teammates
                if rname == "DON":
                    import random
                    living_mafia = await sync_to_async(
                        lambda: list(Player.objects.filter(game=game, is_alive=True, role__name='MAFIA').select_related('role'))
                    )()
                    if living_mafia:
                        new_don = random.choice(living_mafia)
                        from apps.games.models import Role
                        don_role = await sync_to_async(lambda: Role.objects.filter(name='DON').first())()
                        if don_role:
                            await sync_to_async(lambda: Player.objects.filter(id=new_don.id).update(role=don_role))()
                        try:
                            new_don_mention = f'{_player_team_badge(new_don)}<a href="tg://user?id={new_don.telegram_user_id}">{html.escape(new_don.display_name)}</a>{_player_health_badge(new_don)}'
                            await bot.send_message(
                                game.chat_id,
                                f"🤵🏻 {new_don_mention} <b>Don bo'ldi!</b>\nO'yin davom etadi...",
                                parse_mode="HTML"
                            )
                            await bot.send_message(
                                new_don.telegram_user_id,
                                "🤵🏻 <b>Siz endi DON siz!</b>\n"
                                "Don osildi. Endi Mafiya sardori siz bo'ldingiz!",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
        else:
            tpl_pardon = await sync_to_async(TextService.get_text)(
                'voting_pardon_format',
                fallback="<b>Ovoz berish natijalari:</b>\n<b>{kill_votes} 👍 | {save_votes} 👎</b>\n\n🕊️ <b>Aholi {target_name} ni afv etdi!</b>\n<b>Hech kim osilmadi.</b>"
            )
            result_text = (
                tpl_pardon.replace('{target_name}', suspect_mention)
                .replace('{kill_votes}', str(kill_votes))
                .replace('{save_votes}', str(save_votes))
            )

        # Send/edit result
        try:
            if original_msg:
                await original_msg.edit_text(result_text, parse_mode="HTML")
            else:
                await bot.send_message(game.chat_id, result_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not send hanging result: {e}")
            try:
                await bot.send_message(game.chat_id, result_text, parse_mode="HTML")
            except Exception:
                pass

        # Win check
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game.id)
        winner = await sync_to_async(WinConditionService.check_win_condition)(game)

        if winner:
            await asyncio.sleep(2.0)
            await sync_to_async(GameService.finish_game)(game, winner)
            from bot_runtime.handlers.night import _announce_game_winner
            await _announce_game_winner(game, winner, bot)
        else:
            await _advance_to_next_night(game, bot, reason="hanging_done")

    except Exception as h_err:
        logger.exception(f"Error in resolve_hanging for game {game_id}: {h_err}")
        try:
            game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
            if game.phase in [GamePhase.VOTING, GamePhase.DAY] and game.status not in ['FINISHED', 'CANCELED']:
                await _advance_to_next_night(game, bot, reason="resolve_hanging_error_fallback")
        except Exception as fb_err2:
            logger.error(f"Fallback to next night after resolve_hanging error failed: {fb_err2}")


# ---------------------------------------------------------------------------
# Next night
# ---------------------------------------------------------------------------

async def _advance_to_next_night(game: Game, bot: Bot, reason: str = ""):
    """Advances game to next NIGHT round and sends PM keyboards to all role players."""
    game_id = str(game.id)
    logger.info(f"Advancing game {game_id} to next night. Reason: {reason}")
    try:
        from bot_runtime.manager import BotRuntimeManager
        bot = BotRuntimeManager.get_bot_for_game(game, bot)

        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game.id)

        game.phase = GamePhase.NIGHT
        game.round_number += 1
        game.updated_at = timezone.now()
        await sync_to_async(game.save)(update_fields=['phase', 'round_number', 'updated_at'])

        round_num = game.round_number
        bot_username = "mafia_bot"
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
        except Exception:
            pass

        all_players = await sync_to_async(
            lambda: list(game.players.all().order_by('created_at').select_related('role'))
        )()
        living_players = [p for p in all_players if p.is_alive]

        living_roster = "\n".join([
            f' {all_players.index(p) + 1}. {_player_team_badge(p)}<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>{_player_health_badge(p)}'
            for p in living_players
        ])

        from apps.superadmin.services import TextService
        night_tpl = await sync_to_async(TextService.get_text)(
            'night_start_announcement',
            fallback="🌙 <b>Qorong'u va daxshatlarga to'la {round_num}-tun boshlandi.</b>\nKo'chaga yana zulmat tushdi. <b>60 sekund</b> davomida harakatlaringizni bajaring!\n\n👥 <b>Tirik o'yinchilar: ({count} ta)</b>\n{players_list}"
        )
        night_text = (
            night_tpl.replace('{round_num}', str(round_num))
            .replace('{count}', str(len(living_players)))
            .replace('{players_list}', living_roster)
        )
        from bot_runtime.handlers.night import send_dynamic_animation
        try:
            await send_dynamic_animation(
                bot=bot,
                chat_id=game.chat_id,
                media_key='gif_night',
                fallback_url="https://media.giphy.com/media/26hirEPeos6yugLDO/giphy.gif",
                caption=night_text,
                reply_markup=build_bot_pm_keyboard(bot_username),
                parse_mode="HTML"
            )
        except Exception as na_err:
            logger.warning(f"Night animation error: {na_err}")

        living_players = await sync_to_async(
            lambda: list(game.players.filter(is_alive=True).select_related('role'))
        )()

        from bot_runtime.handlers.night import _register_ids, role_label
        _register_ids(game_id, living_players)

        from bot_runtime.keyboards.inline import (
            build_night_target_keyboard,
            build_komissar_action_keyboard,
            build_konchi_mines_keyboard,
            build_joker_boxes_setup_keyboard,
            build_back_to_group_keyboard
        )

        async def _send_next_night_prompt(player):
            if not player.role:
                return
            rname = player.role.name
            try:
                if rname in ["MAFIA", "DON"]:
                    kb = build_night_target_keyboard(game_id, "k", living_players, str(player.id))
                    await safe_send_message(
                        bot,
                        player.telegram_user_id,
                        f"🌙 <b>{round_num}-TUN:</b> Kimni yo'q qilmoqchisiz?",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                elif rname in ["DOCTOR", "HAMSHIRA"] and rname == "DOCTOR":
                    kb = build_night_target_keyboard(game_id, "p", living_players, str(player.id))
                    await safe_send_message(
                        bot,
                        player.telegram_user_id,
                        f"🌙 <b>{round_num}-TUN:</b> Kimni davolaysiz?",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                elif rname in ["DETECTIVE", "KOMISSAR", "SHERIFF"]:
                    kb = build_komissar_action_keyboard(game_id)
                    await safe_send_message(
                        bot,
                        player.telegram_user_id,
                        f"🌙 <b>{round_num}-TUN:</b> Harakatingizni tanlang:",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                elif rname == "QOTIL":
                    kb = build_night_target_keyboard(game_id, "qot", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Qurbonni tanlang:", reply_markup=kb, parse_mode="HTML")
                elif rname == "KEZUVCHI":
                    kb = build_night_target_keyboard(game_id, "kez", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimnikiga mehmonga borasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "DAYDI":
                    kb = build_night_target_keyboard(game_id, "day", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimnikiga ichkilik so'rab borasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "ADVOKAT":
                    kb = build_night_target_keyboard(game_id, "adv", living_players)
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni himoyalaysiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "UBIYTSA":
                    kb = build_night_target_keyboard(game_id, "ubi", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni o'ldirasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "TUZOQCHI":
                    kb = build_night_target_keyboard(game_id, "tuz", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Tuzoqni kimga qo'yasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "ZOMBI":
                    kb = build_night_target_keyboard(game_id, "zom", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni tishlaysiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "KIMYOGAR":
                    kb = build_night_target_keyboard(game_id, "kim", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Eliksirni kimga berasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "AXMOQ":
                    kb = build_night_target_keyboard(game_id, "axm", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni tanlaysiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "RAIS":
                    kb = build_night_target_keyboard(game_id, "rai", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Sovg'ani kimga berasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "AFERIST":
                    kb = build_night_target_keyboard(game_id, "afer", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimning ovozini o'g'irlamoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "GAZABKOR":
                    kb = build_night_target_keyboard(game_id, "gaz", living_players)
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni belgilamoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "JURNALIST":
                    kb = build_night_target_keyboard(game_id, "jurn", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimnikiga intervyuga borasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "SOTQIN":
                    kb = build_night_target_keyboard(game_id, "sotq", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni tekshirmoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "ROBINGUD":
                    kb = build_night_target_keyboard(game_id, "rob", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kamon o'qi bilan kimni otasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "AYGOQCHI":
                    kb = build_night_target_keyboard(game_id, "ayg", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Qaysi o'yinchining rolini bilmoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "KONCHI":
                    kb = build_konchi_mines_keyboard(game_id)
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Qaysi konni qazimoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "FOTOPARATCHI":
                    kb = build_night_target_keyboard(game_id, "foto", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimni rasmga olmoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "QAROQCHI":
                    kb = build_night_target_keyboard(game_id, "qar", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Kimning pullarini shilmoqchisiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "LABORANT":
                    kb = build_night_target_keyboard(game_id, "lab", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Nishonni tanlang:", reply_markup=kb, parse_mode="HTML")
                elif rname == "QORBOBO":
                    kb = build_night_target_keyboard(game_id, "qor", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Sovg'ani kimga topshirasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "OSHPAZ":
                    kb = build_night_target_keyboard(game_id, "osh", living_players, str(player.id))
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Maxsus taomingizni kimga yedirasiz?", reply_markup=kb, parse_mode="HTML")
                elif rname == "JOKER":
                    kb = build_joker_boxes_setup_keyboard(game_id)
                    await safe_send_message(bot, player.telegram_user_id, f"🌙 <b>{round_num}-TUN:</b> Bombani qaysi qutilarga joylaysiz?", reply_markup=kb, parse_mode="HTML")
                elif rname in ["SERJANT", "ADMIRAL"]:
                    await safe_send_message(
                        bot,
                        player.telegram_user_id,
                        f"🌙 <b>{round_num}-TUN boshlandi!</b>\n\n"
                        f"👮🏼‍♂️ Siz {role_label(rname)}siz. Komissarning harakatlarini kuzating yoki bot orqali unga xabar yozing (Politsiya chati)!",
                        reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
                        parse_mode="HTML"
                    )
                else:
                    await safe_send_message(
                        bot,
                        player.telegram_user_id,
                        f"🌙 <b>{round_num}-TUN boshlandi!</b>\n\n"
                        f"Tunda vazifangiz yo'q. Kunduzgi muhokama va ovoz berishda faol qatnashing!",
                        reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
                        parse_mode="HTML"
                    )
            except Exception as pm_err:
                logger.warning(f"Night PM to {player.telegram_user_id} failed: {pm_err}")

        await asyncio.gather(*[_send_next_night_prompt(p) for p in living_players], return_exceptions=True)

        if game.phase == GamePhase.NIGHT and game.status not in ['FINISHED', 'CANCELED']:
            from bot_runtime.handlers.night import start_night_timer
            from apps.superadmin.services import SettingService
            bot_id_str = str(game.bot_id) if game and getattr(game, 'bot_id', None) else ''
            n_dur = await sync_to_async(SettingService.get_bot_timing)(bot_id_str, 'night_duration', 60)
            start_night_timer(game_id, bot, duration=n_dur)

    except Exception as e:
        logger.exception(f"Error in _advance_to_next_night: {e}")
