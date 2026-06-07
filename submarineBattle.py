"""
潜艇大战游戏 - Submarine Battle Game
玩家控制军舰在海面移动，释放深水炸弹消灭潜艇。
"""

import pygame
import random
import sys
import os
import json
import math
import struct

# 确保工作目录是脚本所在目录（兼容PyInstaller打包）
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 游戏配置常量
# ============================================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WATER_LEVEL_Y = 350
FRAMES_PER_SECOND = 60

SHIP_SPEED = 5
BOMB_SPEED = 6
BOMB_COOLDOWN_FRAMES = 12       # 炸弹冷却时间（帧）
SUBMARINE_MIN_SPEED = 1
SUBMARINE_MAX_SPEED = 3
SUBMARINE_SPAWN_INTERVAL = 60   # 帧（初始值，比原来的90更快）
SUBMARINE_MIN_SPAWN_INTERVAL = 20  # 帧（最高难度，比原来的25更快）
EXPLOSION_DURATION = 20         # 帧
EXPLOSION_FRAME_COUNT = 3       # 爆炸动画帧数

MAX_BOMBS = 3
INITIAL_LIVES = 3
MAX_LIVES = 5                   # 生命值上限
LIFE_BONUS_SCORE = 500          # 每500分奖励一条命
COMBO_TIMEOUT_FRAMES = 90       # 连击超时时间（帧，约1.5秒）
HIGH_SCORE_FILE = "highscore.json"

IMAGE_DIR = "images"

# ============================================================
# 工具函数
# ============================================================

def loadImage(fileName, scaleWidth=None, scaleHeight=None):
    """加载图片并可选择缩放；加载失败时返回占位色块"""
    path = os.path.join(IMAGE_DIR, fileName)
    try:
        image = pygame.image.load(path).convert_alpha()
        if scaleWidth and scaleHeight:
            image = pygame.transform.scale(image, (scaleWidth, scaleHeight))
        return image
    except (pygame.error, FileNotFoundError):
        print(f"警告: 无法加载图片 '{path}'，使用占位图")
        w = scaleWidth or 50
        h = scaleHeight or 50
        placeholder = pygame.Surface((w, h), pygame.SRCALPHA)
        placeholder.fill((255, 0, 255))  # 品红色占位
        return placeholder


def createFont(nameList, size):
    """依次尝试字体列表，全部失败则使用pygame默认字体"""
    for fontName in nameList:
        try:
            font = pygame.font.SysFont(fontName, size)
            # 验证字体是否真实可用（SysFont不抛异常但可能回退）
            testSurface = font.render("测试", True, (255, 255, 255))
            if testSurface.get_width() > 0:
                return font
        except Exception:
            continue
    print(f"警告: 所有中文字体不可用，使用pygame默认字体")
    return pygame.font.Font(None, size)


def generateBeepSound(frequency=440, duration=0.1, volume=0.3):
    """程序化生成简单音效（带衰减包络的方波），无需外部音频文件"""
    sampleRate = 11025  # 降低采样率避免 struct.pack 参数展开过多
    sampleCount = int(sampleRate * duration)
    samples = []
    for i in range(sampleCount):
        t = i / sampleRate
        value = 1 if math.sin(2 * math.pi * frequency * t) > 0 else -1
        envelope = max(0, 1 - t / duration)
        samples.append(int(value * envelope * volume * 32767))
    try:
        sound = pygame.mixer.Sound(buffer=bytes(
            struct.pack('h' * len(samples), *samples)))
    except Exception:
        print(f"警告: 无法生成音效 ({frequency}Hz), 使用静默音效")
        sound = pygame.mixer.Sound(buffer=bytes(2))
    return sound


def loadHighScore():
    """从文件加载最高分"""
    try:
        with open(HIGH_SCORE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('highScore', 0)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 0


def saveHighScore(score):
    """保存最高分到文件"""
    try:
        current = loadHighScore()
        if score > current:
            with open(HIGH_SCORE_FILE, 'w', encoding='utf-8') as f:
                json.dump({'highScore': score}, f)
    except Exception:
        pass  # 保存失败不阻塞游戏


# ============================================================
# 全局预加载图片资源（避免每个实例重复加载）
# ============================================================
PRELOADED_IMAGES = {}

def preloadAllImages():
    """游戏启动时一次性预加载所有图片"""
    global PRELOADED_IMAGES
    imageFiles = {
        'ship0': 'ship0.png',
        'ship1': 'ship1.png',
        'boom': 'boom.png',
        'q1': 'q1.png',
        'q2': 'q2.png',
        'r1': 'r1.png',
        'h2': 'h2.png',
        'b': 'b.png',
        'b1': 'b1.png',
        'b2': 'b2.png',
        'background': 'background.png',
    }
    for key, fileName in imageFiles.items():
        PRELOADED_IMAGES[key] = loadImage(fileName)
    print(f"预加载了 {len(PRELOADED_IMAGES)} 张图片")


def getPreloadedImage(key):
    """获取预加载的图片"""
    return PRELOADED_IMAGES.get(key)


# ============================================================
# 游戏实体类
# ============================================================

class Warship:
    """玩家军舰：负责军舰的位置、移动和炸弹释放"""

    def __init__(self):
        self.shipImages = [
            getPreloadedImage('ship0'),
            getPreloadedImage('ship1')
        ]
        self.shipWidth = self.shipImages[0].get_width()
        self.shipHeight = self.shipImages[0].get_height()
        self.positionX = (SCREEN_WIDTH - self.shipWidth) // 2
        self.positionY = WATER_LEVEL_Y - self.shipHeight
        self.animationFrame = 0
        self.animationTimer = 0
        self.isMovingLeft = False
        self.isMovingRight = False

    def moveLeft(self):
        """向左移动"""
        self.isMovingLeft = True

    def moveRight(self):
        """向右移动"""
        self.isMovingRight = True

    def stopMovingLeft(self):
        """停止左移"""
        self.isMovingLeft = False

    def stopMovingRight(self):
        """停止右移"""
        self.isMovingRight = False

    def updatePosition(self):
        """更新军舰位置，确保不超出屏幕边界"""
        if self.isMovingLeft:
            self.positionX -= SHIP_SPEED
        if self.isMovingRight:
            self.positionX += SHIP_SPEED
        self.constrainToScreen()

    def constrainToScreen(self):
        """将军舰限制在屏幕范围内"""
        if self.positionX < 0:
            self.positionX = 0
        if self.positionX > SCREEN_WIDTH - self.shipWidth:
            self.positionX = SCREEN_WIDTH - self.shipWidth

    def updateAnimation(self):
        """更新军舰动画帧"""
        if self.isMovingLeft or self.isMovingRight:
            self.animationTimer += 1
            if self.animationTimer >= 10:
                self.animationTimer = 0
                self.animationFrame = (self.animationFrame + 1) % 2

    def getCurrentImage(self):
        """获取当前动画帧的军舰图片"""
        return self.shipImages[self.animationFrame]

    def getBombReleasePosition(self):
        """获取炸弹释放位置(军舰底部中央)"""
        centerX = self.positionX + self.shipWidth // 2
        bottomY = self.positionY + self.shipHeight
        return centerX, bottomY

    def getCollisionRect(self):
        """获取军舰的碰撞矩形"""
        return pygame.Rect(self.positionX, self.positionY,
                           self.shipWidth, self.shipHeight)


class DepthBomb:
    """深水炸弹：负责炸弹的移动和状态管理"""

    _bombImage = None  # 类级别缓存

    @classmethod
    def getBombImage(cls):
        """获取缓存的炸弹图片"""
        if cls._bombImage is None:
            cls._bombImage = getPreloadedImage('boom')
        return cls._bombImage

    def __init__(self, positionX, positionY):
        self.bombImage = DepthBomb.getBombImage()
        self.positionX = positionX - self.bombImage.get_width() // 2
        self.positionY = positionY
        self.isActive = True

    def updatePosition(self):
        """更新炸弹位置(向下移动)"""
        self.positionY += BOMB_SPEED

    def isOutOfScreen(self):
        """检查炸弹是否超出屏幕底部"""
        return self.positionY > SCREEN_HEIGHT

    def getCollisionRect(self):
        """获取炸弹的碰撞矩形"""
        return pygame.Rect(self.positionX, self.positionY,
                           self.bombImage.get_width(),
                           self.bombImage.get_height())

    def render(self, screen):
        """绘制炸弹"""
        screen.blit(self.bombImage, (self.positionX, self.positionY))


class Submarine:
    """潜艇：负责潜艇的移动、出现和销毁"""

    SUBMARINE_TYPES = ["q1", "q2", "r1", "h2"]
    SUBMARINE_SCORES = {"q1": 10, "q2": 20, "r1": 30, "h2": 50}

    # 类级别预加载的图片缓存
    _imageCache = {}

    @classmethod
    def getSubmarineImage(cls, submarineType):
        """获取缓存的潜艇图片"""
        if submarineType not in cls._imageCache:
            cls._imageCache[submarineType] = getPreloadedImage(submarineType)
        return cls._imageCache[submarineType]

    def __init__(self):
        submarineType = random.choice(self.SUBMARINE_TYPES)
        self.submarineImage = Submarine.getSubmarineImage(submarineType)
        self.submarineType = submarineType
        self.scoreValue = self.SUBMARINE_SCORES[submarineType]
        self.imageWidth = self.submarineImage.get_width()
        self.imageHeight = self.submarineImage.get_height()
        self.isActive = True

        # 随机从左或右边出现，在水面以下的区域
        self.direction = random.choice([-1, 1])
        if self.direction == 1:
            self.positionX = -self.imageWidth
        else:
            self.positionX = SCREEN_WIDTH

        minY = WATER_LEVEL_Y + 20
        maxY = SCREEN_HEIGHT - self.imageHeight - 20
        self.positionY = random.randint(minY, maxY)
        self.moveSpeed = random.randint(SUBMARINE_MIN_SPEED,
                                        SUBMARINE_MAX_SPEED)

    def updatePosition(self):
        """更新潜艇位置"""
        self.positionX += self.moveSpeed * self.direction

    def isOutOfScreen(self):
        """检查潜艇是否完全离开屏幕"""
        if self.direction == 1:
            return self.positionX > SCREEN_WIDTH + self.imageWidth
        else:
            return self.positionX < -self.imageWidth

    def getCollisionRect(self):
        """获取潜艇的碰撞矩形"""
        return pygame.Rect(self.positionX, self.positionY,
                           self.imageWidth, self.imageHeight)

    def render(self, screen):
        """绘制潜艇"""
        if self.direction == -1:
            flippedImage = pygame.transform.flip(self.submarineImage,
                                                 True, False)
            screen.blit(flippedImage, (self.positionX, self.positionY))
        else:
            screen.blit(self.submarineImage, (self.positionX, self.positionY))


class Explosion:
    """爆炸效果：播放爆炸动画"""

    _explosionImages = None  # 类级别缓存

    @classmethod
    def getExplosionImages(cls):
        """获取缓存的爆炸图片"""
        if cls._explosionImages is None:
            cls._explosionImages = [
                getPreloadedImage('b'),
                getPreloadedImage('b1'),
                getPreloadedImage('b2')
            ]
        return cls._explosionImages

    def __init__(self, positionX, positionY):
        self.explosionImages = Explosion.getExplosionImages()
        self.positionX = positionX - self.explosionImages[0].get_width() // 2
        self.positionY = positionY - self.explosionImages[0].get_height() // 2
        self.currentFrame = 0
        self.frameTimer = 0
        self.isActive = True

    def updateAnimation(self):
        """更新爆炸动画帧"""
        self.frameTimer += 1
        if self.frameTimer >= EXPLOSION_DURATION // EXPLOSION_FRAME_COUNT:
            self.frameTimer = 0
            self.currentFrame += 1
            if self.currentFrame >= EXPLOSION_FRAME_COUNT:
                self.isActive = False

    def render(self, screen):
        """绘制爆炸效果"""
        if self.isActive:
            screen.blit(self.explosionImages[self.currentFrame],
                        (self.positionX, self.positionY))


class ComboDisplay:
    """连击显示：在屏幕上显示连击数和额外加分"""

    def __init__(self, comboCount, bonusScore, positionX, positionY):
        self.comboCount = comboCount
        self.bonusScore = bonusScore
        self.positionX = positionX
        self.positionY = positionY
        self.lifeTime = 60  # 显示帧数（约1秒）
        self.isActive = True

    def update(self):
        """更新显示生命周期"""
        self.lifeTime -= 1
        self.positionY -= 1  # 向上飘动
        if self.lifeTime <= 0:
            self.isActive = False

    def render(self, screen, font):
        """绘制连击文字"""
        if not self.isActive:
            return
        alpha = min(255, self.lifeTime * 4)
        if self.comboCount >= 5:
            color = (255, 215, 0)  # 金色
            text = f"* {self.comboCount}连击! +{self.bonusScore}"
        elif self.comboCount >= 3:
            color = (255, 165, 0)  # 橙色
            text = f"* {self.comboCount}连击! +{self.bonusScore}"
        else:
            color = (100, 255, 100)  # 绿色
            text = f"{self.comboCount}连击! +{self.bonusScore}"
        textSurface = font.render(text, True, color)
        textSurface.set_alpha(alpha)
        screen.blit(textSurface, (self.positionX, self.positionY))


# ============================================================
# 游戏主控制器
# ============================================================

class GameController:
    """游戏主控制器：管理游戏循环、事件、碰撞检测和得分"""

    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("潜艇大战 - Submarine Battle")
        self.clock = pygame.time.Clock()
        self.isRunning = True

        # 预加载所有图片资源
        preloadAllImages()

        self.backgroundImage = getPreloadedImage('background')
        self.warship = Warship()
        self.bombList = []
        self.submarineList = []
        self.explosionList = []
        self.comboDisplayList = []

        # 分数与生命
        self.score = 0
        self.lives = INITIAL_LIVES
        self.highScore = loadHighScore()
        self.lastLifeBonusScore = 0  # 上次奖励生命时的分数

        # 生成计时器
        self.spawnTimer = 0
        self._cachedSpawnInterval = SUBMARINE_SPAWN_INTERVAL
        self._lastScoreForInterval = 0

        # 炸弹冷却
        self.bombCooldownTimer = 0

        # 连击系统
        self.comboCount = 0
        self.comboTimer = 0

        # 字体（fallback链：SimHei → Microsoft YaHei → 默认字体）
        self.font = createFont(["SimHei", "Microsoft YaHei", "Noto Sans CJK SC",
                                "WenQuanYi Micro Hei", "Arial"], 24)
        self.smallFont = createFont(["SimHei", "Microsoft YaHei", "Noto Sans CJK SC",
                                      "WenQuanYi Micro Hei", "Arial"], 18)
        self.comboFont = createFont(["SimHei", "Microsoft YaHei", "Arial"], 22)

        # 音效（程序化生成）
        self.soundShoot = self._createShootSound()
        self.soundExplosion = self._createExplosionSound()
        self.soundGameOver = self._createGameOverSound()
        self.soundLifeBonus = self._createLifeBonusSound()
        self.soundCombo = self._createComboSound()

    def _createShootSound(self):
        """生成射击音效（短促低音）"""
        return generateBeepSound(frequency=220, duration=0.08, volume=0.2)

    def _createExplosionSound(self):
        """生成爆炸音效（降频噪声）"""
        return generateBeepSound(frequency=80, duration=0.25, volume=0.4)

    def _createGameOverSound(self):
        """生成游戏结束音效（降调）"""
        # 使用较少的采样点避免 struct.pack 参数过多
        sampleRate = 8000
        duration = 0.5
        totalSamples = int(sampleRate * duration)
        samples = []
        for i in range(totalSamples):
            t = i / sampleRate
            freq = 300 - t * 400
            if freq < 20:
                freq = 20
            value = math.sin(2 * math.pi * freq * t)
            envelope = max(0, 1 - t / duration)
            samples.append(int(value * envelope * 0.5 * 32767))
        return pygame.mixer.Sound(buffer=bytes(
            struct.pack('h' * len(samples), *samples)))

    def _createLifeBonusSound(self):
        """生成奖励音效（升调）"""
        sampleRate = 8000
        duration = 0.25
        totalSamples = int(sampleRate * duration)
        samples = []
        for i in range(totalSamples):
            t = i / sampleRate
            freq = 400 + t * 600
            value = math.sin(2 * math.pi * freq * t)
            envelope = max(0, 1 - t / duration)
            samples.append(int(value * envelope * 0.4 * 32767))
        return pygame.mixer.Sound(buffer=bytes(
            struct.pack('h' * len(samples), *samples)))

    def _createComboSound(self):
        """生成连击音效（短促高音）"""
        return generateBeepSound(frequency=660, duration=0.1, volume=0.25)

    # ---- 游戏主循环 ----

    def startGame(self):
        """启动游戏主循环"""
        self.showStartScreen()
        while True:
            while self.isRunning:
                self.processInputEvents()
                self.updateGameState()
                self.checkCollisions()
                self.renderFrame()
                self.clock.tick(FRAMES_PER_SECOND)
            saveHighScore(self.score)
            self.showGameOverScreen()

    def showStartScreen(self):
        """显示游戏开始画面"""
        pygame.event.get()

        titleFont = createFont(["SimHei", "Microsoft YaHei", "Arial"], 56)
        titleText = titleFont.render("潜艇大战", True, (255, 255, 255))
        startText = self.font.render("按 空格键 开始游戏", True, (100, 255, 100))
        controlText = self.smallFont.render(
            "方向键: 移动军舰    空格键: 释放深水炸弹",
            True, (200, 200, 200))
        objectiveText = self.smallFont.render(
            "消灭所有潜艇，保护海域安全！",
            True, (180, 180, 220))
        highScoreText = self.smallFont.render(
            f"最高分: {self.highScore}",
            True, (255, 215, 0))

        titleRect = titleText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 80))
        startRect = startText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10))
        controlRect = controlText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 55))
        objectiveRect = objectiveText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        highScoreRect = highScoreText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 95))

        # 绘制背景和军舰
        self.screen.blit(self.backgroundImage, (0, 0))
        currentShipImage = self.warship.getCurrentImage()
        self.screen.blit(currentShipImage,
                         (self.warship.positionX, self.warship.positionY))

        # 半透明遮罩
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(170)
        overlay.fill((0, 20, 50))
        self.screen.blit(overlay, (0, 0))

        self.screen.blit(titleText, titleRect)
        self.screen.blit(objectiveText, objectiveRect)
        self.screen.blit(startText, startRect)
        self.screen.blit(controlText, controlRect)
        self.screen.blit(highScoreText, highScoreRect)
        pygame.display.flip()

        self.waitForStartKey()

    def _waitForKey(self, *targetKeys):
        """等待按键：双重检测——事件队列 + 直接 OS 键盘状态查询。
        get_pressed() 直接从操作系统查询键盘，完全绕过 pygame 事件队列。"""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quitGame()
                elif event.type == pygame.KEYDOWN:
                    if event.key in targetKeys:
                        return event.key
            pygame.event.pump()
            keys = pygame.key.get_pressed()
            for target in targetKeys:
                if keys[target]:
                    return target
            pygame.time.wait(20)

    def waitForStartKey(self):
        """等待玩家按下空格键开始游戏"""
        self._waitForKey(pygame.K_SPACE)

    # ---- 事件处理 ----

    def processInputEvents(self):
        """处理键盘输入事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.isRunning = False
            elif event.type == pygame.KEYDOWN:
                self.handleKeyPress(event.key)
            elif event.type == pygame.KEYUP:
                self.handleKeyRelease(event.key)

    def handleKeyPress(self, key):
        """处理按键按下"""
        if key == pygame.K_LEFT:
            self.warship.moveLeft()
        elif key == pygame.K_RIGHT:
            self.warship.moveRight()
        elif key == pygame.K_SPACE:
            self.releaseBomb()

    def handleKeyRelease(self, key):
        """处理按键释放"""
        if key == pygame.K_LEFT:
            self.warship.stopMovingLeft()
        elif key == pygame.K_RIGHT:
            self.warship.stopMovingRight()

    # ---- 炸弹系统 ----

    def releaseBomb(self):
        """释放深水炸弹(冷却 + 数量限制)"""
        if self.bombCooldownTimer > 0:
            return
        if len(self.bombList) < MAX_BOMBS:
            bombX, bombY = self.warship.getBombReleasePosition()
            self.bombList.append(DepthBomb(bombX, bombY))
            self.bombCooldownTimer = BOMB_COOLDOWN_FRAMES
            self.soundShoot.play()

    def updateBombs(self):
        """更新所有炸弹位置，移除越界的炸弹"""
        for bomb in self.bombList:
            bomb.updatePosition()
            if bomb.isOutOfScreen():
                bomb.isActive = False
        self.bombList = [bomb for bomb in self.bombList if bomb.isActive]

    # ---- 潜艇系统 ----

    def updateSubmarines(self):
        """更新所有潜艇位置，移除越界的潜艇"""
        for submarine in self.submarineList:
            submarine.updatePosition()
            if submarine.isOutOfScreen():
                submarine.isActive = False
                self.lives -= 1
                self.comboCount = 0  # 漏掉潜艇重置连击
        self.submarineList = [sub for sub in self.submarineList if sub.isActive]
        self.checkGameOver()

    def calculateSpawnInterval(self):
        """根据得分计算当前潜艇生成间隔；缓存避免每帧重复计算"""
        if self.score != self._lastScoreForInterval:
            reduction = self.score // 100
            interval = SUBMARINE_SPAWN_INTERVAL - reduction * 5
            if interval < SUBMARINE_MIN_SPAWN_INTERVAL:
                interval = SUBMARINE_MIN_SPAWN_INTERVAL
            self._cachedSpawnInterval = interval
            self._lastScoreForInterval = self.score
        return self._cachedSpawnInterval

    def spawnSubmarines(self):
        """按时间间隔自动产生潜艇"""
        self.spawnTimer += 1
        if self.spawnTimer >= self.calculateSpawnInterval():
            self.spawnTimer = 0
            self.submarineList.append(Submarine())

    # ---- 爆炸系统 ----

    def updateExplosions(self):
        """更新所有爆炸动画，移除已完成的"""
        for explosion in self.explosionList:
            explosion.updateAnimation()
        self.explosionList = [exp for exp in self.explosionList if exp.isActive]

    # ---- 碰撞检测 ----

    def checkCollisions(self):
        """检测炸弹与潜艇的碰撞"""
        for bomb in self.bombList:
            if not bomb.isActive:
                continue
            bombRect = bomb.getCollisionRect()
            for submarine in self.submarineList:
                if not submarine.isActive:
                    continue
                if bombRect.colliderect(submarine.getCollisionRect()):
                    self.handleBombHitSubmarine(bomb, submarine)
                    break

    def handleBombHitSubmarine(self, bomb, submarine):
        """处理炸弹命中潜艇"""
        bomb.isActive = False
        submarine.isActive = False

        # 连击计数与奖励
        self.comboCount += 1
        self.comboTimer = COMBO_TIMEOUT_FRAMES
        comboBonus = 0
        if self.comboCount >= 5:
            comboBonus = submarine.scoreValue * 2  # 5连击以上双倍分
        elif self.comboCount >= 3:
            comboBonus = submarine.scoreValue       # 3连击以上额外同分
        else:
            comboBonus = self.comboCount * 2         # 1-2连击少量加分

        totalScore = submarine.scoreValue + comboBonus
        self.score += totalScore

        # 检查生命奖励
        self.checkLifeBonus()

        # 创建爆炸效果
        centerX = submarine.positionX + submarine.imageWidth // 2
        centerY = submarine.positionY + submarine.imageHeight // 2
        self.explosionList.append(Explosion(centerX, centerY))

        # 创建连击显示
        displayX = centerX - 40
        displayY = centerY - 30
        self.comboDisplayList.append(
            ComboDisplay(self.comboCount, comboBonus, displayX, displayY))

        # 音效
        if self.comboCount >= 3:
            self.soundCombo.play()
        else:
            self.soundExplosion.play()

    # ---- 生命奖励系统 ----

    def checkLifeBonus(self):
        """每达到 LIFE_BONUS_SCORE 的倍数奖励一条命"""
        currentMilestone = self.score // LIFE_BONUS_SCORE
        lastMilestone = self.lastLifeBonusScore // LIFE_BONUS_SCORE
        if currentMilestone > lastMilestone and self.lives < MAX_LIVES:
            self.lives += 1
            self.lastLifeBonusScore = self.score
            self.soundLifeBonus.play()

    # ---- 连击系统 ----

    def updateComboSystem(self):
        """更新连击计时和显示"""
        if self.comboCount > 0:
            self.comboTimer -= 1
            if self.comboTimer <= 0:
                self.comboCount = 0
        for display in self.comboDisplayList:
            display.update()
        self.comboDisplayList = [d for d in self.comboDisplayList if d.isActive]

    # ---- 游戏状态 ----

    def updateGameState(self):
        """更新游戏状态：军舰、炸弹、潜艇、爆炸、连击"""
        self.warship.updatePosition()
        self.warship.updateAnimation()
        if self.bombCooldownTimer > 0:
            self.bombCooldownTimer -= 1
        self.updateComboSystem()
        self.updateBombs()
        self.updateSubmarines()
        self.updateExplosions()
        self.spawnSubmarines()

    def checkGameOver(self):
        """检查游戏是否结束"""
        if self.lives <= 0:
            self.isRunning = False

    # ---- 渲染 ----

    def renderFrame(self):
        """渲染整个游戏画面"""
        self.screen.blit(self.backgroundImage, (0, 0))

        for bomb in self.bombList:
            if bomb.isActive:
                bomb.render(self.screen)

        for submarine in self.submarineList:
            if submarine.isActive:
                submarine.render(self.screen)

        for explosion in self.explosionList:
            if explosion.isActive:
                explosion.render(self.screen)

        for comboDisplay in self.comboDisplayList:
            comboDisplay.render(self.screen, self.comboFont)

        currentShipImage = self.warship.getCurrentImage()
        self.screen.blit(currentShipImage,
                         (self.warship.positionX, self.warship.positionY))

        self.renderUserInterface()
        pygame.display.flip()

    def renderUserInterface(self):
        """绘制得分、生命值、连击、最高分"""
        scoreText = self.font.render(f"得分: {self.score}",
                                     True, (255, 255, 255))
        livesText = self.font.render(f"生命: {self.lives}",
                                     True, (255, 255, 255))
        highScoreText = self.font.render(f"最高分: {self.highScore}",
                                         True, (255, 215, 0))
        hintText = self.smallFont.render(
            "方向键移动  空格键释放炸弹",
            True, (200, 200, 200))

        self.screen.blit(scoreText, (15, 10))
        self.screen.blit(livesText, (15, 40))
        self.screen.blit(highScoreText, (15, 70))

        # 连击提示
        if self.comboCount >= 2:
            comboText = self.comboFont.render(
                f"COMBO x{self.comboCount}", True, (255, 200, 50))
            self.screen.blit(comboText, (SCREEN_WIDTH // 2 - 60, 10))

        self.screen.blit(hintText, (SCREEN_WIDTH - 250, 10))

    # ---- 游戏结束 ----

    def quitGame(self):
        """退出游戏"""
        saveHighScore(self.score)
        pygame.quit()
        sys.exit()

    def resetGameState(self):
        """重置游戏状态以便重新开始"""
        self.warship = Warship()
        self.bombList = []
        self.submarineList = []
        self.explosionList = []
        self.comboDisplayList = []
        self.score = 0
        self.lives = INITIAL_LIVES
        self.lastLifeBonusScore = 0
        self.spawnTimer = 0
        self.bombCooldownTimer = 0
        self.comboCount = 0
        self.comboTimer = 0
        self._cachedSpawnInterval = SUBMARINE_SPAWN_INTERVAL
        self._lastScoreForInterval = 0
        self.isRunning = True

    def showGameOverScreen(self):
        """显示游戏结束画面，允许重新开始或退出"""
        pygame.event.get()

        # 判断是否新纪录（必须在更新highScore之前判断）
        isNewRecord = self.score > self.highScore
        if isNewRecord:
            self.highScore = self.score
            saveHighScore(self.score)

        self.soundGameOver.play()

        gameOverFont = createFont(["SimHei", "Microsoft YaHei", "Arial"], 48)
        gameOverText = gameOverFont.render("游戏结束", True, (255, 50, 50))
        finalScoreText = self.font.render(
            f"最终得分: {self.score}", True, (255, 255, 255))
        highScoreText = self.font.render(
            f"最高分: {self.highScore}", True, (255, 215, 0))
        newRecordText = None
        if isNewRecord:
            newRecordText = self.font.render(
                "新纪录！", True, (255, 215, 0))
        restartText = self.font.render(
            "按 R 键重新开始", True, (100, 255, 100))
        quitText = self.font.render(
            "按 Q 键退出", True, (255, 100, 100))

        textRect = gameOverText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 70))
        scoreRect = finalScoreText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10))
        highScoreRect = highScoreText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 25))
        restartRect = restartText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70))
        quitRect = quitText.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 105))

        # 先绘制背景再叠加遮罩，避免依赖上一帧残留画面
        self.screen.blit(self.backgroundImage, (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 30))
        self.screen.blit(overlay, (0, 0))

        self.screen.blit(gameOverText, textRect)
        self.screen.blit(finalScoreText, scoreRect)
        self.screen.blit(highScoreText, highScoreRect)
        if newRecordText:
            newRecordRect = newRecordText.get_rect(
                center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 55))
            self.screen.blit(newRecordText, newRecordRect)
        self.screen.blit(restartText, restartRect)
        self.screen.blit(quitText, quitRect)
        pygame.display.flip()

        self.waitForRestartOrQuit()

    def waitForRestartOrQuit(self):
        """等待玩家选择重新开始或退出"""
        key = self._waitForKey(pygame.K_r, pygame.K_q)
        if key == pygame.K_r:
            self.resetGameState()
        elif key == pygame.K_q:
            self.quitGame()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    game = GameController()
    game.startGame()
