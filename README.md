# 潜艇大战 (Submarine Battle)

基于 Pygame 的潜艇大战视频小游戏。

## 运行方式

```bash
pip install pygame
python submarineBattle.py
```

## 操作说明

| 按键 | 功能 |
|------|------|
| ← → | 移动军舰 |
| 空格 | 释放深水炸弹 |
| R | 游戏结束后重新开始 |
| Q | 游戏结束后退出 |

## 项目结构

```
├── submarineBattle.py          # 游戏主程序
├── rep.py                      # 实验报告生成器
├── images/                     # 游戏图片资源
└── 潜艇大战课程设计实验报告.docx  # 课程设计报告
```

## 技术特点

- 面向对象设计：Warship、DepthBomb、Submarine、Explosion、ComboDisplay 五大实体类
- 连击奖励系统：分层奖励（5连击双倍分/3连击同分）
- 程序化音效：无需外部音频文件，数学函数合成方波音效
- 难度递增：随得分加速潜艇生成
- 事件双重检测：事件队列 + OS 键盘状态查询，确保交互可靠
- 健壮性设计：字体 fallback、图片容错、最高分 JSON 持久化

## 开发环境

- Python 3.12
- Pygame 2.6.1
- SDL 2.28.4
