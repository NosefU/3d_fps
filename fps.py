import curses
from math import *


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return f'{self.__class__.__name__}(x:{self.x}, y:{self.y})'

    def __repr__(self):
        return str(self)


class Vector:
    """Класс математического вектора"""

    def __init__(self, point, direction=None, length=None, end_point=None):
        """
#             Создать вектор из точки start_point.
#             Задать вектор можно двумя способами: либо передав направление и длину, либо передав конечную точку
#         """
        self.start_point = point

        if end_point:
            self.dx = end_point.x - point.x
            self.dy = end_point.y - point.y
            self.module = self._determine_module()
            self.end_point = end_point
            self.direction = self._determine_direction()
            self.sin = sin(radians(self.direction))
            self.cos = cos(radians(self.direction))

        else:
            self.direction = direction % 360
            self.sin = sin(radians(self.direction))
            self.cos = cos(radians(self.direction))
            self.dx = self.cos * length
            self.dy = self.sin * length
            self.module = length
            self.end_point = Point(self.start_point.x + self.dx, self.start_point.y + self.dy, )

    def _determine_module(self):
        return sqrt(self.dx ** 2 + self.dy ** 2)

    @property
    def angle(self):
        return self.direction

    def _determine_direction(self):
        if self.dx == 0:
            if self.dy >= 0:
                return 90
            else:
                return 270
        else:
            angle = atan(self.dy / self.dx) * (180 / pi)
            if self.dx < 0:
                angle += 180
        return angle

    def __str__(self):
        return 'vector([%.2f,%.2f],{%.2f,%.2f})' % (self.dx, self.dy, self.angle, self.module)

    def __repr__(self):
        return str(self)

    def multiply(self, factor):
        """
            Умножить вектор на скалярное число
        """
        self.dx *= factor
        self.dy *= factor
        self.module = self._determine_module()
        self.end_point = Point(self.start_point.x + self.dx, self.start_point.y + self.dy, )

    @property
    def length(self):
        return self.module

    @length.setter
    def length(self, value):
        self.dx = self.cos * value
        self.dy = self.sin * value
        self.module = value
        self.end_point = Point(self.start_point.x + self.dx, self.start_point.y + self.dy, )


class Level:
    def __init__(self, width, height, content):
        self.width = width
        self.height = height
        self.map = content
        self.wall_chars = '#'

    def get_row(self, row):
        assert 0 <= row < self.height, f'Row {row} out of level bounds (0, {self.height})'
        return self.map[row * self.width: (row + 1) * self.width]

    def point_is_present(self, point):
        # установка таких границ работает быстрее, чем int(point.x) или int(point.y)
        return (-1 < point.x < self.width) and (-1 < point.y < self.height)

    def get_cell(self, point):
        assert self.point_is_present(point), f'{point} out of level bounds (0, 0, {self.width}, {self.height})'
        return self.map[int(point.y) * self.width + int(point.x)]

    def check_cell(self, point, cell):
        try:
            return self.get_cell(point) in cell
        except AssertionError:
            return False

    def is_wall(self, point):
        try:
            return self.get_cell(point) in self.wall_chars
        except AssertionError:
            return True


class Player:
    def __init__(self, position, direction, speed=1, turn_step=5):
        self.position = position
        self._dir = direction
        self.speed = speed
        self.turn_step = turn_step

    @property
    def dir(self):
        return self._dir

    @dir.setter
    def dir(self, value):
        self._dir = value % 360

    @property
    def x(self):
        return self.position.x

    @x.setter
    def x(self, value):
        self.position.x = value

    @property
    def y(self):
        return self.position.y

    @y.setter
    def y(self, value):
        self.position.y = value

    def move_forward(self, speed=None):
        speed = speed if speed else self.speed
        self.position = Vector(self.position, self.dir, speed).end_point

    def move_back(self, speed=None):
        speed = speed if speed else self.speed
        self.position = Vector(self.position, self.dir, -speed).end_point

    def turn_left(self, angle=None):
        self.dir -= angle if angle else self.turn_step

    def turn_right(self, angle=None):
        self.dir += angle if angle else self.turn_step

    def get_dir_arrow(self):
        arrow_number = (self.dir + 22.5) // 45
        return '→↘↓↙←↖↑↗→'[int(arrow_number)]


class Camera:
    def __init__(self, viewport_width, viewport_height, fov=60, depth=21.0):
        self.fov = fov      # Угол обзора
        self.depth = depth  # Максимальная дистанция обзора
        self.vp_width, self.vp_height = viewport_width, viewport_height
        self.z_map = []
        self.edges = []
        self.hits = []

    def cast_single_ray(self, level, origin, ray_angle, target='#EWSBM', depth=None):
        """
        Метод вернёт вектор, направленный в сторону ray_angle;
        модуль вектора будет равняться расстоянию от origin до target, если была найдена коллизия,
        либо depth, если коллизии не было.
        По-умолчанию метод ищет коллизию со стеной на расстоянии не более глубины прорисовки
        """
        depth = depth if depth else self.depth
        distance_to_target = 0.0
        target_hit = False
        while not target_hit and distance_to_target < depth:
            distance_to_target += 0.1
            ray = Vector(origin, ray_angle, distance_to_target)
            test_point = ray.end_point
            # проверяем, не вышел ли вектор за карту
            if not level.point_is_present(test_point):
                distance_to_target = depth
            # проверяем, не упёрся ли вектор в стену
            elif level.check_cell(test_point, target):
                target_hit = True

            if target_hit:
                distance_to_target -= 1
                while distance_to_target < depth:
                    distance_to_target += 0.1
                    ray = Vector(origin, ray_angle, distance_to_target)
                    test_point = ray.end_point
                    if level.check_cell(test_point, target):
                        break

                distance_to_target -= 0.1
                while distance_to_target < depth:
                    distance_to_target += 0.01
                    ray = Vector(origin, ray_angle, distance_to_target)
                    test_point = ray.end_point
                    if level.check_cell(test_point, target):
                        break
        return ray

    def raycast(self, player, level):
        """
        Бросаем лучи.
        Разбиваем область видимости (fov) на количество участков, равное ширине экрана/вьюпорта.
        Направлением начала отсчёта будет направление взгляда игрока минус половина области видимости.
        И для каждой координаты x экрана/вьюпорта мы бросаем луч/вектор, последовательно увеличивая его длину.
        Если луч попадает в стену, то записываем длину луча (расстояние до стены) в список и переходим к следующему x.
        Если длина луча стала больше глубины прорисовки, а стену мы так и не нашли,
        то добавляем в список значение глубины прорисовки.
        """
        self.z_map = []
        self.edges = []
        self.hits = []
        prev_dist = None
        for x in range(0, self.vp_width):
            ray_angle = player.dir - (self.fov / 2) + (x / self.vp_width) * self.fov
            current_ray = self.cast_single_ray(level, player.position, ray_angle)
            distance_to_wall = current_ray.length
            wall_hit = current_ray.length < self.depth

            # Если нашли стену (расстояние меньше, чем дальность прорисовки), то кидаем векторы до углов блока.
            # Выбираем два самых "котортких" вектора и считаем угол между брошеным лучом и каждым из этих векторов.
            # Если угол меньше четверти градуса, то считаем, что в этой координате x находится грань блока.
            if wall_hit:
                edge_vectors = []
                for block_x in range(0, 2):
                    for block_y in range(0, 2):
                        test_point = current_ray.end_point
                        edge_pos = Point(int(test_point.x) + block_x, int(test_point.y) + block_y)
                        edge_vector = Vector(player.position, end_point=edge_pos)
                        edge_vectors.append(edge_vector)

                edge_vectors.sort(key=lambda vector: vector.length)
                if (fabs(current_ray.angle - edge_vectors[0].angle) < 0.25
                        or fabs(current_ray.angle - edge_vectors[1].angle) < 0.25):
                    self.edges.append(x)
            # если разница "длин" соседних лучей/расстояний до стены достаточно большая,
            # то считаем, что более "короткий" луч попал в грань блока
            if prev_dist:
                if prev_dist - distance_to_wall > 1:
                    self.edges.append(x)
                elif prev_dist - distance_to_wall < -1:
                    self.edges.append(x-1)
            prev_dist = distance_to_wall

            # если мы прямо сейчас добавим расстояние до стены в z-карту,
            # то получим на экране эффект лупы, поэтому умножим расстояние до стены на косинус угла отклонения луча
            dist_factor = cos(radians(ray_angle - player.dir))
            distance_to_wall = distance_to_wall * dist_factor
            distance_to_wall = distance_to_wall if distance_to_wall > 1 else 1
            self.hits.append(current_ray)
            self.z_map.append(distance_to_wall)

    @staticmethod
    def clear_viewport(screen):
        screen.clear()

    def draw_column(self, screen, x):
        y_top, y_bot = self.get_column_coords(x)
        y_top = 0 if y_top < 0 else y_top
        y_bot = self.vp_height - 1 if y_bot > self.vp_height - 1 else y_bot
        # если x есть в списке с гранями и находится в зоне видимости, то вместо стены будем рисовать эту грань
        if x in self.edges and self.z_map[x] < self.depth:
            wall_char = '|'
        # "красим" стену в зависимости от расстояния до неё
        elif self.z_map[x] <= self.depth / 3:
            wall_char = '█'
        elif self.z_map[x] < self.depth / 2:
            wall_char = '▓'
        elif self.z_map[x] < self.depth / 1.5:
            wall_char = '▒'
        elif self.z_map[x] < self.depth:
            wall_char = '░'
        else:
            wall_char = ' '
        for y in range(y_top, y_bot):
            screen.addstr(y, x, wall_char)

    def get_column_coords(self, x):
        # считаем высоту столбца, которая зависит от расстояни до неё
        col_height = int(self.vp_height / self.z_map[x])
        y_top = int(self.vp_height / 2) - col_height
        y_bot = self.vp_height - y_top
        return y_top, y_bot

    def render_ceil(self, screen):
        for x in range(0, self.vp_width):
            for y in range(0, self.vp_height//2):
                screen.addstr(y, x, ' ')

    def render_floor(self, screen):
        for x in range(0, self.vp_width):
            for y in range(self.vp_height // 2, self.vp_height - 1):
                # В зависимости от высоты от низа используем те или иные символы
                floor_dist = 1 - (y - self.vp_height / 2) / (self.vp_height / 2)
                if floor_dist < 0.25:
                    screen.addstr(y, x, '#')
                elif floor_dist < 0.5:
                    screen.addstr(y, x, 'x')
                elif floor_dist < 0.75:
                    screen.addstr(y, x, '~')
                elif floor_dist < 0.9:
                    screen.addstr(y, x, '-')
                else:
                    screen.addstr(y, x, ' ')

    def draw_walls(self, screen):
        for x in range(0, self.vp_width):
            self.draw_column(screen, x)

    def render_viewport(self, screen):
        self.render_ceil(screen)
        self.render_floor(screen)
        self.draw_walls(screen)


def draw_minimap(screen, position, player, level):
    for y in range(0, level.height):
        screen.addstr(y + position.y, position.x, level.get_row(y))
    screen.addstr(int(player.y) + position.y, int(player.x) + position.x, player.get_dir_arrow())


def main_game(screen):
    viewport_width = curses.COLS
    viewport_height = curses.LINES
    key = 0
    level = Level(map_width, map_height, lvl_map)
    player = Player(Point(2.0, 1.0), 90.0)
    camera = Camera(viewport_width, viewport_height)

    while True:  # игровой цикл
        if key == ord('w'):
            player.move_forward()
            # если упёрлись в стену, то откатываем шаг
            # TODO Дописать условие, при котором игрок не перепрыгнет через стену
            #  (проверка нахождения игрока за полем или перелёт через стену).
            #  По идее надо написать метод для бросания одного луча и заюзать его для этого
            if level.is_wall(player.position):
                player.move_back()
        elif key == ord('s'):
            player.move_back()
            # если упёрлись в стену, то откатываем шаг
            if level.is_wall(player.position):
                player.move_forward()
        elif key == ord('d'):
            player.turn_right()
        elif key == ord('a'):
            player.turn_left()

        camera.raycast(player, level)
        camera.clear_viewport(screen)
        camera.render_viewport(screen)

        draw_minimap(screen, Point(0, 1), player, level)
        screen.addstr(0, 0, f'x={player.x: 6.2f} y={player.y: 6.2f} dir={player.dir:>5}')
        key = screen.getch()


if __name__ == '__main__':
    # карта уровня
    map_height = 16
    map_width = 25
    lvl_map = ("#########################"
               "#.......................#"
               "#....#########..........#"
               "#............#..........#"
               "#............#..........#"
               "#............#..........#"
               "#............#####......#"
               "#....###................#"
               "#....###.....#......##..#"
               "#............#......##..#"
               "#............#..........#"
               "#............#..........#"
               "#........########.......#"
               "#.......................#"
               "#.......................#"
               "#########################").replace('.', ' ')

    curses.wrapper(main_game)
