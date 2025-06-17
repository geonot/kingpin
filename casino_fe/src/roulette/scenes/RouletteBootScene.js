import Phaser from 'phaser';

export default class RouletteBootScene extends Phaser.Scene {
    constructor() {
        super({ key: 'RouletteBootScene' });
    }

    preload() {
        // Load minimal assets for boot screen
        this.createBootGraphics();
    }

    create() {
        console.log('RouletteBootScene: Starting boot sequence');
        
        // Get configuration from registry
        const gameConfig = this.sys.game.config.gameConfig || {};
        this.registry.set('gameConfig', gameConfig);
        
        // Set up event bus if provided
        const eventBus = this.registry.get('eventBus');
        if (eventBus) {
            this.eventBus = eventBus;
        }
        
        // Create boot screen UI
        this.createBootScreen();
        
        // Auto-advance to preload after a short delay
        this.time.delayedCall(1000, () => {
            this.scene.start('RoulettePreloadScene');
        });
    }

    createBootGraphics() {
        // Create simple graphics for boot screen
        this.load.image('roulette-logo', 'data:image/svg+xml;base64,' + btoa(`
            <svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="40" fill="#8B0000" stroke="#FFD700" stroke-width="3"/>
                <circle cx="50" cy="50" r="30" fill="none" stroke="#FFD700" stroke-width="2"/>
                <text x="110" y="35" font-family="Arial" font-size="24" fill="#FFD700" font-weight="bold">ROULETTE</text>
                <text x="110" y="55" font-family="Arial" font-size="14" fill="#FFFFFF">European Style</text>
                <text x="110" y="75" font-family="Arial" font-size="12" fill="#CCCCCC">Place Your Bets</text>
            </svg>
        `));
    }

    createBootScreen() {
        const { width, height } = this.cameras.main;
        
        // Background
        this.add.rectangle(width / 2, height / 2, width, height, 0x0d5016);
        
        // Logo
        const logo = this.add.image(width / 2, height / 2 - 50, 'roulette-logo');
        
        // Loading text
        const loadingText = this.add.text(width / 2, height / 2 + 100, 'Loading Roulette...', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Pulsing animation for loading text
        this.tweens.add({
            targets: loadingText,
            alpha: 0.3,
            duration: 800,
            yoyo: true,
            repeat: -1,
            ease: 'Power2'
        });
        
        // Spinning animation for logo
        this.tweens.add({
            targets: logo,
            rotation: Math.PI * 2,
            duration: 3000,
            repeat: -1,
            ease: 'Linear'
        });
        
        // Version info
        this.add.text(width - 10, height - 10, 'v1.0.0', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#666666'
        }).setOrigin(1, 1);
    }
}
