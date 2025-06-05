import Phaser from 'phaser';

export default class BootScene extends Phaser.Scene {
    constructor() {
        super('BootScene');
    }

    preload() {
        // TODO: Load assets for PreloadScene (e.g., loading bar, logo)
        // this.load.image('logo', 'path/to/logo.png');
        // this.load.image('loading_bar_bg', 'path/to/loading_bar_bg.png');
        // this.load.image('loading_bar_fill', 'path/to/loading_bar_fill.png');
    }

    create() {
        this.scene.start('PreloadScene');
    }
}
