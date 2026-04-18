import pygame
import math
import random

# TODO: optional polish — add subtle jump dust VFX (procedural); smoother wall sliding;
#       expand world_map with more vanilla courses.  files = off (no external assets).

# === CONFIG ===
WIDTH, HEIGHT = 800, 600
RAY_COUNT = 200
MAP_SIZE = 20
FOV = math.pi / 3
MAX_WALL_DIST = 20.0
INNER_WALLS = 40  # Fixed obstacle count (no corruption-based density)

# SM64-ish physics constants
MOVE_ACCEL = 8.0
MOVE_FRICTION = 0.85
MAX_SPEED = 4.0
GRAVITY = 700.0          # Positive = downward
JUMP_FORCE = 280.0
MOUSE_SENS = 0.0025
PITCH_CLAMP = math.radians(70)  # ~70 degrees up/down

# === HELPERS ===
def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    if not hex_code:
        return (0, 0, 0)
    if len(hex_code) == 3:
        hex_code = "".join([c*2 for c in hex_code])
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def draw_shadow_text(surface, text, font, color, x, y, align="center"):
    """Draw text with black offset shadow, SM64 HUD style"""
    shadow = font.render(text, True, (0, 0, 0))
    txt = font.render(text, True, color)
    if align == "center":
        sx, sy = x - shadow.get_width()//2 + 2, y + 2
        tx, ty = x - txt.get_width()//2, y
    else:  # left
        sx, sy = x + 2, y + 2
        tx, ty = x, y
    surface.blit(shadow, (sx, sy))
    surface.blit(txt, (tx, ty))

def draw_n64_star(surface, x, y, size):
    """Draw a simple 5-point star with outline"""
    points = []
    for i in range(10):
        angle = i * math.pi/5 - math.pi/2
        r = size if i % 2 == 0 else size/2.5
        points.append((x + math.cos(angle)*r, y + math.sin(angle)*r))
    pygame.draw.polygon(surface, (255, 215, 0), points)
    pygame.draw.polygon(surface, (0, 0, 0), points, 2)

def draw_coin(surface, x, y, size):
    """Draw a simple coin sprite"""
    pygame.draw.circle(surface, (255, 215, 0), (int(x), int(y)), size)
    pygame.draw.circle(surface, (200, 150, 0), (int(x), int(y)), size//3, 2)
    pygame.draw.rect(surface, (255, 255, 150), 
                    (x-size//4, y-size//2, size//2, size))

def draw_power_meter(surface, font, x, y, health):
    """SM64-style segmented power meter"""
    # Background circle
    pygame.draw.circle(surface, (0, 0, 0), (x, y), 42)
    
    # Color by health state
    if health >= 7: color = (0, 80, 255)
    elif health >= 5: color = (0, 220, 0)
    elif health >= 3: color = (255, 220, 0)
    else: color = (255, 50, 50)
    
    # Draw filled arc segments (8 wedges)
    for i in range(8):
        if i < health:
            start_angle = -math.pi/2 + i * math.pi/4
            end_angle = start_angle + math.pi/4
            points = [(x, y)]
            for a in [start_angle, end_angle]:
                points.append((x + 36*math.cos(a), y + 36*math.sin(a)))
            pygame.draw.polygon(surface, color, points)
    
    # Inner circle + label
    pygame.draw.circle(surface, (0, 0, 0), (x, y), 22)
    draw_shadow_text(surface, "POWER", font, (255, 255, 255), x, y-55, "center")

# === ENGINE (vanilla SM64-style labels, no corruption / liminal graph) ===
class SM64WorldEngine:
    def __init__(self):
        self.location = "Castle Grounds"
        self.coins = 0
        self.stars = 0
        self.health = 8
        self.game_over = False
        self.collectibles = {}

        self.world_map = {
            "Castle Grounds": [
                "Castle Lobby",
                "Bob-omb Battlefield",
                "Cool, Cool Mountain",
                "Jolly Roger Bay",
            ],
            "Castle Lobby": [
                "Castle Grounds",
                "Whomp's Fortress",
                "Lethal Lava Land",
                "Bowser in the Dark World",
            ],
            "Bob-omb Battlefield": ["Castle Grounds", "Bowser in the Dark World"],
            "Cool, Cool Mountain": ["Castle Grounds", "Snowman's Land"],
            "Jolly Roger Bay": ["Castle Grounds", "Dire Dire Docks"],
            "Whomp's Fortress": ["Castle Lobby", "Tick Tock Clock"],
            "Lethal Lava Land": ["Castle Lobby", "Bowser in the Fire Sea"],
            "Bowser in the Dark World": ["Bob-omb Battlefield", "Castle Lobby"],
            "Snowman's Land": ["Cool, Cool Mountain", "Castle Grounds"],
            "Dire Dire Docks": ["Jolly Roger Bay", "Castle Grounds"],
            "Tick Tock Clock": ["Whomp's Fortress", "Castle Grounds"],
            "Bowser in the Fire Sea": ["Lethal Lava Land", "Castle Grounds"],
        }

        self.map_configs = {
            "Castle Grounds": {"sky": "87CEEB", "ground": "228B22"},
            "Castle Lobby": {"sky": "2F2F2F", "ground": "808080"},
            "Bob-omb Battlefield": {"sky": "87CEEB", "ground": "6B8E23"},
            "Cool, Cool Mountain": {"sky": "E0FFFF", "ground": "F0F8FF"},
            "Jolly Roger Bay": {"sky": "20B2AA", "ground": "D2B48C"},
            "Whomp's Fortress": {"sky": "87CEEB", "ground": "A0522D"},
            "Lethal Lava Land": {"sky": "8B0000", "ground": "FF4500"},
            "Bowser in the Dark World": {"sky": "1A0A1A", "ground": "4B0082"},
            "Snowman's Land": {"sky": "B0E0E6", "ground": "FFFFFF"},
            "Dire Dire Docks": {"sky": "00008B", "ground": "4682B4"},
            "Tick Tock Clock": {"sky": "2F4F4F", "ground": "DAA520"},
            "Bowser in the Fire Sea": {"sky": "4A0000", "ground": "FF8C00"},
        }

    def travel(self):
        dests = self.world_map.get(self.location, ["Castle Grounds"])
        self.location = random.choice(dests)
        self._spawn_collectibles()
        return self.location

    def _spawn_collectibles(self):
        """Spawn coins/stars in open map tiles"""
        self.collectibles.clear()
        for _ in range(random.randint(3, 7)):
            x, y = random.randint(3, MAP_SIZE - 4), random.randint(3, MAP_SIZE - 4)
            if (x, y) not in [(2, 2), (2, 3), (3, 2), (3, 3)]:
                self.collectibles[(x, y)] = "coin" if random.random() > 0.2 else "star"

    def generate_map_grid(self, size=MAP_SIZE):
        grid = [[0] * size for _ in range(size)]
        for i in range(size):
            grid[0][i] = grid[size - 1][i] = grid[i][0] = grid[i][size - 1] = 1
        for _ in range(INNER_WALLS):
            x, y = random.randint(2, size - 3), random.randint(2, size - 3)
            if x > 3 or y > 3:
                grid[x][y] = 1
        self._spawn_collectibles()
        return grid

# === PYGAME SETUP ===
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Super Mario 64 (style) — Raycaster • files off")
clock = pygame.time.Clock()

# Fonts (SysFont when available; Font(None) fallback — no bundled font files)
try:
    font_ui = pygame.font.SysFont("Courier", 18, bold=True)
except Exception:
    font_ui = pygame.font.Font(None, 18)
try:
    font_hud = pygame.font.SysFont("Impact", 26, bold=True)
except Exception:
    font_hud = pygame.font.Font(None, 26)
try:
    font_warn = pygame.font.SysFont("Courier", 32, bold=True)
except Exception:
    font_warn = pygame.font.Font(None, 32)
try:
    font_title = pygame.font.SysFont("Courier", 64, bold=True)
except Exception:
    font_title = pygame.font.Font(None, 64)
try:
    font_menu = pygame.font.SysFont("Courier", 24, bold=True)
except Exception:
    font_menu = pygame.font.Font(None, 24)

# Engine + Map
engine = SM64WorldEngine()
grid = engine.generate_map_grid()
DEFAULT_AREA = "Castle Grounds"

# Player State (SM64-style)
px, py = 2.5, 2.5
pz, pvz = 0.0, 0.0
angle = math.pi/4
pitch = 0.0
vx, vy = 0.0, 0.0  # Velocity for acceleration
mouse_look = True

# Game State
state = "MAIN"  # Fixed missing key
menu_idx = 0
menus = {
    "MAIN": ["Play Game", "Options", "How to Play", "Credits", "Exit"],
    "OPTIONS": ["Fullscreen: OFF", "Mouse Look: ON", "← Back"],
    "HOW": ["WASD: Move", "Mouse/←→: Look", "SPACE: Jump (hold for height)", "T: Warp", "ESC: Menu"],
    "CREDITS": [
        "Inspired by Super Mario 64 (Nintendo)",
        "Pygame fan raycaster — procedural art only",
        "No external asset files",
    ],
}
fullscreen = False
fps_target = 60

# Starfield bg
stars = [(random.randint(0,WIDTH), random.randint(0,HEIGHT), random.uniform(0.3,2.0)) for _ in range(120)]

# === MAIN LOOP ===
running = True
pygame.mouse.set_visible(True)

while running:
    dt = clock.tick(fps_target) / 1000.0

    # ── EVENTS ──
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        if event.type == pygame.KEYDOWN:
            # ESC always returns to menu
            if event.key == pygame.K_ESCAPE:
                state = "MAIN"
                menu_idx = 0
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)
                continue
                
            if state in ["MAIN", "OPTIONS"]:
                if event.key == pygame.K_UP:
                    menu_idx = (menu_idx - 1) % len(menus[state])
                elif event.key == pygame.K_DOWN:
                    menu_idx = (menu_idx + 1) % len(menus[state])
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    opt = menus[state][menu_idx]
                    
                    if state == "MAIN":
                        if opt == "Play Game":
                            state = "PLAY"
                            if mouse_look:
                                pygame.mouse.set_visible(False)
                                pygame.event.set_grab(True)
                        elif opt == "Options": state = "OPTIONS"; menu_idx = 0
                        elif opt == "How to Play": state = "HOW"
                        elif opt == "Credits": state = "CREDITS"
                        elif opt == "Exit": running = False
                    elif state == "OPTIONS":
                        if "Fullscreen" in opt:
                            fullscreen = not fullscreen
                            mode = pygame.FULLSCREEN if fullscreen else 0
                            screen = pygame.display.set_mode((WIDTH, HEIGHT), mode)
                            menus["OPTIONS"][0] = f"Fullscreen: {'ON' if fullscreen else 'OFF'}"
                        elif "Mouse Look" in opt:
                            mouse_look = not mouse_look
                            menus["OPTIONS"][1] = f"Mouse Look: {'ON' if mouse_look else 'OFF'}"
                        elif "Back" in opt:
                            state = "MAIN"; menu_idx = 1
            
            elif state == "PLAY":
                if event.key == pygame.K_t:
                    engine.travel()
                    grid = engine.generate_map_grid()
                    px, py, pz, pvz = 2.5, 2.5, 0.0, 0.0
                    vx = vy = 0.0
                if event.key == pygame.K_SPACE and pz == 0:
                    pvz = JUMP_FORCE # Initial jump impulse applied
    
    # ── MENU RENDER ──
    if state != "PLAY":
        screen.fill((0,0,0))
        # Animate stars
        for i, (sx, sy, sp) in enumerate(stars):
            sy -= sp
            if sy < 0: sy, sx = HEIGHT, random.randint(0, WIDTH)
            stars[i] = (sx, sy, sp)
            pygame.draw.circle(screen, (180,180,200), (int(sx), int(sy)), 1)
        
        draw_n64_star(screen, WIDTH // 2, HEIGHT // 4, 45)
        draw_shadow_text(
            screen,
            "Super Mario 64",
            font_title,
            (50, 105, 255),
            WIDTH // 2,
            HEIGHT // 4 + 50,
        )
        draw_shadow_text(
            screen,
            "(style) raycaster",
            font_menu,
            (220, 220, 220),
            WIDTH // 2,
            HEIGHT // 4 + 115,
        )
        
        # Menu items
        base_y = HEIGHT//2
        is_interactive = state in ["MAIN", "OPTIONS"]
        
        for i, item in enumerate(menus[state]):
            col = (255,255,50) if i==menu_idx and is_interactive else (180,180,180)
            prefix = "> " if i==menu_idx and is_interactive else "  "
            draw_shadow_text(screen, f"{prefix}{item}", font_menu, col, WIDTH//2, base_y + i*40)
        
        pygame.display.flip()
        continue
    
    # ── GAMEPLAY ──
    if engine.game_over:
        screen.fill((0,0,0))
        draw_shadow_text(screen, "GAME OVER", font_title, (255,50,50), WIDTH//2, HEIGHT//2-40)
        draw_shadow_text(screen, f"Stars: {engine.stars} | Coins: {engine.coins}", font_ui, (200,200,200), WIDTH//2, HEIGHT//2+20)
        draw_shadow_text(screen, "Press ESC to return", font_menu, (150,150,150), WIDTH//2, HEIGHT//2+70)
        pygame.display.flip()
        continue
    
    # Mouse look
    if mouse_look and pygame.mouse.get_focused():
        dx, dy = pygame.mouse.get_rel()
        angle += dx * MOUSE_SENS
        pitch += dy * MOUSE_SENS
        pitch = max(-PITCH_CLAMP, min(PITCH_CLAMP, pitch))
    
    # Keyboard fallback look
    keys = pygame.key.get_pressed()
    if not mouse_look:
        if keys[pygame.K_LEFT]: angle -= 2.5*dt
        if keys[pygame.K_RIGHT]: angle += 2.5*dt
        if keys[pygame.K_UP]: pitch = min(PITCH_CLAMP, pitch + 3*dt)
        if keys[pygame.K_DOWN]: pitch = max(-PITCH_CLAMP, pitch - 3*dt)
    
    # Movement with acceleration (SM64 style)
    target_vx = target_vy = 0
    if keys[pygame.K_w]:
        target_vx += math.cos(angle) * MAX_SPEED
        target_vy += math.sin(angle) * MAX_SPEED
    if keys[pygame.K_s]:
        target_vx -= math.cos(angle) * MAX_SPEED
        target_vy -= math.sin(angle) * MAX_SPEED
    if keys[pygame.K_a]:
        target_vx += math.cos(angle - math.pi/2) * MAX_SPEED
        target_vy += math.sin(angle - math.pi/2) * MAX_SPEED
    if keys[pygame.K_d]:
        target_vx += math.cos(angle + math.pi/2) * MAX_SPEED
        target_vy += math.sin(angle + math.pi/2) * MAX_SPEED
    
    # Apply acceleration/friction
    vx += (target_vx - vx) * MOVE_ACCEL * dt
    vy += (target_vy - vy) * MOVE_ACCEL * dt
    vx *= MOVE_FRICTION
    vy *= MOVE_FRICTION
    
    # Accurate Variable Height Jump Physics
    if pz > 0 or pvz != 0:
        # Halve gravity while ascending AND holding jump to extend air time (Mario 64 style)
        grav = GRAVITY * 0.4 if keys[pygame.K_SPACE] and pvz > 0 else GRAVITY
        pvz -= grav * dt
        pz += pvz * dt
        if pz <= 0:
            pz = pvz = 0
    
    # Collision + movement
    nx, ny = px + vx*dt, py + vy*dt
    # Check collision at new position (simple grid check)
    for dx_check in [-1,0,1]:
        for dy_check in [-1,0,1]:
            tx, ty = int(nx+dx_check*0.3), int(ny+dy_check*0.3)
            if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and grid[tx][ty] == 1:
                # Slide along wall
                if abs(vx) > abs(vy): vy *= 0.1
                else: vx *= 0.1
                nx, ny = px, py
                break
    px, py = nx, ny
    
    # Collect items
    tile_x, tile_y = int(px+0.5), int(py+0.5)
    if (tile_x, tile_y) in engine.collectibles:
        item = engine.collectibles.pop((tile_x, tile_y))
        if item == "coin":
            engine.coins += 1
            if engine.coins >= 100:
                engine.coins -= 100
                engine.stars += 1
        else:
            engine.stars += 1
    
    # Background (sky / ground — stable, no shake or chromatic corruption)
    cfg = engine.map_configs.get(engine.location, engine.map_configs[DEFAULT_AREA])
    sky = hex_to_rgb(cfg["sky"])
    ground = hex_to_rgb(cfg["ground"])
    horizon = HEIGHT // 2 + int(pitch * HEIGHT / 2)
    pygame.draw.rect(screen, sky, (0, 0, WIDTH, max(0, horizon)))
    pygame.draw.rect(screen, ground, (0, max(0, horizon), WIDTH, HEIGHT - max(0, horizon)))
    if engine.health <= 2:
        pygame.draw.rect(screen, (120, 0, 0), (0, 0, WIDTH, HEIGHT), 5)
    
    # Raycasting
    for i in range(RAY_COUNT):
        ray_angle = angle - FOV/2 + i * (FOV/RAY_COUNT)
        dx, dy = math.cos(ray_angle), math.sin(ray_angle)
        dist = 0.01
        hit = False
        
        while not hit and dist < MAX_WALL_DIST:
            tx, ty = int(px + dx*dist), int(py + dy*dist)
            if not (0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE) or grid[tx][ty] == 1:
                hit = True
            else:
                dist += 0.05
        
        # Fisheye correction + pitch projection
        corr = dist * math.cos(ray_angle - angle)
        if corr < 0.01: corr = 0.01
        z_offset = (pz * HEIGHT) / corr
        wall_h = HEIGHT / corr
        top = horizon - wall_h + z_offset
        bottom = horizon + wall_h + z_offset

        shade = max(20, 255 - int(dist * 12))
        color = (shade, shade, shade)

        x_pos = int(i * (WIDTH // RAY_COUNT))
        pygame.draw.rect(
            screen,
            color,
            (x_pos, int(top), WIDTH // RAY_COUNT + 1, int(bottom - top)),
        )
    
    # HUD
    draw_power_meter(screen, font_hud, WIDTH//2, 65, engine.health)
    draw_n64_star(screen, WIDTH-100, 35, 18)
    draw_shadow_text(screen, f"x{engine.stars:02d}", font_hud, (255,255,255), WIDTH-65, 25, "left")
    draw_coin(screen, WIDTH-100, 75, 14)
    draw_shadow_text(screen, f"x{engine.coins:03d}", font_hud, (255,255,255), WIDTH-65, 65, "left")
    draw_shadow_text(screen, engine.location, font_ui, (180,180,255), 20, HEIGHT-50, "left")
    
    # Warnings
    if engine.health <= 2:
        draw_shadow_text(
            screen,
            "LOW POWER",
            font_warn,
            (255, 200, 50),
            WIDTH // 2,
            HEIGHT - 130,
        )
    
    pygame.display.flip()

pygame.quit()