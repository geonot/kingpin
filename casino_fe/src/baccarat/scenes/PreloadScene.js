import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
    constructor() {
        super('PreloadScene');
    }

    preload() {
        // Display loading progress
        const progressBar = this.add.graphics();
        const progressBox = this.add.graphics();
        progressBox.fillStyle(0x222222, 0.8);
        progressBox.fillRect(this.cameras.main.width / 2 - 160, this.cameras.main.height / 2 - 25, 320, 50);

        // Placeholder paths for loading bar assets
        this.load.image('loading_bar_bg', 'assets/images/ui/loading_bar_bg.png');
        this.load.image('loading_bar_fill', 'assets/images/ui/loading_bar_fill.png');

        this.load.on('progress', (value) => {
            progressBar.clear();
            progressBar.fillStyle(0xffffff, 1);
            progressBar.fillRect(this.cameras.main.width / 2 - 150, this.cameras.main.height / 2 - 15, 300 * value, 30);
        });

        this.load.on('complete', () => {
            progressBar.destroy();
            progressBox.destroy();
        });

        // Load all Baccarat game assets
        this.load.image('baccarat_table', 'assets/images/baccarat/table.png');
        this.load.image('card_back', 'assets/images/cards/card_back.png');
        this.load.atlas('cards_atlas', 'assets/images/cards/cards_atlas.png', 'assets/images/cards/cards_atlas.json');
        this.load.spritesheet('chips_sprite', 'assets/images/baccarat/chips.png', { frameWidth: 100, frameHeight: 100 });
        this.load.audio('deal_sound', ['assets/audio/baccarat/deal.mp3']);
        this.load.audio('chip_sound', ['assets/audio/baccarat/chip.mp3']);
        this.load.audio('win_sound', ['assets/audio/baccarat/win.mp3']);
        this.load.audio('lose_sound', ['assets/audio/baccarat/lose.mp3']);
    }

    create() {
        // Initialize animations if any from spritesheets
        // this.anims.create({...});

        this.scene.start('GameScene');
        this.scene.launch('UIScene'); // Launch UIScene in parallel
    }
}
