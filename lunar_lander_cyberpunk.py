"""Cyberpunk-inspired Lunar Lander game implemented with pygame.

This module contains a complete, single-file game that fuses classic
Lunar Lander mechanics with neon-drenched visuals reminiscent of
Cyberpunk 2077. The code is structured for clarity and customization,
with clearly marked sections for tweaking visuals, audio, and gameplay.
"""

from __future__ import annotations

import math
import random
import sys
from array import array
from dataclasses import dataclass
from typing import List, Tuple

try:
    import pygame
except ImportError as exc:
    raise SystemExit(
        "pygame is required to run this game. Install it with 'pip install pygame'."
    ) from exc


# ---------------------------------------------------------------------------
# Customization Section: Color Palette & Visual Identity
# ---------------------------------------------------------------------------
# To experiment with new color themes, adjust the palette below. Colors are
# defined as RGB tuples and pulled throughout the UI, lander, and effects.
NEON_PALETTE = {
    "background_dark": (6, 6, 20),
    "background_mid": (16, 16, 40),
    "background_high": (0, 180, 216),
    "lander_primary": (255, 0, 110),
    "lander_secondary": (0, 255, 200),
    "thruster_core": (255, 255, 0),
    "thruster_glow": (0, 255, 255),
    "hud_primary": (255, 0, 110),
    "hud_secondary": (0, 255, 200),
    "warning": (255, 94, 0),
    "success": (144, 238, 144),
}


# ---------------------------------------------------------------------------
# Customization Section: Gameplay Tuning
# ---------------------------------------------------------------------------
@dataclass
class GameConfig:
    screen_size: Tuple[int, int] = (960, 720)
    target_fps: int = 60
    gravity: float = 36.0  # pixels per second^2
    thrust_force: float = 120.0  # engine thrust in pixels per second^2
    fuel_capacity: float = 100.0
    fuel_burn_rate: float = 22.0  # units per second while thruster active
    rotation_speed: float = 90.0  # degrees per second
    landing_pad_width: int = 160
    landing_pad_height: int = 12
    max_landing_speed: float = 42.0  # vertical speed threshold
    max_horizontal_speed: float = 32.0
    max_landing_angle: float = 12.0  # degrees
    star_count: int = 120
    scanline_spacing: int = 4


@dataclass
class Particle:
    position: pygame.Vector2
    velocity: pygame.Vector2
    lifetime: float
    color: Tuple[int, int, int]
    size: float

    def update(self, dt: float) -> bool:
        self.position += self.velocity * dt
        self.lifetime -= dt
        self.size = max(0.0, self.size - dt * 6)
        return self.lifetime > 0

    def draw(self, surface: pygame.Surface) -> None:
        if self.lifetime <= 0:
            return
        alpha = max(0, min(255, int(255 * self.lifetime)))
        color = (*self.color, alpha)
        glow_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, color, (4, 4), max(1, int(self.size)))
        surface.blit(glow_surface, self.position - pygame.Vector2(4, 4))


class LandingPad:
    def __init__(self, config: GameConfig):
        width, height = config.screen_size
        pad_width = config.landing_pad_width
        x = random.randint(pad_width // 2 + 40, width - pad_width // 2 - 40)
        y = height - config.landing_pad_height * 6
        self.rect = pygame.Rect(0, 0, pad_width, config.landing_pad_height)
        self.rect.center = (x, y)
        self.timer = 0.0

    def update(self, dt: float) -> None:
        self.timer += dt

    def draw(self, surface: pygame.Surface) -> None:
        neon_color = NEON_PALETTE["hud_secondary"]
        animated_alpha = int(120 + 60 * math.sin(self.timer * 6.0))
        pygame.draw.rect(surface, neon_color, self.rect)
        edge_width = 12
        glow_surface = pygame.Surface((self.rect.width + edge_width * 2, self.rect.height + 16), pygame.SRCALPHA)
        glow_surface.fill((0, 0, 0, 0))
        pygame.draw.rect(
            glow_surface,
            (*NEON_PALETTE["hud_secondary"], animated_alpha),
            glow_surface.get_rect(),
            border_radius=8,
        )
        surface.blit(glow_surface, (self.rect.x - edge_width, self.rect.y - 8), special_flags=pygame.BLEND_ADD)


class Lander:
    def __init__(self, config: GameConfig, start_pos: Tuple[float, float]):
        self.config = config
        self.position = pygame.Vector2(start_pos)
        self.velocity = pygame.Vector2(0, 0)
        self.angle = 0.0
        self.fuel = config.fuel_capacity
        self.thrusting = False
        self.particles: List[Particle] = []
        self.status = "flying"  # values: flying, landed, crashed
        self.status_timer = 0.0

    def reset(self, config: GameConfig, start_pos: Tuple[float, float]) -> None:
        self.__init__(config, start_pos)

    def handle_input(self, keys: pygame.key.ScancodeWrapper, dt: float) -> None:
        self.thrusting = False
        if self.status != "flying":
            return
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.angle += self.config.rotation_speed * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.angle -= self.config.rotation_speed * dt
        if (keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]) and self.fuel > 0:
            self.thrusting = True

    def update(self, dt: float) -> None:
        if self.status != "flying":
            self.status_timer += dt
            return

        gravity = pygame.Vector2(0, self.config.gravity)
        acceleration = gravity.copy()

        if self.thrusting and self.fuel > 0:
            thrust_vector = pygame.Vector2(0, -self.config.thrust_force).rotate(-self.angle)
            acceleration += thrust_vector
            self.fuel = max(0.0, self.fuel - self.config.fuel_burn_rate * dt)
            self.emit_thruster_particles(thrust_vector)
        else:
            self.thrusting = False

        self.velocity += acceleration * dt
        self.position += self.velocity * dt

        # Keep lander horizontally on screen to avoid disappearing off-screen.
        width, height = self.config.screen_size
        self.position.x = max(40, min(width - 40, self.position.x))

        # Treat leaving the bottom as a crash state.
        if self.position.y > height + 80:
            self.status = "crashed"

        self.update_particles(dt)

    def emit_thruster_particles(self, thrust_vector: pygame.Vector2) -> None:
        base_position = self.position + pygame.Vector2(0, 20).rotate(-self.angle)
        for _ in range(3):
            direction = thrust_vector.normalize() if thrust_vector.length() else pygame.Vector2(0, 1)
            velocity = direction.rotate(random.uniform(-20, 20)) * random.uniform(60, 120) * -0.65
            velocity += pygame.Vector2(random.uniform(-10, 10), random.uniform(-10, 10))
            particle = Particle(
                position=base_position.copy(),
                velocity=velocity,
                lifetime=random.uniform(0.3, 0.6),
                color=NEON_PALETTE["thruster_glow"],
                size=random.uniform(2, 4),
            )
            self.particles.append(particle)

    def update_particles(self, dt: float) -> None:
        self.particles = [p for p in self.particles if p.update(dt)]

    def check_landing(self, pad: LandingPad) -> None:
        if self.status != "flying":
            return
        lander_rect = pygame.Rect(0, 0, 42, 42)
        lander_rect.center = self.position
        if lander_rect.bottom >= pad.rect.top and lander_rect.colliderect(pad.rect.inflate(40, 12)):
            vertical_speed = abs(self.velocity.y)
            horizontal_speed = abs(self.velocity.x)
            angle_delta = abs((self.angle + 180) % 360 - 180)  # normalize to [-180, 180]
            if (
                vertical_speed <= self.config.max_landing_speed
                and horizontal_speed <= self.config.max_horizontal_speed
                and angle_delta <= self.config.max_landing_angle
            ):
                self.status = "landed"
            else:
                self.status = "crashed"
            self.status_timer = 0.0

    def draw(self, surface: pygame.Surface) -> None:
        ship_surface = pygame.Surface((48, 64), pygame.SRCALPHA)
        body_color = NEON_PALETTE["lander_primary"]
        accent_color = NEON_PALETTE["lander_secondary"]
        pygame.draw.polygon(
            ship_surface,
            body_color,
            [(24, 4), (40, 44), (32, 54), (16, 54), (8, 44)],
        )
        pygame.draw.polygon(
            ship_surface,
            accent_color,
            [(24, 12), (34, 42), (24, 48), (14, 42)],
            width=2,
        )
        pygame.draw.line(ship_surface, accent_color, (12, 44), (6, 60), width=2)
        pygame.draw.line(ship_surface, accent_color, (36, 44), (42, 60), width=2)

        if self.thrusting and self.fuel > 0:
            core_color = NEON_PALETTE["thruster_core"]
            pygame.draw.polygon(
                ship_surface,
                core_color,
                [(24, 56), (30, 60), (24, 62), (18, 60)],
            )

        rotated = pygame.transform.rotozoom(ship_surface, self.angle, 1.0)
        rect = rotated.get_rect(center=self.position)

        glow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
        glow_color = (*NEON_PALETTE["lander_secondary"], 50)
        pygame.draw.ellipse(glow, glow_color, glow.get_rect())
        surface.blit(glow, glow.get_rect(center=self.position), special_flags=pygame.BLEND_ADD)
        surface.blit(rotated, rect)

        for particle in self.particles:
            particle.draw(surface)


def build_starfield(config: GameConfig) -> List[Tuple[pygame.Vector2, float]]:
    width, height = config.screen_size
    stars: List[Tuple[pygame.Vector2, float]] = []
    for _ in range(config.star_count):
        position = pygame.Vector2(random.uniform(0, width), random.uniform(0, height))
        speed = random.uniform(5.0, 20.0)
        stars.append((position, speed))
    return stars


def draw_starfield(surface: pygame.Surface, stars: List[Tuple[pygame.Vector2, float]], dt: float) -> None:
    width, height = surface.get_size()
    for position, speed in stars:
        position.y += speed * dt
        if position.y > height:
            position.y = 0
            position.x = random.uniform(0, width)
        color_value = min(255, int(120 + speed * 2))
        surface.fill((color_value, 0, color_value), (int(position.x), int(position.y), 2, 2))


def draw_background(surface: pygame.Surface, time_accumulator: float, config: GameConfig) -> None:
    width, height = surface.get_size()
    top_color = pygame.Color(*NEON_PALETTE["background_dark"])
    bottom_color = pygame.Color(*NEON_PALETTE["background_high"])
    for y in range(height):
        blend = y / height
        color = (
            int(top_color.r + (bottom_color.r - top_color.r) * blend),
            int(top_color.g + (bottom_color.g - top_color.g) * blend),
            int(top_color.b + (bottom_color.b - top_color.b) * blend),
        )
        surface.fill(color, (0, y, width, 1))

    skyline_rng = random.Random(42)
    skyline_height = height // 3
    for i in range(40):
        building_width = skyline_rng.randint(24, 64)
        building_height = skyline_rng.randint(40, skyline_height)
        x = int((i / 40.0) * width) + skyline_rng.randint(-12, 12)
        y = height - building_height
        color_shift = int((math.sin(time_accumulator * 0.6 + i) + 1) * 40)
        color = (
            min(255, NEON_PALETTE["background_mid"][0] + color_shift),
            NEON_PALETTE["background_mid"][1],
            min(255, NEON_PALETTE["background_mid"][2] + color_shift),
        )
        pygame.draw.rect(surface, color, (x, y, building_width, building_height))

    draw_scanlines(surface, config.scanline_spacing)


def draw_scanlines(surface: pygame.Surface, spacing: int) -> None:
    width, height = surface.get_size()
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 0))
    for y in range(0, height, spacing):
        pygame.draw.line(overlay, (255, 0, 255, 16), (0, y), (width, y))
    surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_ADD)


def draw_hud(surface: pygame.Surface, lander: Lander, elapsed: float, config: GameConfig) -> None:
    font = pygame.font.Font(None, 28)
    large_font = pygame.font.Font(None, 72)

    fuel_percentage = lander.fuel / config.fuel_capacity
    hud_color = NEON_PALETTE["hud_primary"]
    accent_color = NEON_PALETTE["hud_secondary"]

    hud_surface = pygame.Surface((240, 120), pygame.SRCALPHA)
    pygame.draw.rect(hud_surface, (*hud_color, 50), hud_surface.get_rect(), border_radius=12)
    pygame.draw.rect(hud_surface, accent_color, hud_surface.get_rect(), width=2, border_radius=12)
    fuel_text = font.render(f"FUEL {lander.fuel:05.1f}", True, accent_color)
    velocity_text = font.render(
        f"VEL X {lander.velocity.x:5.1f} | Y {lander.velocity.y:5.1f}", True, accent_color
    )
    angle_text = font.render(f"ANGLE {lander.angle:5.1f}", True, accent_color)
    hud_surface.blit(fuel_text, (16, 16))
    hud_surface.blit(velocity_text, (16, 48))
    hud_surface.blit(angle_text, (16, 80))
    surface.blit(hud_surface, (20, 20))

    bar_width = 600
    bar_height = 14
    bar_x = 180
    bar_y = 32
    pygame.draw.rect(surface, (*hud_color, 70), (bar_x, bar_y, bar_width, bar_height), border_radius=8)
    pygame.draw.rect(
        surface,
        accent_color,
        (bar_x, bar_y, int(bar_width * fuel_percentage), bar_height),
        border_radius=8,
    )

    if lander.status == "landed":
        message = "Touchdown Achieved"
        color = NEON_PALETTE["success"]
    elif lander.status == "crashed":
        message = "Impact Detected"
        color = NEON_PALETTE["warning"]
    else:
        message = "Neon Descent"
        color = accent_color

    if lander.status != "flying" or int(elapsed) % 2 == 0:
        text_surface = large_font.render(message, True, color)
        glitch_offset = math.sin(elapsed * 12.0) * 6
        surface.blit(text_surface, text_surface.get_rect(center=(surface.get_width() / 2 + glitch_offset, 80)))
        surface.blit(
            text_surface,
            text_surface.get_rect(center=(surface.get_width() / 2 - glitch_offset, 80)),
            special_flags=pygame.BLEND_ADD,
        )


def create_thruster_sound() -> pygame.mixer.Sound:
    frequency = 44100
    duration = 0.25
    amplitude = 32767
    sample_count = int(frequency * duration)
    waveform = array("h")
    for i in range(sample_count):
        t = i / frequency
        value = int(amplitude * 0.3 * math.sin(2 * math.pi * 220 * t))
        waveform.append(value)
    return pygame.mixer.Sound(buffer=waveform.tobytes())


def run_game() -> None:
    config = GameConfig()
    pygame.init()
    pygame.display.set_caption("Neon Lander")
    screen = pygame.display.set_mode(config.screen_size)
    clock = pygame.time.Clock()

    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1)
        thruster_sound = create_thruster_sound()
        thruster_sound.set_volume(0.45)
    except pygame.error:
        thruster_sound = None

    lander = Lander(config, (config.screen_size[0] / 2, 140))
    landing_pad = LandingPad(config)
    starfield = build_starfield(config)

    elapsed = 0.0
    time_accumulator = 0.0
    thruster_channel = None

    while True:
        dt_ms = clock.tick(config.target_fps)
        dt = dt_ms / 1000.0
        elapsed += dt
        time_accumulator += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                lander.reset(config, (config.screen_size[0] / 2, 140))
                landing_pad = LandingPad(config)

        keys = pygame.key.get_pressed()
        lander.handle_input(keys, dt)
        lander.update(dt)
        lander.check_landing(landing_pad)
        landing_pad.update(dt)

        if thruster_sound:
            if lander.thrusting and lander.status == "flying" and lander.fuel > 0:
                if thruster_channel is None or not thruster_channel.get_busy():
                    thruster_channel = thruster_sound.play(loops=-1)
            else:
                if thruster_channel and thruster_channel.get_busy():
                    thruster_channel.fadeout(120)
                    thruster_channel = None

        draw_background(screen, time_accumulator, config)
        draw_starfield(screen, starfield, dt)
        landing_pad.draw(screen)
        lander.draw(screen)
        draw_hud(screen, lander, elapsed, config)

        pygame.display.flip()


if __name__ == "__main__":
    run_game()
