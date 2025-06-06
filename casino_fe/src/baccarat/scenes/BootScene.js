import Phaser from 'phaser';

export default class BootScene extends Phaser.Scene {
    constructor() {
        super('BootScene');
    }

    preload() {
        // Load assets for PreloadScene (e.g., loading bar, logo)
        this.load.image('logo', 'assets/images/ui/logo.png'); // Optional: Uncomment if a logo is desired
        this.load.image('loading_bar_bg', 'assets/images/ui/loading_bar_bg.png');
        this.load.image('loading_bar_fill', 'assets/images/ui/loading_bar_fill.png');
    }

    create() {
        this.scene.start('PreloadScene');
    }
}
