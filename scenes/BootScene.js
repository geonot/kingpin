class BootScene extends Phaser.Scene {
    constructor() {
        super({ key: 'BootScene' });
    }

    preload() {
        // Load assets for the loading screen (e.g., logo, progress bar background)
        // For now, we'll keep this empty
    }

    create() {
        this.scene.start('PreloadScene');
    }
}
