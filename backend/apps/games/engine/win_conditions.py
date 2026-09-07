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
        2. Solo Killer Win: Qotil / Tuzoqchi / Joker is last survivor or 1v1 with civilian.
        3. Mafia Win: Living Mafia >= Living Non-Mafia and no living Solo killers.
        4. Civilian Win: All hostile threats (Mafia, Qotil, Tuzoqchi, Joker, Ubiytsa, Kimyogar, Zombi) are eliminated!
        """
        alive_players = list(Player.objects.filter(game=game, is_alive=True).select_related('role'))

        if not alive_players:
            return None

        total_alive = len(alive_players)

        # 1. Check Zombie Victory: All living players are Zombies
        zombie_count = sum(1 for p in alive_players if p.role and p.role.team == RoleTeam.ZOMBIE)
        if zombie_count == total_alive and total_alive > 0:
            return RoleTeam.ZOMBIE

        # Count factions
        mafia_count = sum(1 for p in alive_players if p.role and p.role.team == RoleTeam.MAFIA)
        solo_killer_roles = {'QOTIL', 'TUZOQCHI', 'JOKER'}
        solo_killers = [p for p in alive_players if p.role and p.role.name in solo_killer_roles]
        solo_killer_count = len(solo_killers)

        civilian_count = sum(1 for p in alive_players if p.role and p.role.team == RoleTeam.CIVILIAN)

        # 2. Solo Killer Victory: Single solo killer remains alone or in 1v1 with a civilian
        if solo_killer_count == 1 and total_alive <= 2 and mafia_count == 0 and zombie_count == 0:
            return RoleTeam.SOLO

        # 3. Mafia Victory
        if mafia_count > 0 and solo_killer_count == 0 and zombie_count == 0:
            non_mafia_count = total_alive - mafia_count
            if mafia_count >= non_mafia_count:
                return RoleTeam.MAFIA

        # 4. Civilian Victory: All hostile threats eliminated
        if mafia_count == 0 and solo_killer_count == 0 and zombie_count == 0:
            return RoleTeam.CIVILIAN

        return None
