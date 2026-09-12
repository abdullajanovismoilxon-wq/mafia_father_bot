from typing import Optional
from apps.games.models import Game, Player, RoleTeam


class WinConditionService:
    """
    Evaluates living player factions to determine if game has reached a terminal win state.
    """

    LETHAL_SOLO_ROLES = {
        'QOTIL', 'TUZOQCHI', 'JOKER', 'KIMYOGAR', 'AFSUNGAR', 'GAZABKOR', 'SEHRGAR', 'MANIAK'
    }

    BENIGN_SOLO_ROLES = {
        'RAIS', 'QORBOBO', 'OSHPAZ', 'KONCHI', 'AFERIST', 'BUQALAMUN', 'SUIDSID', 'SUITSID', 'BORI', "BO'RI", 'AXMOQ', 'QAROQCHI'
    }

    @classmethod
    def check_win_condition(cls, game: Game) -> Optional[str]:
        """
        Evaluates living players across all teams:
        1. Zombie Win: All living players are Zombies.
        2. Solo Killer Win: Single lethal killer (Qotil, Tuzoqchi, Joker, Kimyogar, Afsungar, Gazabkor, Sehrgar)
           is the last survivor or in 1v1 against an unarmed civilian.
        3. Mafia Win: Living Mafia > Living Non-Mafia (or 1v1 without town shooter) and no lethal solo killers or zombies.
        4. Civilian Win: All hostile threats (Mafia, Zombies, Lethal Solo Killers) are eliminated!
           Living benign solo roles (Rais, Qorbobo, Oshpaz, Konchi, Aferist, etc.) share victory with Civilians.
        """
        alive_players = list(Player.objects.filter(game=game, is_alive=True).select_related('role'))

        if not alive_players:
            if Player.objects.filter(game=game).exists():
                return 'ALL_DEAD'
            return None

        # TEAM Mode Win Condition: Last surviving team (RED vs BLUE) wins!
        if getattr(game, 'mode', 'CLASSIC') == 'TEAM':
            red_alive = sum(1 for p in alive_players if p.metadata and p.metadata.get('team_side') == 'RED')
            blue_alive = sum(1 for p in alive_players if p.metadata and p.metadata.get('team_side') == 'BLUE')
            if red_alive > 0 and blue_alive == 0:
                return 'TEAM_RED'
            elif blue_alive > 0 and red_alive == 0:
                return 'TEAM_BLUE'
            return None

        # Guard against unassigned roles during initialization in CLASSIC mode
        if any(p.role is None for p in alive_players):
            return None

        total_alive = len(alive_players)

        # 1. Check Zombie Victory: All living players are Zombies
        zombie_players = [p for p in alive_players if p.role and str(p.role.team).upper() in ['ZOMBIE', RoleTeam.ZOMBIE]]
        if len(zombie_players) == total_alive and total_alive > 0:
            return RoleTeam.ZOMBIE

        # Count factions
        mafia_players = [
            p for p in alive_players
            if p.role and (
                str(p.role.team).upper() in ['MAFIA', RoleTeam.MAFIA] or
                p.role.name in ['DON', 'MAFIA', 'ADVOKAT', 'UBIYTSA', 'JURNALIST', 'AYGOQCHI', 'LABORANT']
            )
        ]
        mafia_count = len(mafia_players)

        lethal_solo_players = [
            p for p in alive_players
            if p.role and p.role.name in cls.LETHAL_SOLO_ROLES
        ]
        lethal_solo_count = len(lethal_solo_players)

        # Town lethal roles that can shoot hostile targets at night
        town_shooters = [
            p for p in alive_players
            if p.role and p.role.name in ['DETECTIVE', 'KOMISSAR', 'SHERIFF', 'ROBINGUD']
        ]

        # 2. Solo Killer Victory: Single lethal solo killer remains alone or in 1v1 with a civilian without shooting power
        if lethal_solo_count == 1 and mafia_count == 0 and len(zombie_players) == 0:
            if total_alive == 1:
                return RoleTeam.SOLO
            elif total_alive == 2:
                if len(town_shooters) == 0:
                    return RoleTeam.SOLO
                return None  # Let night duel play out

        # If multiple lethal killers are alive, or 1 killer with 2+ citizens, continue playing
        if lethal_solo_count > 0:
            return None

        # 3. Mafia Victory: Living Mafia >= Living Non-Mafia and no lethal solo killers or zombies
        if mafia_count > 0 and lethal_solo_count == 0 and len(zombie_players) == 0:
            non_mafia_count = total_alive - mafia_count
            if mafia_count > non_mafia_count:
                return RoleTeam.MAFIA
            elif mafia_count == non_mafia_count:
                # If 1v1 with a town shooter (Komissar/Sheriff/RobinGud), allow night shootout!
                if len(town_shooters) == 0:
                    return RoleTeam.MAFIA
                return None

        # 4. Civilian Victory: All hostile threats (Mafia, Zombies, Lethal Solo Killers) eliminated!
        if mafia_count == 0 and lethal_solo_count == 0 and len(zombie_players) == 0:
            return RoleTeam.CIVILIAN

        return None
