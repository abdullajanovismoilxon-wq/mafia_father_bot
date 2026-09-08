"""
Configuration-driven Night Action Service.

Phase 3: Validates role→action mapping via RoleAbility DB entries.
Falls back to Phase 2 hardcoded mapping if no RoleAbility records found.
Ensures full backward compatibility with all existing Phase 2 tests.
"""
from typing import Optional
from django.db import transaction
from apps.games.models import Game, Player, NightAction, NightActionType, GamePhase, RoleType, AbilityType


class ActionValidationError(Exception):
    """Raised when a night action fails domain validation."""
    pass


# Phase 2 & 3 mapping
_LEGACY_ROLE_ACTION_MAP = {
    RoleType.MAFIA: NightActionType.MAFIA_KILL,
    RoleType.DON: NightActionType.MAFIA_KILL,
    RoleType.DOCTOR: NightActionType.DOCTOR_PROTECT,
    RoleType.DETECTIVE: NightActionType.DETECTIVE_INVESTIGATE,
    RoleType.QOTIL: NightActionType.QOTIL_KILL,
    RoleType.KEZUVCHI: NightActionType.KEZUVCHI_VISIT,
    RoleType.DAYDI: NightActionType.DAYDI_VISIT,
    RoleType.ADVOKAT: NightActionType.ADVOKAT_PROTECT,
    RoleType.UBIYTSA: NightActionType.UBIYTSA_KILL,
    RoleType.TUZOQCHI: NightActionType.TUZOQCHI_TRAP,
    RoleType.ZOMBI: NightActionType.ZOMBI_BITE,
    RoleType.KIMYOGAR: NightActionType.KIMYOGAR_POTION,
    RoleType.AXMOQ: NightActionType.AXMOQ_VISIT,
    RoleType.BUQALAMUN: NightActionType.BUQALAMUN_MORPH,
    RoleType.RAIS: NightActionType.RAIS_GIFT,
    RoleType.JOKER: NightActionType.JOKER_BOXES,
    RoleType.SOTQIN: NightActionType.SOTQIN_CHECK,
    RoleType.ROBINGUD: NightActionType.ROBINGUD_SHOOT,
    RoleType.AYGOQCHI: NightActionType.AYGOQCHI_SPY,
    RoleType.KONCHI: NightActionType.KONCHI_MINE,
    RoleType.FOTOPARATCHI: NightActionType.FOTOPARATCHI_SNAP,
    RoleType.QAROQCHI: NightActionType.QAROQCHI_ROB,
    RoleType.LABORANT: NightActionType.LABORANT_ACTION,
    RoleType.QORBOBO: NightActionType.QORBOBO_GIFT,
    RoleType.OSHPAZ: NightActionType.OSHPAZ_FEED,
    RoleType.AFERIST: NightActionType.AFERIST_STEAL,
    RoleType.GAZABKOR: NightActionType.GAZABKOR_MARK,
    RoleType.JURNALIST: NightActionType.JURNALIST_INVESTIGATE,
}

# Map AbilityType → NightActionType
_ABILITY_TO_ACTION_MAP = {
    AbilityType.KILL: NightActionType.MAFIA_KILL,
    AbilityType.PROTECT: NightActionType.DOCTOR_PROTECT,
    AbilityType.INVESTIGATE: NightActionType.DETECTIVE_INVESTIGATE,
}


def _get_allowed_action_for_role(role) -> Optional[str]:
    """
    Determines which NightActionType a role may perform.
    """
    try:
        from apps.games.models import RoleAbility, AbilityPhase
        night_ability = role.abilities.filter(
            phase__in=[AbilityPhase.NIGHT, AbilityPhase.ANY]
        ).exclude(ability_type=AbilityType.NONE).first()

        if night_ability:
            return _ABILITY_TO_ACTION_MAP.get(night_ability.ability_type)
    except Exception:
        pass

    return _LEGACY_ROLE_ACTION_MAP.get(role.name)


class NightActionService:
    """Service handling validation and persistence of Night Actions."""

    @classmethod
    def submit_action(
        cls,
        game: Game,
        actor: Player,
        target: Optional[Player],
        action_type: str,
        metadata: dict = None
    ) -> NightAction:
        """
        Validates and records a night action under atomic transaction.
        """
        with transaction.atomic():
            if game.phase != GamePhase.NIGHT:
                raise ActionValidationError("Night actions can only be submitted during the NIGHT phase.")

            if actor.game_id != game.id or not actor.is_alive:
                raise ActionValidationError("Only living players in this game can perform night actions.")

            if not actor.role:
                raise ActionValidationError("Actor has no assigned role.")

            # Validate role capability
            allowed_action = _get_allowed_action_for_role(actor.role)

            is_detective = actor.role.name in [RoleType.DETECTIVE, 'KOMISSAR', 'SHERIFF']
            is_doctor = actor.role.name in [RoleType.DOCTOR, 'SHIFOKOR']
            
            if is_detective and action_type in [NightActionType.DETECTIVE_INVESTIGATE, NightActionType.DETECTIVE_SHOOT]:
                pass  # Allowed
            elif is_doctor and action_type == NightActionType.DOCTOR_PROTECT:
                pass  # Allowed
            elif allowed_action != action_type:
                raise ActionValidationError(
                    f"Role '{actor.role.name}' cannot perform '{action_type}'."
                )

            # Doctor can only protect self once per game
            if is_doctor and target and target.id == actor.id:
                previous_self_protects = NightAction.objects.filter(
                    game=game,
                    actor=actor,
                    target=actor,
                    action_type=NightActionType.DOCTOR_PROTECT
                ).exclude(round=game.round_number).count()
                if previous_self_protects >= 1:
                    raise ActionValidationError("Shifokor o'zini o'yin davomida faqat 1 marta qutqara oladi!")

            # Kezuvchi cannot choose same target 2 nights in a row
            if actor.role.name == RoleType.KEZUVCHI and target:
                prev_action = NightAction.objects.filter(
                    game=game,
                    actor=actor,
                    round=game.round_number - 1
                ).first()
                if prev_action and prev_action.target_id == target.id:
                    raise ActionValidationError("Kezuvchi bir xil o'yinchini ketma-ket 2 marta tanlay olmaydi!")

            # Buqalamun only acts on round 1
            if actor.role.name == RoleType.BUQALAMUN and game.round_number > 1:
                raise ActionValidationError("Buqalamun faqat 1-tunda rolni tanlay oladi!")

            if target:
                if target.game_id != game.id:
                    raise ActionValidationError("Target player must belong to the same game.")
                if not target.is_alive:
                    raise ActionValidationError("Cannot target an eliminated player.")

            # Create or update existing action for this round & actor
            action, _ = NightAction.objects.update_or_create(
                game=game,
                round=game.round_number,
                actor=actor,
                defaults={
                    'target': target,
                    'action_type': action_type,
                    'metadata': metadata or {},
                }
            )
            return action
