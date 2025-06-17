import Phaser from 'phaser';

export default class RoulettePreloadScene extends Phaser.Scene {
    constructor() {
        super({ key: 'RoulettePreloadScene' });
    }

    preload() {
        console.log('RoulettePreloadScene: Loading assets');
        
        // Create loading bar
        this.createLoadingBar();
        
        // Load game assets
        this.loadAssets();
        
        // Update loading progress
        this.load.on('progress', this.updateLoadingBar, this);
        this.load.on('complete', this.loadComplete, this);
    }

    create() {
        console.log('RoulettePreloadScene: Assets loaded, starting game');
        
        // Store loaded textures in registry for easy access
        this.setupAssetRegistry();
        
        // Start the main game scene
        this.scene.start('RouletteScene');
    }

    createLoadingBar() {
        const { width, height } = this.cameras.main;
        
        // Background
        this.add.rectangle(width / 2, height / 2, width, height, 0x0d5016);
        
        // Loading bar background
        this.loadingBarBg = this.add.rectangle(width / 2, height / 2 + 50, 400, 20, 0x333333);
        this.loadingBarBg.setStrokeStyle(2, 0xFFD700);
        
        // Loading bar fill
        this.loadingBar = this.add.rectangle(width / 2 - 200, height / 2 + 50, 0, 16, 0xFFD700);
        this.loadingBar.setOrigin(0, 0.5);
        
        // Loading text
        this.loadingText = this.add.text(width / 2, height / 2 - 50, 'Loading Assets...', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Progress percentage
        this.progressText = this.add.text(width / 2, height / 2 + 100, '0%', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFFFFF'
        }).setOrigin(0.5);
    }

    updateLoadingBar(progress) {
        // Update loading bar width
        this.loadingBar.width = 400 * progress;
        
        // Update progress text
        this.progressText.setText(Math.round(progress * 100) + '%');
        
        // Update loading text based on progress
        if (progress < 0.3) {
            this.loadingText.setText('Loading Table Assets...');
        } else if (progress < 0.6) {
            this.loadingText.setText('Loading Wheel Graphics...');
        } else if (progress < 0.9) {
            this.loadingText.setText('Loading Sound Effects...');
        } else {
            this.loadingText.setText('Almost Ready...');
        }
    }

    loadComplete() {
        this.loadingText.setText('Ready!');
        
        // Flash effect
        this.tweens.add({
            targets: this.loadingBar,
            alpha: 0.3,
            duration: 200,
            yoyo: true,
            repeat: 2
        });
    }

    loadAssets() {
        // Generate textures for game elements since we don't have asset files
        this.generateGameTextures();
        
        // Load any actual image files if they exist
        this.loadImageAssets();
        
        // Generate audio if needed
        this.generateAudioAssets();
    }

    generateGameTextures() {
        // Roulette wheel segments
        for (let i = 0; i < 37; i++) {
            const isRed = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36].includes(i);
            const isBlack = !isRed && i !== 0;
            const color = i === 0 ? 0x00AA00 : (isRed ? 0xAA0000 : 0x000000);
            
            this.generateWheelSegment(`wheel-segment-${i}`, color, i);
        }
        
        // Chips
        [1, 5, 25, 100, 500].forEach(value => {
            this.generateChip(`chip-${value}`, this.getChipColor(value), value);
        });
        
        // Ball
        this.generateBall('roulette-ball');
        
        // Table elements
        this.generateTableElements();
        
        // UI elements
        this.generateUIElements();
    }

    generateWheelSegment(key, color, number) {
        const graphics = this.add.graphics();
        
        // Segment background
        graphics.fillStyle(color);
        graphics.beginPath();
        graphics.arc(0, 0, 100, 0, Math.PI / 18.5, false);
        graphics.lineTo(0, 0);
        graphics.closePath();
        graphics.fillPath();
        
        // Segment border
        graphics.lineStyle(1, 0xFFD700);
        graphics.strokePath();
        
        // Generate texture
        graphics.generateTexture(key, 120, 120);
        graphics.destroy();
    }

    generateChip(key, color, value) {
        const graphics = this.add.graphics();
        
        // Chip base
        graphics.fillStyle(color);
        graphics.fillCircle(25, 25, 22);
        
        // Chip border
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeCircle(25, 25, 22);
        
        // Inner ring
        graphics.lineStyle(1, 0xFFFFFF);
        graphics.strokeCircle(25, 25, 18);
        
        // Generate texture
        graphics.generateTexture(key, 50, 50);
        graphics.destroy();
        
        // Add value text as separate texture
        const text = this.add.text(25, 25, value.toString(), {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: value === 500 ? '#FFFFFF' : '#000000',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        text.generateTexture(`${key}-text`, 50, 50);
        text.destroy();
    }

    generateBall(key) {
        const graphics = this.add.graphics();
        
        // Ball shadow
        graphics.fillStyle(0x000000, 0.3);
        graphics.fillCircle(11, 13, 8);
        
        // Ball
        graphics.fillStyle(0xFFFFFF);
        graphics.fillCircle(10, 10, 8);
        
        // Ball highlight
        graphics.fillStyle(0xFFFFFF, 0.8);
        graphics.fillCircle(8, 8, 3);
        
        graphics.generateTexture(key, 20, 20);
        graphics.destroy();
    }

    generateTableElements() {
        // Number cells
        for (let i = 0; i <= 36; i++) {
            this.generateNumberCell(`number-${i}`, i);
        }
        
        // Outside bet areas
        this.generateOutsideBetAreas();
    }

    generateNumberCell(key, number) {
        const graphics = this.add.graphics();
        const isRed = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36].includes(number);
        const isBlack = !isRed && number !== 0;
        const color = number === 0 ? 0x00AA00 : (isRed ? 0xAA0000 : 0x000000);
        
        // Cell background
        graphics.fillStyle(color);
        graphics.fillRect(0, 0, 40, 60);
        
        // Cell border
        graphics.lineStyle(1, 0xFFFFFF);
        graphics.strokeRect(0, 0, 40, 60);
        
        graphics.generateTexture(key, 40, 60);
        graphics.destroy();
        
        // Number text
        const text = this.add.text(20, 30, number.toString(), {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        text.generateTexture(`${key}-text`, 40, 60);
        text.destroy();
    }

    generateOutsideBetAreas() {
        const areas = [
            { key: 'bet-red', color: 0xAA0000, text: 'RED' },
            { key: 'bet-black', color: 0x000000, text: 'BLACK' },
            { key: 'bet-even', color: 0x555555, text: 'EVEN' },
            { key: 'bet-odd', color: 0x555555, text: 'ODD' },
            { key: 'bet-low', color: 0x555555, text: '1-18' },
            { key: 'bet-high', color: 0x555555, text: '19-36' },
            { key: 'bet-1st12', color: 0x555555, text: '1st 12' },
            { key: 'bet-2nd12', color: 0x555555, text: '2nd 12' },
            { key: 'bet-3rd12', color: 0x555555, text: '3rd 12' }
        ];
        
        areas.forEach(area => {
            const graphics = this.add.graphics();
            graphics.fillStyle(area.color);
            graphics.fillRect(0, 0, 80, 40);
            graphics.lineStyle(1, 0xFFFFFF);
            graphics.strokeRect(0, 0, 80, 40);
            graphics.generateTexture(area.key, 80, 40);
            graphics.destroy();
            
            const text = this.add.text(40, 20, area.text, {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            text.generateTexture(`${area.key}-text`, 80, 40);
            text.destroy();
        });
    }

    generateUIElements() {
        // Control buttons
        const buttons = [
            { key: 'btn-spin', color: 0x4CAF50, text: 'SPIN' },
            { key: 'btn-clear', color: 0xF44336, text: 'CLEAR' },
            { key: 'btn-double', color: 0xFF9800, text: 'DOUBLE' },
            { key: 'btn-rebet', color: 0x2196F3, text: 'REBET' }
        ];
        
        buttons.forEach(button => {
            const graphics = this.add.graphics();
            graphics.fillStyle(button.color);
            graphics.fillRoundedRect(0, 0, 80, 35, 5);
            graphics.lineStyle(2, 0xFFFFFF);
            graphics.strokeRoundedRect(0, 0, 80, 35, 5);
            graphics.generateTexture(button.key, 80, 35);
            graphics.destroy();
            
            const text = this.add.text(40, 17, button.text, {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            text.generateTexture(`${button.key}-text`, 80, 35);
            text.destroy();
        });
    }

    loadImageAssets() {
        // Load actual image assets if they exist
        // For now, we'll use generated textures
        
        // Example:
        // this.load.image('roulette-wheel', 'assets/images/roulette/wheel.png');
        // this.load.image('roulette-table', 'assets/images/roulette/table.png');
    }

    generateAudioAssets() {
        // Generate simple audio tones for sound effects
        // In a real implementation, you'd load actual audio files
        
        // Example:
        // this.load.audio('wheel-spin', 'assets/audio/roulette/wheel_spin.mp3');
        // this.load.audio('ball-roll', 'assets/audio/roulette/ball_roll.mp3');
    }

    setupAssetRegistry() {
        // Store commonly used textures in registry for easy access
        const gameConfig = this.registry.get('gameConfig') || {};
        
        this.registry.set('wheelSegments', Array.from({length: 37}, (_, i) => `wheel-segment-${i}`));
        this.registry.set('chipTextures', [1, 5, 25, 100, 500].map(v => `chip-${v}`));
        this.registry.set('numberTextures', Array.from({length: 37}, (_, i) => `number-${i}`));
    }

    getChipColor(value) {
        const colors = {
            1: 0xFFFFFF,    // White
            5: 0xFF4444,    // Red
            25: 0x44AA44,   // Green
            100: 0x4444FF,  // Blue
            500: 0x000000   // Black
        };
        return colors[value] || 0x808080;
    }
}
