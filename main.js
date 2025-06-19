const config = {
    type: Phaser.AUTO,
    parent: 'game-container',
    width: 800,
    height: 600,
    scene: [BootScene, PreloadScene, GameScene]
};

const game = new Phaser.Game(config);
