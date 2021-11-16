import pygame
import random
import time

pygame.init()


class Button():
    def __init__(self, x, y, image,):
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)
        self.clicked = False

    def draw(self, surface):
        action = False
        # get mouse position
        pos = pygame.mouse.get_pos()

        # check mouseover and clicked conditions
        if self.rect.collidepoint(pos):
            if pygame.mouse.get_pressed()[0] == 1 and self.clicked == False:
                self.clicked = True
                action = True

        if pygame.mouse.get_pressed()[0] == 0:
            self.clicked = False

        # draw button on screen
        surface.blit(self.image, (self.rect.x, self.rect.y))

        return action


def home_screen():
    pygame.mixer.music.load("C:\\Users\\Dell\\Downloads\\Shape of You(PagalWorld.com.se).mp3")
    pygame.mixer.music.play()
    home_screen = pygame.display.set_mode([900, 600])
    light_blue = 173, 216, 230
    grey = 128, 126, 120
    pygame.display.set_caption("PONG GAME")
    textscreen("or press enter to continue", black, 355, 210)
    start_img = pygame.image.load("C:\\Users\\Dell\\Pictures\\MAIN PONG START BUTTON.png").convert_alpha()
    exit_img = pygame.image.load("C:\\Users\\Dell\\Pictures\\QUIT REAL WORKS.png").convert_alpha()
    exit_button = Button(500,250,exit_img)
    start_button = Button(150, 250, start_img)

    run = True

    while run:
        home_screen.fill(light_blue)
        textscreen("welcome to pong game",black,280,50)
        if start_button.draw(home_screen):
            game_loop()
        if exit_button.draw(home_screen):
            pygame.quit()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False


        pygame.display.update()


def textscreen(text, color, x, y):
    screen_text = font.render(text, True, color)
    game_window.blit(screen_text, [x, y])


def player_animation():
    player.y += player_speed

    if player.top <= 0:
        player.top = 5
    if player.bottom >= screen_height:
        player.bottom = screen_height

def ball_animation():
    global opponent_score, player_score, ball_speed_x, ballspeed_y,score_time
    ball.y += ballspeed_y
    ball.x += ball_speed_x

    if ball.top <= 0 or ball.bottom >= screen_height:
        ballspeed_y *= -1
    if ball.left <= 0 or ball.right >= screen_width:
        score_time = pygame.time.get_ticks()
        ball_speed_x *= -1
    if ball.colliderect(player) or ball.colliderect(opponent1):
        ball_speed_x *= -1
    if ball.x <= 0:
        ball_start()
        opponent_score += 10

    if ball.right >= screen_width:
        ball_start()
        player_score += 10


def opponent_ai():
    if opponent1.top < ball.y:
        opponent1.y += opponent_speed
    if opponent1.bottom > ball.y:
        opponent1.y -= opponent_speed

    if opponent1.top <= 0:
        opponent1.top = 0
    if opponent1.bottom >= screen_height:
        opponent1.bottom = screen_height


def ball_start():
    global ball_speed_x, ball_speed_y, ball_moving, score_time

    ball.center = (screen_width / 2, screen_height / 2)
    current_time = pygame.time.get_ticks()

    if current_time - score_time < 700:
        number_three = font.render("3", False, red)
        game_window.blit(number_three, (screen_width / 2 - 10, screen_height / 2 + 20))
    if 700 < current_time - score_time < 1400:
        number_two = font.render("2", False, red)
        game_window.blit(number_two, (screen_width / 2 - 10, screen_height / 2 + 20))
    if 1400 < current_time - score_time < 2100:
        number_one = font.render("1", False,red)
        game_window.blit(number_one, (screen_width / 2 - 10, screen_height / 2 + 20))

    if current_time - score_time < 2100:
        ball_speed_y, ball_speed_x = 0, 0
    else:
        ball_speed_x = 7 * random.choice((1, -1))
        ball_speed_y = 7 * random.choice((1, -1))
        score_time = None

def game_over():
    game_over = pygame.display.set_mode([900,600])
    pygame.display.set_caption("better luck next time")
    game_over.fill(black)
    textscreen("GAME OVER!",white,350,200)
    textscreen("BETTER LUCK NEXT TIME!",white,270,230)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
        pygame.display.update()

grey = (200, 200, 200)
screen_width = 900
white = 255, 255, 255
black = 0, 0, 0
red = (255, 0, 0)
screen_height = 600
fps = 30
green = 0,255,0
font = pygame.font.SysFont(None, 45)
score_time = True
clock = pygame.time.Clock()
game_window = pygame.display.set_mode([screen_width, screen_height])
pygame.display.set_caption("PONG GAME")


player = pygame.Rect(1.5, 30, 25, 110)
ball = pygame.Rect(screen_width / 2 - 15, screen_height / 2 - 15, 30, 30)

pygame.display.update()
aline = (34, 35, 76,)
ballspeed_y = 8
ball_speed_x = 8
opponent_speed = 6
opponent1 = pygame.Rect(874, 200, 25, 110)
player_score = 0
opponent_score = 0


player_speed = 0
def game_loop():
    # pygame.mixer.init()
    pygame.mixer.music.stop()
    pygame.mixer.music.load("C:\\Users\\Dell\\Downloads\\Cheap Thrills(PagalWorld.com.se).mp3")
    pygame.mixer.music.play()
    global player_speed, player, opponent1, opponent_speed
    while True:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    player.y -= 6
                if event.key == pygame.K_UP:
                    player_speed += - 6
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_UP:
                    player_speed -= 6
                if event.key == pygame.K_DOWN:
                    player_speed += 6

        game_window.fill(grey)
        textscreen(f"player_score: {player_score}",red,207,20)
        textscreen(f"Opponent_score: {opponent_score}",red,460,20)
        player = pygame.draw.rect(game_window, black,(player))
        opponent = pygame.draw.rect(game_window, black, (opponent1))
        pygame.draw.ellipse(game_window,black, (ball))
        pygame.draw.aaline(game_window, black, (screen_width / 2, 0), (screen_width / 2, screen_height))
        player_animation()
        ball_animation()
        opponent_ai()
        if score_time:
            ball_start()
        pygame.display.flip()
        clock.tick(fps)

home_screen()
pygame.quit()
quit()
