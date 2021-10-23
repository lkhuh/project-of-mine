import pygame
pygame.init()
import random
pygame.mixer.init()
pygame.mixer.music.load("C:\\Users\\Dell\\Downloads\\back.mp3.mp3")
pygame.mixer.music.play()

white = (255, 255, 255)
red = (255, 0, 0)
blue = (0, 0, 255)
black = (0, 0, 0)
fps = 60
font = pygame.font.SysFont(None, 55)
def textscreen(text, color, x, y):
    screentext = font.render(text,True,color)
    gamewindow.blit(screentext,[x,y])
def plot_snake(gameWindow, color, snk_list, snake_size):
    for x,y in snk_list:
        pygame.draw.rect(gameWindow, color, [x, y, snake_size, snake_size])
clock = pygame.time.Clock()
screen_height = 600
screen_width = 900
gamewindow = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("SNAKE game made by - sparsh")
purple = (203,195,227)
# # backround creating
bgimg = pygame.image.load("C:\\Users\\Dell\\Downloads\\background2.jpg")
bgimg = pygame.transform.scale(bgimg,(screen_width,screen_height)).convert_alpha()
goimg = pygame.image.load("C:\\Users\\Dell\\Downloads\\gameover.jpg")
goimg = pygame.transform.scale(bgimg,(screen_width,screen_height)).convert_alpha()


def welcome():
    exit_game = False
    while not exit_game:
        gamewindow.fill(purple)
        textscreen("WELCOME TO SNAKE GAME ",black,230,260)
        textscreen("press space to play snake game",black,210,295)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit_game = True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    gameloop()
        pygame.display.update()
        clock.tick(60)




def gameloop():
    exit_game = False
    game_over = False
    snake_x = 45
    snake_y = 55
    velocity_x = 0
    velocity_y = 0
    snk_list = []
    snk_length = 1

    food_x = random.randint(20, screen_width / 2)
    food_y = random.randint(20, screen_height / 2)
    score = 0
    init_velocity = 5
    snake_size = 15
    fps = 60
    while not exit_game:

        if game_over:
            gamewindow.fill(white)
            gamewindow.blit(goimg,(0,0))
            textscreen("Game Over! Press Enter To Continue", red, 100, 250)



            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit_game = True

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        gameloop()

        else:

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit_game = True

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RIGHT:
                        velocity_x = init_velocity
                        velocity_y = 0

                    if event.key == pygame.K_LEFT:
                        velocity_x = - init_velocity
                        velocity_y = 0

                    if event.key == pygame.K_UP:
                        velocity_y = - init_velocity
                        velocity_x = 0

                    if event.key == pygame.K_DOWN:
                        velocity_y = init_velocity
                        velocity_x = 0

            snake_x = snake_x + velocity_x
            snake_y = snake_y + velocity_y

            if abs(snake_x - food_x) < 6 and abs(snake_y - food_y) < 6:
                score += 1
                food_x = random.randint(20, screen_width / 2)
                food_y = random.randint(20, screen_height / 2)
                snk_length += 5

            gamewindow.fill(white)
            gamewindow.blit(bgimg,(0,0))
            textscreen("Score: " + str(score * 10), red, 5, 5)
            pygame.draw.rect(gamewindow, red, [food_x, food_y, snake_size, snake_size])

            head = []
            head.append(snake_x)
            head.append(snake_y)
            snk_list.append(head)

            if len(snk_list) > snk_length:
                del snk_list[0]

            if head in snk_list[:-1]:
                game_over = True
                gamewindow.blit(goimg, (0, 0))
                pygame.mixer.music.load("C:\\Users\\Dell\\Downloads\\mixkit-arcade-retro-game-over-213.wav")
                pygame.mixer.music.play()

            if snake_x < 0 or snake_x > screen_width or snake_y < 0 or snake_y > screen_height:
                game_over = True
                pygame.mixer.music.load("C:\\Users\\Dell\\Downloads\\mixkit-arcade-retro-game-over-213.wav")
                pygame.mixer.music.play()
                gamewindow.blit(goimg, (0, 0))
            plot_snake(gamewindow, black, snk_list, snake_size)
        pygame.display.update()
        clock.tick(fps)

    pygame.quit()
    quit()


welcome()





