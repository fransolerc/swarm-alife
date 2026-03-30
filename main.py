# =============================================================================
# main.py — swarm-alife entry point
# =============================================================================

import sys
import pygame

from utils import setup_logging
setup_logging()

from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE
from agent.creature import Creature
from core.game import Game


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)

    game = Game(screen, Creature)
    game.run()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
