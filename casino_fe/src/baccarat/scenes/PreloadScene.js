import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
    constructor() {
        super('PreloadScene');
    }

    preload() {
        // Display loading progress
        // const progressBar = this.add.graphics();
        // const progressBox = this.add.graphics();
        // progressBox.fillStyle(0x222222, 0.8);
        // progressBox.fillRect(this.cameras.main.width / 2 - 160, this.cameras.main.height / 2 - 25, 320, 50);

        // this.load.on('progress', (value) => {
        //     progressBar.clear();
        //     progressBar.fillStyle(0xffffff, 1);
        //     progressBar.fillRect(this.cameras.main.width / 2 - 150, this.cameras.main.height / 2 - 15, 300 * value, 30);
        // });

        // this.load.on('complete', () => {
        //     progressBar.destroy();
        //     progressBox.destroy();
        // });

        // TODO: Load all Baccarat game assets
        // this.load.image('table', 'path/to/baccarat_table.png');
        // this.load.atlas('cards', 'path/to/cards_atlas.png', 'path/to/cards_atlas.json');
        // this.load.spritesheet('chips', 'path/to/chips_spritesheet.png', { frameWidth: 100, frameHeight: 100 });
        // this.load.audio('dealSound', ['path/to/deal.mp3']);
        // ... other assets
    }

    create() {
        // Initialize animations if any from spritesheets
        // this.anims.create({...});

        this.scene.start('GameScene');
        this.scene.launch('UIScene'); // Launch UIScene in parallel
    }
}
