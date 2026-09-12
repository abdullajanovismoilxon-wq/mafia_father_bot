from typing import Optional
from apps.games.models import Game, Player, RoleTeam


class WinConditionService:
    """
    Evaluates living player factions to determine if game has reached a terminal win state.
    """

    @classmethod
    def check_win_condition(cls, game: Game) -> Optional[str]:
        """
        Evaluates living players across all teams:
        1. Zombie Win: All living players are Zombies.
        2. Solo Killer Win: Qotil / Tuzoqchi / Joker / Kimyogar is last survivor or 1v1 with civilian.
        3. Mafia Win: Living Mafia >= Living Non-Mafia and no living Solo killers.
           Note: If 1 Mafia vs 1 lethal Civilian (Komissar/Sheriff/Robin Gud), Mafia doesn't win immediately; night duel plays out.
        4. Civilian Win: All hostile threats (Mafia, Qotil, Tuzoqchi, Joker, Ubiytsa, Kimyogar, Afsungar, Gazabkor, Zombi) are eliminated!
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
        zombie_count = sum(1 for p in alive_players if p.role and str(p.role.team).upper() in ['ZOMBIE', RoleTeam.ZOMBIE])
        if zombie_count == total_alive and total_alive > 0:
            return RoleTeam.ZOMBIE

        # Count factions
        mafia_count = sum(1 for p in alive_players if p.role and str(p.role.team).upper() in ['MAFIA', RoleTeam.MAFIA])
        solo_killer_roles = {'QOTIL', 'TUZOQCHI', 'JOKER', 'KIMYOGAR', 'AFSUNGAR', 'GAZABKOR'}
        solo_killers = [
            p for p in alive_players
            if p.role and (
                p.role.name in solo_killer_roles or
                str(p.role.team).upper() in ['SOLO', RoleTeam.SOLO]
            )
        ]
        solo_killer_count = len(solo_killers)

        civilian_count = sum(1 for p in alive_players if p.role and str(p.role.team).upper() in ['CIVILIAN', RoleTeam.CIVILIAN])

        # Town lethal roles that can shoot hostile targets at night
        town_shooters = [
            p for p in alive_players
            if p.role and p.role.name in ['DETECTIVE', 'KOMISSAR', 'SHERIFF', 'ROBINGUD']
        ]

        # 2. Solo Killer Victory: Single solo killer remains alone or in 1v1 with a civilian without shooting power
        if solo_killer_count == 1 and total_alive <= 2 and mafia_count == 0 and zombie_count == 0:
            if total_alive == 2 and len(town_shooters) > 0:
                return None  # Let night duel play out
            return RoleTeam.SOLO

        # 3. Mafia Victory
        if mafia_count > 0 and solo_killer_count == 0 and zombie_count == 0:
            non_mafia_count = total_alive - mafia_count
            if mafia_count > non_mafia_count:
                return RoleTeam.MAFIA
            elif mafia_count == non_mafia_count:
                # If 1v1 with a town shooter (Komissar/Sheriff/RobinGud), allow night shootout!
                if len(town_shooters) == 0:
                    return RoleTeam.MAFIA

        # 4. Civilian Victory: All hostile threats eliminated
        if mafia_count == 0 and solo_killer_count == 0 and zombie_count == 0:
            return RoleTeam.CIVILIAN

        return None
