import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PreloadScene' });
    }

    preload() {
        console.log('PreloadScene: Preload');
        const gameConfig = this.registry.get('gameConfig'); // Get config from registry

        if (!gameConfig) {
            console.error("PreloadScene: Game config not found in registry!");
            // Handle error - perhaps return to main menu or show error
            return;
        }

        this.createLoadingBar();

        // --- Load Game Assets Based on Config ---
        //const assetDir = gameConfig.asset_dir; // e.g., /slot1/
        const assetDir = '/'
        // 1. Background Image
        if (gameConfig.background?.image) {
            this.load.image('background', `${assetDir}${gameConfig.background.image.replace(/^\//, '')}`); // Remove leading slash if present
        }

        // 2. Symbol Images
        if (gameConfig.symbols && Array.isArray(gameConfig.symbols)) {
            gameConfig.symbols.forEach(symbol => {
                if (symbol.icon) {
                     // Use internal ID for texture key consistency
                    this.load.image(`symbol_${symbol.id}`, `${assetDir}${symbol.icon.replace(/^\//, '')}`);
                }
            });
        }

        // 3. UI Button Images
        if (gameConfig.ui?.buttons) {
            Object.values(gameConfig.ui.buttons).forEach(button => {
                if (button.icon && button.name) {
                    this.load.image(button.name, `${assetDir}${button.icon.replace(/^\//, '')}`);
                }
            });
             // Also load common UI assets if defined separately
            this.load.image('settings-button', '/assets/ui/settings.png'); // Example common asset
            this.load.image('payline-dot', '/assets/ui/payline_dot.png'); // Small dot for paylines
            this.load.image('win-particle', '/assets/ui/particle.png'); // Particle for win effects
        }


        // 4. Audio Files
        if (gameConfig.sound) {
            Object.entries(gameConfig.sound).forEach(([key, path]) => {
                if (path) {
                    // Ensure path has correct asset directory prefix
                    const fullPath = path.startsWith('/assets/') ? path : `${assetDir}${path.replace(/^\//, '')}`;
                    console.log(`Loading sound: ${key} from ${fullPath}`);
                    // Phaser determines format from extension
                    this.load.audio(key, fullPath);
                }
            });
        }

        // --- Loading Progress ---
        this.load.on('progress', (value) => {
            this.updateLoadingBar(value);
        });

        this.load.on('complete', () => {
            console.log('PreloadScene: Asset loading complete.');
            this.loadingFill?.destroy(); // Clean up loading bar elements
            this.loadingBg?.destroy();
            this.loadingText?.destroy();
            this.percentText?.destroy();

            // Start the main game scenes
            console.log('PreloadScene: Starting GameScene and UIScene...');
            this.scene.start('GameScene');
            this.scene.start('UIScene'); // Start UI scene concurrently
        });

         this.load.on('loaderror', (file) => {
            console.error('PreloadScene: Error loading file:', file.key, file.src);
             // Optionally display error to user
         });
    }

     createLoadingBar() {
        const centerX = this.cameras.main.width / 2;
        const centerY = this.cameras.main.height / 2;

        this.loadingText = this.add.text(centerX, centerY - 50, 'Loading...', {
            font: '24px Arial',
            fill: '#ffffff'
        }).setOrigin(0.5);

        // Background of the loading bar
        this.loadingBg = this.add.image(centerX, centerY, 'loader-bg').setOrigin(0.5);

        // Filling part of the loading bar
        this.loadingFill = this.add.image(centerX - this.loadingBg.width / 2 + 4, centerY, 'loader-fill').setOrigin(0, 0.5); // Align left edge
        this.loadingFill.setCrop(0, 0, 0, this.loadingFill.height); // Initially crop to zero width


        this.percentText = this.add.text(centerX, centerY + 50, '0%', {
            font: '18px Arial',
            fill: '#ffffff'
        }).setOrigin(0.5);
    }

    updateLoadingBar(value) {
        if (this.loadingFill) {
            const fillWidth = (this.loadingBg.width - 8) * value; // Calculate width based on progress (-8 for padding)
            this.loadingFill.setCrop(0, 0, fillWidth, this.loadingFill.height);
        }
        if (this.percentText) {
            this.percentText.setText(parseInt(value * 100) + '%');
        }
    }

    create() {
        // This scene transitions immediately after preload is complete
        console.log('PreloadScene: Create (should transition immediately)');
    }
}

