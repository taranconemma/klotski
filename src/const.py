# Constants de configuració per a l'avaluació i la generació dels grafs

# Llindars màxims de normalització de les mètriques d'avaluació (eval)
MAX_ESTATS: int = 74176  # nodes
MAX_SOLUCIO: int = 126  # moviments
MAX_DIAMETRE: int = 210  # pseudo-diàmetre
MAX_PARANYS: float = 0.0025  # densitat paranys ponderada
MAX_PONTS: int = 9  # ponts en el camí òptim
MAX_ENGANY: int = 2  # caselles d'allunyament màxim

# Configuració de la generació del graf (graph)
LIMIT_NODES: int = 800_000  # límit de nodes permesos en el graf
TIMEOUT_ACTIVAT: bool = True
TIMEOUT_SEGONS: int = 5 * 60  # 5 minuts
