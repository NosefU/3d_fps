import math
import os
import raycast
import pygame
from pygame import locals as pgl


# карта уровня
map_size = (25, 16)
wall_chars = '#EWSBM'
map_content = ("#########################"
               "#.......................#"
               "#....SSSSSSSSM..........#"
               "#............M..........#"
               "#............M..........#"
               "#............M..........#"
               "#............SSSSS......#"
               "#....BBB................#"
               "#....BBB.....W......##..#"
               "#............W......##..#"
               "#............W..........#"
               "#............W..........#"
               "#........E######E.......#"
               "#.......................#"
               "#.......................#"
               "#########################").replace('.', ' ')


class PGCamera:
    """
        Класс камеры, в котором происходят все расчёты и рендер уровня.
        Из-за большого количества изменений (по сравнению с консольной версией) практически во всех методах,
        оказалось проще не наследоваться, а создать новый класс на основе консольного
    """
    def __init__(self, screen, level, player, fov=60, depth=21.0):
        # привязываем камеру к экрану, уровню и игроку для более удобной работы
        self._screen = screen
        self.level = level
        self.player = player
        self.fov = fov  # Угол обзора
        self.depth = depth  # Максимальная дистанция обзора
        self.vp_width, self.vp_height = self._screen.get_size()     # берём размер вьюпорта из размеров экрана
        self.z_map = []      # список расстояний от игрока до объектов для каждого луча (скорректированный)
        self.hits = []      # "сырые" векторы, полученные рейкастингом

        # подгружаем используемые текстуры
        self.textures = {
            '#': pygame.image.load(os.path.join('assets', 'redbrick.png')).convert(),
            ' ': pygame.image.load(os.path.join('assets', 'redbrick.png')).convert(),
            'E': pygame.image.load(os.path.join('assets', 'eagle.png')).convert(),
            'W': pygame.image.load(os.path.join('assets', 'wood.png')).convert(),
            'S': pygame.image.load(os.path.join('assets', 'greystone.png')).convert(),
            'B': pygame.image.load(os.path.join('assets', 'bluestone.png')).convert(),
            'M': pygame.image.load(os.path.join('assets', 'slimestone.png')).convert(), }

        # подгружаем текстуру для скайбокса
        # и изменяем её размер так, чтобы её высота равнялась высоте окна (с сохранением пропорций)
        self.bg_texture = pygame.image.load(os.path.join('assets', 'deathvalley_panorama.jpg')).convert()
        bg_scale_factor = self.vp_height / self.bg_texture.get_height()
        bg_height = int(self.bg_texture.get_height() * bg_scale_factor)
        bg_width = int(self.bg_texture.get_width() * bg_scale_factor)
        self.bg_texture = pygame.transform.scale(self.bg_texture, (bg_width, bg_height))

    @property
    def screen(self):
        return self._screen

    @screen.setter
    def screen(self, new_screen):
        # устанавливаем размер вьюпорта равным размеру экрана
        self.vp_width, self.vp_height = new_screen.get_size()
        self._screen = new_screen
        # и скейлим фон в соответствии с новой высотой экрана
        bg_scale_factor = self.vp_height / self.bg_texture.get_height()
        bg_height = int(self.bg_texture.get_height() * bg_scale_factor)
        bg_width = int(self.bg_texture.get_width() * bg_scale_factor)
        self.bg_texture = pygame.transform.scale(self.bg_texture, (bg_width, bg_height))

    def _precise_ray(self, ray, step, target, depth=None):
        """
            Когда в более грубом проходе найдена стена, этот метод используется,
            чтобы уточнить точку столкновения луча и стены с точностью step.
            Изменяет переданный вектор
        """
        depth = depth if depth else self.depth
        while ray.length < depth:
            ray.length += step
            test_point = ray.end_point
            if self.level.check_cell(test_point, target):
                break

    def cast_single_ray(self, ray_angle, level=None, origin=None, target=None, depth=None):
        """
        Метод вернёт вектор, направленный в сторону ray_angle;
        модуль вектора будет равняться расстоянию от origin до target,
        если была найдена коллизия с целевым блоком, либо depth, если коллизии не было.
        По-умолчанию метод ищет коллизию со стеной на расстоянии не более глубины прорисовки
        """
        origin = origin if origin else self.player.position
        level = level if level else self.level
        depth = depth if depth else self.depth
        target = target if target else self.level.wall_chars
        ray = raycast.Vector(origin, ray_angle, 0.0)
        while ray.length < depth:
            ray.length += 1
            test_point = ray.end_point
            # проверяем, не вышел ли вектор за карту
            if not level.point_is_present(test_point):
                ray.length = depth
            # проверяем, не упёрся ли вектор в стену
            elif level.check_cell(test_point, target):
                # если нашли стену, то возвращаемся на шаг назад и проходим шажками сначала по 0.1, а затем по 0.01
                ray.length -= 1
                self._precise_ray(ray, 0.1, target, depth=depth)

                ray.length -= 0.1
                self._precise_ray(ray, 0.01, target, depth=depth)
                break
        return ray

    def get_column_coords(self, x):
        """
            Считаем высоту столбца, которая зависит от расстояни до него
        """
        col_height = int(self.vp_height / self.z_map[x])
        # чтобы избавиться от артефактов приводим высоту столбца к чётному числу.
        # В терминале даёт более грубую картинку. Если не нравится - закомментить следующую строку
        col_height = col_height if col_height % 2 == 0 else col_height - 1
        y_top = int(self.vp_height / 2) - col_height
        y_bot = self.vp_height - y_top
        return y_top, y_bot

    def raycast(self):
        """
        Бросаем лучи.
        Разбиваем область видимости (fov) на количество участков, равное ширине экрана/вьюпорта.
        Направлением начала отсчёта будет направление взгляда игрока минус половина области видимости.
        Для каждой координаты x экрана/вьюпорта мы бросаем луч/вектор, последовательно увеличивая его длину.
        Если луч попадает в стену, то записываем длину луча (расстояние до стены) в список и переходим к следующему x.
        Если длина луча стала больше глубины прорисовки, а стену мы так и не нашли,
        то добавляем в список значение глубины прорисовки.
        """
        self.z_map = []
        self.hits = []
        for x in range(0, self.vp_width):
            ray_angle = self.player.dir - (self.fov / 2) + (x / self.vp_width) * self.fov
            current_ray = self.cast_single_ray(ray_angle)
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
                        edge_pos = raycast.Point(int(test_point.x) + block_x, int(test_point.y) + block_y)
                        edge_vector = raycast.Vector(self.player.position, end_point=edge_pos)
                        edge_vectors.append(edge_vector)

            # если мы прямо сейчас добавим расстояние до стены в z-карту,
            # то получим на экране эффект лупы, поэтому умножим расстояние до стены на косинус угла отклонения луча
            dist_factor = math.cos(math.radians(ray_angle - self.player.dir))
            distance_to_wall = distance_to_wall * dist_factor
            distance_to_wall = distance_to_wall if distance_to_wall > 1 else 1
            self.hits.append(current_ray)
            self.z_map.append(distance_to_wall)

    def draw_column(self, x):
        # находим верхнюю и нижнюю ординаты (это не ошибка) стены
        y_top, y_bot = self.get_column_coords(x)
        # берём текстуру, соответствующую блоку, в который попал луч
        texture = self.textures[self.level.get_cell(self.hits[x].end_point)]

        # а теперь немного магии с текстурами:
        # поскольку в пределах одной ячейки карты попадает сразу несколько лучей,
        # то мы можем взять дробную часть от x или y (если x стремится к 0 или 1) точки попадания,
        # умножить это значение на ширину текстуры и получить столбец в текстуре, который надо вывести
        if self.hits[x].end_point.x % 1 < 0.01 or self.hits[x].end_point.x % 1 > 0.99:
            texture_x = int((self.hits[x].end_point.y % 1) * texture.get_width())
        else:
            texture_x = int((self.hits[x].end_point.x % 1) * texture.get_width())

        # теперь вырезаем из текстуры столбец шириной в один пиксель как раз по найденной позиции
        cropped = pygame.Surface((1, texture.get_height()))
        cropped.blit(texture, (0, 0),
                     (texture_x, 0, texture_x + 1, texture.get_height()))
        # меняем высоту столбца на высоту стены и выводим столбец на экран
        cropped = pygame.transform.scale(cropped, (1, y_bot - y_top))
        rect = cropped.get_rect()
        rect = rect.move((x, y_top))
        self._screen.blit(cropped, rect)

        # чтобы было красивее, затеним участки стены: чем дальше от игрока, тем сильнее затемнение.
        # Просто поверх уже нарисованной полоски текстуры рисуем чёрную полоску в 1 пиксель,
        # прозрачность которой и будем регулировать: чем дальше от игрока,
        # тем больше байт прозрачности (то есть прозрачность меньше, а затемнение бильнее)
        transparency = int(255 * (self.z_map[x] / self.depth))
        transparency = transparency if transparency <= 255 else 255
        shadow = pygame.Surface((1, y_bot - y_top), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, transparency))
        self._screen.blit(shadow, rect)

        # И небольшое украшательство: если разница "длин" соседних лучей/расстояний до стены достаточно большая,
        # то считаем, что более "короткий" луч попал в грань блока.
        # Выделим эту грань чёрной линией
        if 0 < x < self.vp_width-1:
            if (self.z_map[x - 1] - self.z_map[x] > 1.5
                    or self.z_map[x + 1] - self.z_map[x] > 1.5):
                color = (0, 0, 0)
                pygame.draw.line(self._screen, color, (x, y_top), (x, y_bot), 1)

    def render_viewport(self):
        self.render_ceil()        # рендерим потолок
        # self.render_floor()     # здесь рендеринг пола нам не пригодится
        self.render_walls()       # рендерим стены

    def render_walls(self):
        for x in range(0, self.vp_width):
            self.draw_column(x)

    def clear_viewport(self):
        # заливаем экран "прозрачным" цветом
        self._screen.fill((0, 0, 0, 0))
        
    def render_floor(self):
        # от половины высоты экрана до низа рисуем градиент от чёрного к белому
        for y in range(self.vp_height // 2, self.vp_height):
            color_byte = int(255 * (y - self.vp_height / 2) / (self.vp_height / 2))
            color = (color_byte, color_byte, color_byte)
            pygame.draw.line(self._screen, color,
                             (0, y), (self.vp_width, y), 1)

    def render_ceil(self):
        # для того, чтобы небо поворачивалось правильно, поступим так же, как и со стенами:
        # будем выводить скайбокс полосками шириной в 1 пиксель, а столбец, который мы будем брать из текстуры,
        # получим разделив угол текущего луча на 360 и умножив эту цифру на ширину текстуры скайбокса
        for x, hit in enumerate(self.hits):
            texture_x = int(hit.angle / 360 * (self.bg_texture.get_width()-1))
            cropped = pygame.Surface((1, self.bg_texture.get_height()))
            cropped.blit(self.bg_texture, (0, 0),
                         (texture_x, 0, texture_x + 1, self.bg_texture.get_height()))
            rect = cropped.get_rect()
            rect = rect.move((x, 0))
            self._screen.blit(cropped, rect)


class Interface:
    """
        Заготовка для интерфейса
    """
    def __init__(self, screen, camera):
        self.screen = screen
        self.camera = camera
        hud_texture = pygame.image.load(os.path.join('assets', 'interface.png')).convert()
        hud_scale_factor = screen.get_width() / hud_texture.get_width()
        self.hud_texture = pygame.transform.scale(hud_texture,
                                                  (int(hud_texture.get_width() * hud_scale_factor),
                                                   int(hud_texture.get_height() * hud_scale_factor)))
        self.frame = self._prepare_frame()

    def clear_viewport(self):
        self.screen.fill((0, 0, 0, 0))

    def draw_minimap(self, position):
        """
            Вывод миникарты
        """
        player = self.camera.player
        level = self.camera.level
        font = pygame.font.SysFont('Courier New', 12)
        arrow_font = pygame.font.Font(os.path.join('assets', 'Meslo LG M Regular for Powerline.ttf'), 12)
        font_size = font.size('#')
        transparency = 128
        text_bg = pygame.Surface((font_size[0] * level.width, font_size[1] * level.height), pygame.SRCALPHA)
        text_bg.fill((0, 0, 0, transparency))
        rect = text_bg.get_rect()
        rect = rect.move((position.x, position.y))
        self.screen.blit(text_bg, rect)

        for y in range(0, level.height):
            self.screen.blit(font.render(level.get_row(y), 0,
                                         (255, 255, 255)), (position.x, position.y + font_size[1] * y))

        self.screen.blit(arrow_font.render(player.get_dir_arrow(), 0, (255, 255, 255)),
                         (position.x + int(player.x) * font_size[0], position.y + int(player.y) * font_size[1]))

    def draw_rays_fixed(self, position, scale=7, transparency=128):
        """
            Вывод неподвижного "радара" препятствий
        """
        rays_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        rect = rays_surface.get_rect()
        for hit in self.camera.hits[::4]:
            vector = raycast.Vector(position, hit.angle - self.camera.player.dir - 90, hit.length * scale)
            pygame.draw.line(rays_surface, (255, 255, 255, transparency),
                             (vector.start_point.x, vector.start_point.y), (vector.end_point.x, vector.end_point.y), 1)
        pygame.draw.line(rays_surface, (255, 0, 0),
                         (position.x, position.y), (position.x, position.y - self.camera.depth * scale), 1)
        self.screen.blit(rays_surface, rect)

    def draw_rays(self, position, scale=7, transparency=128):
        """
            Вывод потовротного "радара" препятствий
        """
        player_vector = raycast.Vector(self.camera.player.position, self.camera.player.dir, self.camera.depth * scale)
        player_endpoint = raycast.Point(player_vector.end_point.x + position.x, player_vector.end_point.y + position.y)
        player_pos = raycast.Point(self.camera.player.x + position.x, self.camera.player.y + position.y)

        for hit in self.camera.hits:
            vector = raycast.Vector(self.camera.player.position, hit.angle, hit.length * scale)
            hit_pos = raycast.Point(vector.end_point.x + position.x, vector.end_point.y + position.y)
            pygame.draw.line(self.screen, (255, 255, 255, transparency),
                             (player_pos.x, player_pos.y), (hit_pos.x, hit_pos.y), 1)

        pygame.draw.line(self.screen, (255, 0, 0, transparency),
                         (player_pos.x, player_pos.y), (player_endpoint.x, player_endpoint.y), 1)

    def _prepare_frame(self):
        # нарисуем заранее рамку вокруг игрового поля, чтобы не тратить на неё ресурсы позже
        frame = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        hud_y = self.screen.get_height() - self.hud_texture.get_height()
        # рамка
        frame_width = self.screen.get_width() // 30
        inner_frame_width = self.screen.get_width() // 240
        right_bot = raycast.Point(self.screen.get_width(), self.screen.get_height())
        # толстая обводка
        pygame.draw.rect(frame, (44, 76, 76),
                         (0, 0, right_bot.x, right_bot.y), frame_width)
        # верхняя горизонтальная линия
        pygame.draw.line(frame, (0, 0, 0),
                         (frame_width // 2, frame_width // 2),
                         (right_bot.x - frame_width // 2, frame_width // 2), inner_frame_width)
        # правая вертикальная
        pygame.draw.line(frame, (0, 0, 0),
                         (right_bot.x - frame_width // 2, frame_width // 2),
                         (right_bot.x - frame_width // 2, hud_y - inner_frame_width), inner_frame_width)
        # левая вертикальная
        pygame.draw.line(frame, (72, 123, 124),
                         (frame_width // 2, frame_width // 2),
                         (frame_width // 2, hud_y - inner_frame_width), inner_frame_width)
        # нижняя горизонтальная
        pygame.draw.line(frame, (72, 123, 124),
                         (frame_width // 2, hud_y - inner_frame_width),
                         (right_bot.x - frame_width // 2, hud_y - inner_frame_width),
                         inner_frame_width)
        return frame

    def draw_hud(self):
        """
            Рисуем интерфейс.
            В дальнейшем в этом методе могут выводиться параметры игрока и игры (здоровье, патроны и т.д.)
        """
        # выводим рамку
        self.screen.blit(self.frame, self.frame.get_rect())
        # интерфейс
        rect = self.hud_texture.get_rect()
        hud_y = self.screen.get_height() - self.hud_texture.get_height()
        rect = rect.move((0, hud_y))
        self.screen.blit(self.hud_texture, rect)


def get_root_screen(resolution):
    """
        Инициализация экрана для рисования
    """
    pygame.init()
    pygame.font.init()
    screen_rectangle = pgl.Rect((0, 0), resolution)
    screen = pygame.display.set_mode(screen_rectangle.size)
    pygame.display.set_caption('Pygame FPS')
    pygame.display.flip()
    return screen


def main_game():
    root_screen = get_root_screen((480, 360))
    game_screen = pygame.Surface((480, 360))
    interface_screen = pygame.Surface((480, 360), pygame.SRCALPHA)

    level = raycast.Level(*map_size, map_content)
    level.wall_chars = wall_chars
    player = raycast.Player(raycast.Point(2.0, 2.0), 45.0)
    camera = PGCamera(game_screen, level, player, fov=60)
    interface = Interface(interface_screen, camera)
    # уменьшим игровой экран на высоту интерфейса,
    # чтобы сместить центр игрового экрана в середину свободной от интерфейса области
    game_screen = pygame.Surface((480, 360 - interface.hud_texture.get_height()))
    camera.screen = game_screen

    while True:  # игровой цикл
        # реагируем на клавиатуру
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()

        keys = pygame.key.get_pressed()
        if keys[pgl.K_w]:
            player.move_forward()
            if level.is_wall(player.position):
                player.move_back()
        if keys[pgl.K_s]:
            player.move_back()
            # если упёрлись в стену, то откатываем шаг
            if level.is_wall(player.position):
                player.move_forward()
        if keys[pgl.K_d]:
            player.turn_right()
        if keys[pgl.K_a]:
            player.turn_left()

        # считаем расстояния
        camera.raycast()
        # очищаем игровой и интерфейсный экраны
        camera.clear_viewport()
        interface.clear_viewport()

        # рендерим игру, основной интерфейс и дополнительные вещи
        camera.render_viewport()
        interface.draw_hud()
        # interface.draw_minimap(fps.Point(0, 0))
        interface.draw_rays_fixed(raycast.Point(camera.vp_width // 2 + 100, camera.vp_height // 2 + 100))

        # накладываем игровой и интерфейсный экраны на основной и показываем игроку
        root_screen.blit(game_screen, game_screen.get_rect())
        root_screen.blit(interface_screen, interface_screen.get_rect())
        pygame.display.flip()


if __name__ == '__main__':
    main_game()
