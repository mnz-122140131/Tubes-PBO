import pygame, sys, math, random, time
from pygame import Vector2
from pygame import mixer
from abc import ABC, abstractmethod

pygame.init()
info = pygame.display.Info()
screen = pygame.display.set_mode((800, 800), pygame.RESIZABLE)
pygame.display.set_caption("Ghost Jump")

class Settings:
    def __init__(self):
        self.is_fullscreen = False
        self.volume = 0.3
        self.is_menu = True
        self.is_character_selection = False
        self.is_settings_menu = False
        self.is_paused = False
        self.is_background_selection = False
        self.selected_character = None
        self.selected_background = "data/images/latargame.jpg"
        self.start_game = False
        self.dt = 0.1

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            return pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
        else:
            return pygame.display.set_mode((800, 800), pygame.RESIZABLE)

    def change_volume(self, change):
        self.volume = max(0, min(1, self.volume + change))
        mixer.music.set_volume(self.volume)
        print(f"Volume: {self.volume}")

settings = Settings()

class GameObject(ABC):
    def __init__(self, position):
        self._position = position

    @abstractmethod
    def draw(self, screen):
        pass

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value

class GameCharacter(GameObject):
    def __init__(self, position, sprite):
        super().__init__(position)
        self._sprite = sprite

    def draw(self, screen):
        screen.blit(self._sprite, (self._position.x, self._position.y))

class Player(GameCharacter):
    def __init__(self, position, sprite):
        super().__init__(position, sprite)
        self.is_dead = False
        self._score = 0
        self.velocity = Vector2()
        self.rotation = Vector2()
        self.offset = Vector2()
        self.gun = Gun()
        self.drag = 100
        self.gravity_scale = 300
        self.shield_sprite = None
        self.shield_sprite_duration = 3
        self.shield_sprite_timer = 0
        self.shield_alpha = 255

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, value):
        self._score = value

    def move(self):
        self.gravity()
        self.air_resistance()
        self.wall_detection()
        self.position.x -= self.velocity.x * settings.dt
        self.position.y -= self.velocity.y * settings.dt
        self.update_shield_sprite()

    def handle_gun(self):
        self.gun.set_position(self.position)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        rel_x, rel_y = mouse_x - self.position.x, mouse_y - self.position.y
        angle = (180 / math.pi) * -math.atan2(rel_y, rel_x)
        self.gun.set_rotation(angle)

        if self.offset.x > 0:
            self.offset.x = rel_x if rel_x < 2 else 2
        else:
            self.offset.x = rel_x if rel_x > -2 else -2
        if self.offset.y > 0:
            self.offset.y = rel_y if rel_y < 1.5 else 1.5
        else:
            self.offset.y = rel_y if rel_y > -1.5 else -1.5

    def update_shield_sprite(self):
        if self.shield_sprite_timer > 0:
            self.shield_sprite_timer -= settings.dt
            self.update_shield_alpha()
        else:
            self.shield_sprite = None

    def update_shield_alpha(self):
        remaining_time_percentage = self.shield_sprite_timer / self.shield_sprite_duration
        self.shield_alpha = int(255 * remaining_time_percentage)
        self.shield_sprite.set_alpha(self.shield_alpha)

    def gravity(self):
        self.velocity.y -= self.gravity_scale * settings.dt

    def air_resistance(self):
        self.velocity.y -= self.drag * settings.dt if self.velocity.y > 0 else 0
        self.velocity.x -= (self.drag - 50) * settings.dt if self.velocity.x > 0 else (self.drag - 50) * settings.dt if self.velocity.x < 0 else 0

    def wall_detection(self):
        screen_width, screen_height = screen.get_size()
        if self.position.x < 0:
            self.position.x = screen_width
        if self.position.x > screen_width:
            self.position.x = 0

    def check_state(self):
        if self.is_dead:
            try:
                with open("data/serialisation/highscore.txt", "r") as highscore_file:
                    old_highscore_value = highscore_file.readline()
                if self.score > int(old_highscore_value):
                    with open("data/serialisation/highscore.txt", "w") as highscore_value:
                        highscore_value.write(str(self.score))
            except FileNotFoundError:
                print("Error: Highscore file not found.")
            except Exception as e:
                print("Error:", e)

            settings.is_menu = True
            settings.is_character_selection = True
            settings.selected_character = None

    def collision_detection(self, level_builder):
        for collectible in level_builder.collectibles:
            if self.get_bounds().colliderect(collectible.get_bounds()):
                if collectible.collectible_type == "soul":
                    self.gun.soul_count += 1
                    level_builder.collectibles.remove(collectible)
                    level_builder.repopulate_collectible("soul")
                    self.score += 1
                elif collectible.collectible_type == "baby":
                    self.gun.soul_count += 3
                    level_builder.collectibles.remove(collectible)
                    level_builder.repopulate_collectible("baby")
                    self.score += 3
                elif collectible.collectible_type == "enemy":
                    if not self.ignore_enemy_collision():
                        self.is_dead = True
                elif collectible.collectible_type == "shield":
                    self.ignore_enemy_collision(3)
                    self.show_shield_sprite()
                    level_builder.collectibles.remove(collectible)
                    level_builder.repopulate_collectible("shield")

        if self.position.y > screen.get_height():
            self.is_dead = True

    def show_shield_sprite(self):
        sound = mixer.Sound("data/audio/Shield.mp3")
        sound.set_volume(0.5)
        sound.play()
        self.shield_sprite = pygame.image.load('data/images/shield.png').convert_alpha()
        self.shield_sprite = pygame.transform.scale(self.shield_sprite, (90, 120))
        self.shield_sprite_timer = self.shield_sprite_duration
        self.shield_alpha = 255

    def ignore_enemy_collision(self, duration=None):
        if duration is not None:
            self.ignore_enemy_collision_until = time.time() + duration
        return time.time() < getattr(self, 'ignore_enemy_collision_until', 0)

    def get_bounds(self):
        return pygame.Rect(self.position.x - (self._sprite.get_width() // 2),
                           self.position.y - (self._sprite.get_height() // 2),
                           self._sprite.get_width(),
                           self._sprite.get_height())

    def draw(self, screen):
        self.gun.draw(screen)
        screen.blit(self._sprite, self.blit_position())
        if self.shield_sprite:
            self.shield_sprite.set_alpha(self.shield_alpha)
            screen.blit(self.shield_sprite, (self.position.x - self.shield_sprite.get_width() // 2, self.position.y - self.shield_sprite.get_height() // 2))
        pygame.draw.circle(screen, (170, 10, 10), (self.position.x  - 5 + self.offset.x, self.position.y - 7 + self.offset.y), 3)
        pygame.draw.circle(screen, (170, 10, 10), (self.position.x  + 10 + self.offset.x , self.position.y - 7 + self.offset.y ), 3)

    def blit_position(self):
        return (self.position.x - (self._sprite.get_width() // 2), self.position.y - (self._sprite.get_height() // 2))

    def shoot(self):
        if self.gun.soul_count <= 0:
            return
        mouse_x, mouse_y = pygame.mouse.get_pos()
        rel_x, rel_y = mouse_x - self.position.x, mouse_y - self.position.y
        vector = Vector2()
        vector.xy = rel_x, rel_y
        mag = vector.magnitude()
        vector.xy /= mag
        self.velocity.y = 0
        self.velocity.x = 0
        self.add_force(vector, 500)

    def add_force(self, vector, magnitude):
        self.velocity.x += vector.x * magnitude
        self.velocity.y += vector.y * magnitude

class Explosion(GameObject):
    def __init__(self, position):
        super().__init__(position)
        self.width = 20

    def draw(self, screen):
        pygame.draw.circle(screen, (220, 0, 0), self.position, self.width)
        pygame.draw.circle(screen, (255, 153, 51), self.position, self.width - (self.width // 2))
    
    def scale_down(self):
        if self.width > 0:
            self.width -= settings.dt * 50

class Collectible(GameObject):
    def __init__(self, position, collectible_type):
        super().__init__(position)
        self.collectible_type = collectible_type
        self.load_sprite()

    def load_sprite(self):
        if self.collectible_type == "soul":
            self.sprite = pygame.image.load('data/images/Soul.png')
            self.sprite = pygame.transform.scale(self.sprite, (30, 40))
        elif self.collectible_type == "baby":
            self.sprite = pygame.image.load('data/images/Baby.png')
            self.sprite = pygame.transform.scale(self.sprite, (70, 80))
        elif self.collectible_type == "shield":
            self.sprite = pygame.image.load('data/images/shield.png')
            self.sprite = pygame.transform.scale(self.sprite, (40, 50))
        elif self.collectible_type == "enemy":
            rand = random.randint(0, 1)
            if rand == 0:
                self.sprite = pygame.image.load('data/images/Nail.png')
            else:
                self.sprite = pygame.image.load('data/images/Fish.png')
            self.sprite = pygame.transform.scale(self.sprite, (30, 50))
            self.gravity_scale = random.randint(20, 40)

    def draw(self, screen):
        screen.blit(self.sprite, self.position)
        if self.collectible_type == "enemy":
            self.apply_gravity()

    def apply_gravity(self):
        self.position.y += self.gravity_scale * settings.dt

    def get_bounds(self):
        return pygame.Rect(self.position.x, self.position.y, self.sprite.get_width(), self.sprite.get_height())

class Gun(GameObject):
    def __init__(self):
        self.gun_sprite = None
        self.position = Vector2()
        self.is_flipped = False
        self._soul_count = 3
        pygame.font.init()
        self.font = pygame.font.Font("data/fonts/Montserrat-ExtraBold.ttf", 300)
        self.refresh_sprite()
        self.explosions = []

    @property
    def soul_count(self):
        return self._soul_count

    @soul_count.setter
    def soul_count(self, value):
        self._soul_count = value

    def render_current_ammo(self, screen):
        text = self.font.render(str(self.soul_count), False, (0, 0, 0))
        text_rect = text.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
        screen.blit(text, text_rect)
        outline_color = (0, 0, 0)

        text = self.font.render(str(self.soul_count), False, (150, 150, 150))
        text_rect = text.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2.08))
        screen.blit(text, text_rect)
        outline_color = (0, 0, 0)

    def shoot(self):
        if self._soul_count > 0:
            sound = mixer.Sound("data/audio/Gunshot.wav")
            sound.set_volume(0.1)
            sound.play()
            exp_pos = Vector2(self.position)
            mouse_x, mouse_y = pygame.mouse.get_pos()
            rel_x, rel_y = mouse_x - self.position.x, mouse_y - self.position.y
            mag = Vector2(rel_x, rel_y).magnitude()
            exp_pos.x += (rel_x / mag) * 100
            exp_pos.y += (rel_y / mag) * 100
            explosion = Explosion(exp_pos)
            self.explosions.append(explosion)
            self._soul_count -= 1
        else:
            sound = mixer.Sound("data/audio/CantShoot.wav")
            sound.set_volume(0.08)
            sound.play()

    def explode(self, screen):
        for explosion in self.explosions:
            if explosion.width <= 1:
                self.explosions.remove(explosion)
                break
            explosion.scale_down()
            explosion.draw(screen)

    def refresh_sprite(self):
        self.gun_sprite = pygame.image.load('data/images/Gun.png')
        self.gun_sprite = pygame.transform.scale(self.gun_sprite, (200, 200))

    def draw(self, screen):
        screen.blit(self.gun_sprite, self.blit_position())
        self.explode(screen)

    def set_position(self, position):
        self.position = position
    
    def set_rotation(self, degrees):
        self.refresh_sprite()
        self.gun_sprite = pygame.transform.rotate(self.gun_sprite, degrees)
          
    def blit_position(self):
        return self.position.x - (self.gun_sprite.get_width() // 2), self.position.y - (self.gun_sprite.get_height() // 2)

class SelectionScreen:
    def __init__(self, screen, mode='character'):
        self.screen = screen
        self.mode = mode
        self.background = pygame.image.load("data/images/latarhome.jpg").convert()

        self.characters = [
            pygame.image.load("data/images/Player1.png"),
            pygame.image.load("data/images/Player2.png"),
            pygame.image.load("data/images/Player3.png"),
            pygame.image.load("data/images/Player4.png")
        ]
        self.character_rects = []

        self.backgrounds = [
            pygame.image.load("data/images/latargame.jpg"),
            pygame.image.load("data/images/latargame2.jpg"),
            pygame.image.load("data/images/latargame3.jpg")
        ]
        self.background_rects = []

        self.back_button_rect = pygame.Rect(10, 10, 100, 50)
        self.init_rects()
        self.show_selection_screen()

    def init_rects(self):
        screen_width, screen_height = self.screen.get_size()
        
        if self.mode == 'character':
            num_items = len(self.characters)
            total_width = num_items * 200
            start_x = (screen_width - total_width) // 2

            for i, character in enumerate(self.characters):
                rect = character.get_rect(center=(start_x + i * 200 + 100, screen_height // 2))
                self.character_rects.append(rect)
        
        elif self.mode == 'background':
            num_items = len(self.backgrounds)
            total_width = num_items * 320 + (num_items - 1) * 20 if settings.is_fullscreen else num_items * 230 + (num_items - 1) * 20
            start_x = (screen_width - total_width) // 2

            for i, background in enumerate(self.backgrounds):
                scaled_background = pygame.transform.scale(background, (320, 320) if settings.is_fullscreen else (230, 230))
                rect = scaled_background.get_rect(center=(start_x + i * (320 + 20) + 160 if settings.is_fullscreen else start_x + i * (230 + 20) + 115, screen_height // 2))
                self.background_rects.append(rect)

    def draw_hover_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        color = (180, 20, 20) if rect.collidepoint(mouse_pos) else (160, 160, 160)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        font = pygame.font.Font("data/fonts/Melted Monster.ttf", 30)
        text_rendered = font.render(text, False, (0, 0, 0))
        self.screen.blit(text_rendered, (rect.centerx - text_rendered.get_width() // 2, rect.centery - text_rendered.get_height() // 2))

    def show_selection_screen(self):
        while settings.is_character_selection or settings.is_background_selection:
            self.clear_screen()

            if self.mode == 'character':
                for i, character in enumerate(self.characters):
                    mouse_pos = pygame.mouse.get_pos()
                    if self.character_rects[i].collidepoint(mouse_pos):
                        enlarged_character = pygame.transform.scale(character, (character.get_width() + 20, character.get_height() + 20))
                        enlarged_rect = enlarged_character.get_rect(center=self.character_rects[i].center)
                        self.screen.blit(enlarged_character, enlarged_rect.topleft)
                    else:
                        self.screen.blit(character, self.character_rects[i].topleft)
                
                font_size = 60 if settings.is_fullscreen else 40
                text_position = (self.screen.get_width() // 2, 150 if settings.is_fullscreen else 100)
                font = pygame.font.Font("data/fonts/Melted Monster.ttf", font_size)
                text = font.render("Select Your Character", False, (170, 10, 10))
                text_rect = text.get_rect(center=text_position)
                self.screen.blit(text, text_rect)
                
            elif self.mode == 'background':
                for i, background in enumerate(self.backgrounds):
                    mouse_pos = pygame.mouse.get_pos()
                    scaled_background = pygame.transform.scale(background, (320, 320) if settings.is_fullscreen else (230, 230))
                    enlarged_background = pygame.transform.scale(background, (340, 340) if settings.is_fullscreen else (250, 250)) if self.background_rects[i].collidepoint(mouse_pos) else scaled_background
                    rect = enlarged_background.get_rect(center=self.background_rects[i].center) if self.background_rects[i].collidepoint(mouse_pos) else self.background_rects[i]
                    self.screen.blit(enlarged_background, rect.topleft)
                
                font_size = 60 if settings.is_fullscreen else 40
                text_position = (self.screen.get_width() // 2, 150 if settings.is_fullscreen else 100)
                font = pygame.font.Font("data/fonts/Melted Monster.ttf", font_size)
                text = font.render("Select Your Background", False, (170, 10, 10))
                text_rect = text.get_rect(center=text_position)
                self.screen.blit(text, text_rect)

            self.draw_hover_button(self.back_button_rect, "Back")
            pygame.display.flip()
            self.handle_events()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                if self.back_button_rect.collidepoint(mouse_pos):
                    if self.mode == 'character':
                        settings.is_character_selection = False
                        settings.is_menu = True
                    elif self.mode == 'background':
                        settings.is_background_selection = False
                        settings.is_character_selection = True
                        self.mode = 'character'
                        self.init_rects()
                else:
                    if self.mode == 'character':
                        for i, rect in enumerate(self.character_rects):
                            if rect.collidepoint(mouse_pos):
                                settings.selected_character = self.characters[i]
                                settings.is_character_selection = False
                                settings.is_background_selection = True
                                self.mode = 'background'
                                self.init_rects()
                                break
                    elif self.mode == 'background':
                        for i, rect in enumerate(self.background_rects):
                            if rect.collidepoint(mouse_pos):
                                settings.selected_background = ["data/images/latargame.jpg", "data/images/latargame2.jpg", "data/images/latargame3.jpg"][i]
                                settings.is_background_selection = False
                                settings.start_game = True
                                show_loading_screen(self.screen)
                                return

    def clear_screen(self):
        self.screen.blit(self.background, (0, 0))

def show_loading_screen(screen, duration=3.0):
    start_time = time.time()
    font = pygame.font.Font("data/fonts/Melted Monster.ttf", 60)
    text = "Loading..."
    text_surfaces = [font.render(char, False, (255, 255, 255)) for char in text]
    text_red_surfaces = [font.render(char, False, (170, 0, 0)) for char in text]
    while time.time() - start_time < duration:
        screen.fill((0, 0, 0))
        
        elapsed_time = time.time() - start_time
        num_chars_to_color = int(len(text) * (elapsed_time / duration))
        
        x_offset = (screen.get_width() - sum(surf.get_width() for surf in text_surfaces)) // 2
        y_offset = screen.get_height() // 2.8
        
        for i, (white_surf, red_surf) in enumerate(zip(text_surfaces, text_red_surfaces)):
            if i < num_chars_to_color:
                screen.blit(red_surf, (x_offset, y_offset))
            else:
                screen.blit(white_surf, (x_offset, y_offset))
            x_offset += white_surf.get_width()
        
        if settings.is_fullscreen:
            font_size = 30
            text_position = (screen.get_width() // 2, screen.get_height() - 250)
        else:
            font_size = 20
            text_position = (screen.get_width() // 2, screen.get_height() - 200)
        
        font_small = pygame.font.Font("data/fonts/Melted Monster.ttf", font_size)
        instructions_text = font_small.render("Tekan spasi jika ingin pause atau melanjutkan game", False, (255, 255, 255))
        instructions_rect = instructions_text.get_rect(center=text_position)
        screen.blit(instructions_text, instructions_rect)
        pygame.display.flip()
        pygame.time.delay(50)

class Game:
    def __init__(self, screen):
        self.screen = screen
        self.load_background()
        self.player = Player(Vector2(400, 200), pygame.transform.scale(settings.selected_character, (50, 60)))
        self.collectibles = []
        self.clock = pygame.time.Clock()
        self.score = 0
        self.load_music()
        self.play_music()
        self.enemy_iteration = 0
        self.wave_iteration = 0
        self.is_game_over = False
        self.populate_collectibles()
        self.update()

    def load_background(self):
        self.background = pygame.image.load(settings.selected_background).convert()
        self.background = pygame.transform.scale(self.background, self.screen.get_size())

    def load_music(self):
        mixer.init()
        mixer.music.load("data/audio/songgame.mp3")

    def play_music(self):
        mixer.music.set_volume(0.2)
        mixer.music.play(-1)

    def stop_music(self):
        mixer.music.stop()

    def populate_collectibles(self):
        self.populate_collectible("soul", 2)
        self.populate_collectible("baby", 1)
        self.populate_collectible("shield", 1)

    def populate_collectible(self, collectible_type, count):
        screen_width, screen_height = self.screen.get_size()
        for _ in range(count):
            pos = Vector2()
            pos.x = random.randint(100, screen_width - 100)
            pos.y = random.randint(100, screen_height - 100)
            collectible = Collectible(pos, collectible_type)
            self.collectibles.append(collectible)

    def spawn_enemies(self, count):
        screen_width = self.screen.get_width()
        for _ in range(count):
            pos = Vector2()
            pos.x = random.randint(0, screen_width - 40)
            pos.y = -35
            enemy = Collectible(pos, "enemy")
            self.collectibles.append(enemy)

    def repopulate_collectible(self, collectible_type):
        self.collectibles = [c for c in self.collectibles if c.collectible_type != collectible_type]
        if collectible_type == "soul":
            self.populate_collectible("soul", 2)
        elif collectible_type == "baby":
            self.populate_collectible("baby", 1)
        elif collectible_type == "shield":
            self.populate_collectible("shield", 1)

    def update(self):
        next_time = time.time()
        elapsed_time = time.time()
        min_time = 5
        max_time = 10
        while not settings.is_menu and not settings.is_character_selection:
            self.handle_dt()
            self.clear_screen()

            if not settings.is_paused:
                self.player.gun.render_current_ammo(screen)
                self.draw_collectibles()
                self.player.move()
                self.player.handle_gun()
                self.player.collision_detection(self)
                self.player.check_state()
                self.player.draw(self.screen)

                self.score = self.player.score
                self.render_score()
                self.render_wave()

            if settings.is_paused:
                self.render_pause_screen()

            pygame.display.flip()
            self.handle_events()

            self.player.check_state()
            if self.player.is_dead:
                self.is_game_over = True
                game_over_screen = GameOverScreen(self.screen, self.player.score)
                result = game_over_screen.show_game_over_screen()
                if result == "back_to_home":
                    settings.is_menu = True

            if self.is_game_over:
                mixer.music.play(-1)
                self.stop_music()

            elapsed_time = time.time()
            if elapsed_time > next_time:
                next_time = elapsed_time + random.randint(min_time, max_time)
                self.spawn_enemies(random.randint(1, 3))
                self.enemy_iteration += 1
                self.wave_iteration += 1
                if self.enemy_iteration > 2 and min_time > 1:
                    min_time -= 1
                    max_time -= 1
                    self.enemy_iteration = 0

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    settings.is_paused = not settings.is_paused
            if event.type == pygame.MOUSEBUTTONDOWN and not settings.is_paused:
                self.player.shoot()
                self.player.gun.shoot()

    def clear_screen(self):
        screen_width, screen_height = self.screen.get_size()
        background = pygame.transform.scale(self.background, (screen_width, screen_height))
        self.screen.blit(background, (0, 0))

    def handle_dt(self):
        settings.dt = self.clock.tick() / 1000

    def render_pause_screen(self):
        font = pygame.font.Font("data/fonts/Melted Monster.ttf", 100)
        pause_text = font.render("Paused", False, (255, 255, 255))
        text_rect = pause_text.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 - 50))
        self.screen.blit(pause_text, text_rect)

    def render_wave(self):
        font = pygame.font.Font("data/fonts/Montserrat-ExtraBold.ttf", 30)
        wave_text = font.render("Wave: " + str(self.wave_iteration), True, (180, 180, 180))
        screen_width = self.screen.get_width()
        text_rect = wave_text.get_rect(topright=(screen_width - 10, 10))
        self.screen.blit(wave_text, text_rect.topleft)

    def render_score(self):
        font = pygame.font.Font("data/fonts/Montserrat-ExtraBold.ttf", 30)
        score_text = font.render("Score: " + str(self.score), True, (180, 180, 180))
        self.screen.blit(score_text, (10, 10))

    def draw_collectibles(self):
        for collectible in self.collectibles:
            collectible.draw(self.screen)
            if collectible.collectible_type == "enemy" and collectible.position.y > self.screen.get_height():
                self.collectibles.remove(collectible)

class GameOverScreen:
    def __init__(self, screen, score):
        self.background_color = 240, 240, 240
        self.screen = screen
        self.score = score
        self.screen_center = screen.get_rect().center
        self.is_hovered = False

        button_width = 300
        button_height = 50
        screen_width, screen_height = self.screen.get_size()
        button_x = (screen_width - button_width) // 2
        button_y = 450
        self.back_to_home_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)

    def show_game_over_screen(self):
        pygame.font.init()

        while True:
            self.clear_screen()

            font = pygame.font.Font("data/fonts/BLOODY.ttf", 70)
            text = font.render("Game Over", False, (100, 100, 100))
            text_rect = text.get_rect(center=(self.screen_center[0], self.screen_center[1]-100))
            self.screen.blit(text, text_rect)

            font = pygame.font.Font("data/fonts/BLOODY.ttf", 30)
            score_text = font.render("Your Score: " + str(self.score), False, (180, 180, 180))
            score_text_rect = score_text.get_rect(center=(self.screen_center[0], self.screen_center[1]-30))
            self.screen.blit(score_text, score_text_rect)

            button_color = (105, 10, 20) if not self.is_hovered else (180, 180, 180)
            pygame.draw.rect(self.screen, button_color, self.back_to_home_button_rect)
            font = pygame.font.Font("data/fonts/BLOODY.ttf", 30)
            back_to_home_text = font.render("Back to Home", False, (0, 0, 0))
            back_to_home_text_rect = back_to_home_text.get_rect(center=self.back_to_home_button_rect.center)
            self.screen.blit(back_to_home_text, back_to_home_text_rect)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()
                    if self.back_to_home_button_rect.collidepoint(mouse_pos):
                        settings.is_character_selection = True
                        settings.is_menu = True
                        return "back_to_home"
                if event.type == pygame.MOUSEMOTION:
                    self.is_hovered = self.back_to_home_button_rect.collidepoint(event.pos)

    def clear_screen(self):
        self.screen.fill((0, 0, 0))

class Menu:
    def __init__(self, screen):
        self.background_color = 240, 240, 240
        self.background = pygame.image.load("data/images/latarhome.jpg").convert()
        self.quit_button_size_halfscreen = 60
        self.quit_button_size_fullscreen = 80
        self.quit_button_margin = 20
        self.screen = screen
        self.set_quit_button_position()
        self.play_button_rect = pygame.Rect(250, 300, 300, 50)
        self.help_button_rect = pygame.Rect(250, 370, 300, 50)
        self.settings_button_rect = pygame.Rect(250, 440, 300, 50)
        self.instructions_visible = False
        self.initial_button_positions = {
            "play": self.play_button_rect.center,
            "help": self.help_button_rect.center,
            "settings": self.settings_button_rect.center
        }
        self.back_button_rect = pygame.Rect(250, 510, 300, 50)
        self.fullscreen_button_rect = pygame.Rect(250, 300, 300, 50)
        self.volume_up_button_rect = pygame.Rect(250, 370, 140, 50)
        self.volume_down_button_rect = pygame.Rect(410, 370, 140, 50)
        self.is_settings_menu = False
        self.show_menu()
        self.center_buttons()

    def set_quit_button_position(self):
        screen_width, screen_height = self.screen.get_size()
        quit_button_size = self.quit_button_size_fullscreen if settings.is_fullscreen else self.quit_button_size_halfscreen
        quit_button_x = screen_width - quit_button_size - self.quit_button_margin
        quit_button_y = screen_height - quit_button_size - self.quit_button_margin
        self.quit_button_rect = pygame.Rect(quit_button_x, quit_button_y, quit_button_size, quit_button_size)

    def center_buttons(self):
        screen_width, screen_height = self.screen.get_size()
        button_width = 300
        button_height = 50
        button_x = (screen_width - button_width) // 2
        button_margin = 20

        play_button_y = 330
        self.play_button_rect = pygame.Rect(button_x, play_button_y, button_width, button_height)

        help_button_y = play_button_y + button_height + button_margin
        self.help_button_rect = pygame.Rect(button_x, help_button_y, button_width, button_height)

        settings_button_y = help_button_y + button_height + button_margin
        self.settings_button_rect = pygame.Rect(button_x, settings_button_y, button_width, button_height)

        fullscreen_button_y = 300
        self.fullscreen_button_rect = pygame.Rect(button_x, fullscreen_button_y, button_width, button_height)

        volume_up_button_y = fullscreen_button_y + button_height + button_margin
        self.volume_up_button_rect = pygame.Rect(button_x, volume_up_button_y, 140, button_height)

        volume_down_button_y = volume_up_button_y
        self.volume_down_button_rect = pygame.Rect(button_x + 160, volume_down_button_y, 140, button_height)

        back_button_y = volume_down_button_y + button_height + button_margin
        self.back_button_rect = pygame.Rect(button_x, back_button_y, button_width, button_height)

        self.set_quit_button_position()

    def show_menu(self):
        pygame.font.init()

        sound = mixer.Sound("data/audio/Error.wav")
        sound.set_volume(0.05)
        sound.play()

        highscore_value = ""
        try:
            with open("data/serialisation/highscore.txt", "r") as highscore_file:
                highscore_value = highscore_file.readline()
        except FileNotFoundError:
            print("Error: Highscore file not found.")
        except Exception as e:
            print("Error:", e)

        while settings.is_menu or self.is_settings_menu:
            self.clear_screen()
            self.center_buttons()

            if settings.is_menu:
                self.draw_main_menu(highscore_value)
            elif self.is_settings_menu:
                self.draw_settings_menu()

            pygame.display.flip()
            self.handle_events()

    def draw_main_menu(self, highscore_value):
        font = pygame.font.Font("data/fonts/Melted Monster.ttf", 100)
        text = font.render("Ghost Jump", False, (170, 10, 10))
        text_x = (self.screen.get_width() - text.get_width()) // 2
        text_y = 150
        self.screen.blit(text, (text_x, text_y))

        self.draw_button(self.quit_button_rect, "Quit")
        self.draw_button(self.play_button_rect, "Play")
        self.draw_button(self.help_button_rect, "Help")
        self.draw_button(self.settings_button_rect, "Settings")

        if self.instructions_visible:
            self.display_instructions()
        else:
            highscore_font_size = 50 if settings.is_fullscreen else int(self.screen.get_width() * 0.04)
            font = pygame.font.Font("data/fonts/Melted Monster.ttf", highscore_font_size)
            highscore = font.render("Highscore: " + str(highscore_value), False, (180, 180, 180))
            highscore_rect = highscore.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() * 0.65 if settings.is_fullscreen else self.screen.get_height() * 0.75))
            self.screen.blit(highscore, highscore_rect)

    def draw_settings_menu(self):
        font = pygame.font.Font("data/fonts/Melted Monster.ttf", 80)
        text = font.render("Settings", False, (170, 10, 10))
        text_x = (self.screen.get_width() - text.get_width()) // 2
        text_y = 150
        self.screen.blit(text, (text_x, text_y))

        self.draw_button(self.back_button_rect, "Back")
        self.draw_button(self.fullscreen_button_rect, "Fullscreen" if not settings.is_fullscreen else "Halfscreen")
        self.draw_button(self.volume_up_button_rect, "Volume +")
        self.draw_button(self.volume_down_button_rect, "Volume -")

    def clear_screen(self):
        self.screen.blit(self.background, (0, 0))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                if settings.is_menu:
                    self.handle_main_menu_events(mouse_pos)
                elif self.is_settings_menu:
                    self.handle_settings_menu_events(mouse_pos)

    def handle_main_menu_events(self, mouse_pos):
        if self.play_button_rect.collidepoint(mouse_pos):
            settings.is_menu = False
            settings.is_character_selection = True
        elif self.help_button_rect.collidepoint(mouse_pos):
            self.instructions_visible = not self.instructions_visible
        elif self.settings_button_rect.collidepoint(mouse_pos):
            settings.is_menu = False
            self.is_settings_menu = True
        elif self.quit_button_rect.collidepoint(mouse_pos):
            sys.exit()

    def handle_settings_menu_events(self, mouse_pos):
        if self.back_button_rect.collidepoint(mouse_pos):
            self.is_settings_menu = False
            settings.is_menu = True
        elif self.fullscreen_button_rect.collidepoint(mouse_pos):
            settings.screen = settings.toggle_fullscreen()
        elif self.volume_up_button_rect.collidepoint(mouse_pos):
            settings.change_volume(0.1)
        elif self.volume_down_button_rect.collidepoint(mouse_pos):
            settings.change_volume(-0.1)

    def draw_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        color = (180, 20, 20) if rect.collidepoint(mouse_pos) else (160, 160, 160)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        font = pygame.font.Font("data/fonts/Melted Monster.ttf", 30)
        text_rendered = font.render(text, False, (0, 0, 0))
        self.screen.blit(text_rendered, (rect.centerx - text_rendered.get_width() // 2, rect.centery - text_rendered.get_height() // 2))

    def display_instructions(self):
        try:
            with open("data/serialisation/instruction.txt", "r") as file:
                instructions_text = file.readlines()
            
            instructions_font_size = 20 if settings.is_fullscreen else 14
            instructions_font = pygame.font.Font("data/fonts/BLOODY.ttf", instructions_font_size)
        except FileNotFoundError:
            print("Error: Instructions file not found.")
            return
        except Exception as e:
            print("Error:", e)
            return

        y_offset = 540
        for line in instructions_text:
            instructions_surface = instructions_font.render(line.strip(), True, (190, 190, 190))
            self.screen.blit(instructions_surface, (50, y_offset))
            y_offset += instructions_surface.get_height() + 5

mixer.init()

while True:
    if settings.is_menu:
        mixer.music.load("data/audio/home.mp3")
        mixer.music.set_volume(settings.volume)
        mixer.music.play(-1)
        Menu(screen)
    elif settings.is_character_selection or settings.is_background_selection:
        SelectionScreen(screen, mode='character' if settings.is_character_selection else 'background')
    elif settings.start_game:
        settings.start_game = False 
        Game(screen)
