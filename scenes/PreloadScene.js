class PreloadScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PreloadScene' });
    }

    preload() {
        // Display a loading indicator
        let loadingText = this.add.text(this.cameras.main.width / 2, this.cameras.main.height / 2, 'Loading...', {
            font: '20px monospace',
            fill: '#ffffff'
        });
        loadingText.setOrigin(0.5, 0.5);

        // Load all game assets (images, audio)
        this.load.audio('plink', ['sounds/plink.mp3']);
        this.load.audio('zap', ['sounds/zap.mp3']);
        this.load.audio('collect', ['sounds/collect.mp3']);
        this.load.audio('win', ['sounds/win.mp3']);
        this.load.audio('drop', ['sounds/drop.mp3']);
        this.load.audio('jackpot_sound', ['sounds/jackpot.mp3']);
        this.load.audio('portal_activate', ['sounds/portal.mp3']);

        // Optional: Load a simple particle texture if you don't want to generate 'pixel' in GameScene
        // let graphics = this.make.graphics();
        // graphics.fillStyle(0xffffff);
        // graphics.fillRect(0, 0, 8, 8); // A small square for particle
        // graphics.generateTexture('particle_square', 8, 8);
        // graphics.destroy();
    }

    create() {
        this.scene.start('GameScene');
    }
}
