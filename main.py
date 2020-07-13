import curses
import simple_draw
from math import sin, cos, pi
from time import sleep

# VIEWPORT_WIDTH = curses.COLS
# VIEWPORT_HEIGHT = curses.LINES


class TPlayer:
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self._dir = direction

    @property
    def dir(self):
        return self._dir

    @dir.setter
    def dir(self, value):
        self._dir = value % 360

    def move_forward(self, distance):
        direction = (self._dir * pi) / 180
        self.x += cos(direction) * distance
        self.y -= sin(direction) * distance

    def move_back(self, distance):
        direction = (self._dir * pi) / 180
        self.x -= cos(direction) * distance
        self.y += sin(direction) * distance

    # def get_dir_arrow(self):
    #     if self._dir// 306


class TCamera:
    def __init__(self, viewport, fov=3.14159 / 3, depth=30.0):
        self.fov = fov          # Угол обзора
        self.depth = depth      # Максимальная дистанция обзора
        self.vp_width, self.vp_height = viewport



map_height = 16
map_width = 16
level_map = ("################"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "#..............#"
             "################")


def main_game(screen):
    key = 0
    player = TPlayer(5.0, 5.0, 0.0)
    # camera = TCamera()

    while True:     # игровой цикл
        key = screen.getch()
        for y in range(0, map_height):
            screen.addstr(y, 0, level_map[y * map_width:(y + 1) * map_width])
        if key == ord('w'):
            player.move_forward(1)
            # если упёрлись в стену, то откатываем шаг
            if level_map[int(player.y) * map_width + int(player.x)] == '#':
                player.move_back(1)
        elif key == ord('s'):
            player.move_back(1)
            # если упёрлись в стену, то откатываем шаг
            if level_map[int(player.y) * map_width + int(player.x)] == '#':
                player.move_forward(1)
        elif key == ord('d'):
            player.dir -= 1.5
        elif key == ord('a'):
            player.dir += 1.5

        screen.addstr(int(player.y), int(player.x), '█')
        screen.addstr(20, 0, f'x={player.x: 5.2f} y={player.y: 5.2f} dir={player.dir:>5}')
        key = 0
        # sleep(1/30)


curses.wrapper(main_game)
