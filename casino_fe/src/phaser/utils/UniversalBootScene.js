import Phaser from 'phaser';

export default class UniversalBootScene extends Phaser.Scene {
    constructor(key = 'UniversalBootScene') {
        super({ key });
        this.gameType = 'generic';
        this.assets = {
            images: new Map(),
            audio: new Map(),
            textures: new Map()
        };
    }

    init(data) {
        // Detect game type from scene configuration
        this.gameType = this.detectGameType(data);
        console.log(`UniversalBootScene: Initializing for ${this.gameType} game`);
        
        // Set up registry data
        this.setupGameRegistry(data);
    }

    preload() {
        console.log('UniversalBootScene: Loading universal assets');
        
        // Create loading screen
        this.createBootScreen();
        
        // Load universal assets
        this.loadUniversalAssets();
        
        // Load game-specific assets
        this.loadGameSpecificAssets();
        
        // Set up progress tracking
        this.setupProgressTracking();
    }

    create() {
        console.log('UniversalBootScene: Boot complete, proceeding to game');
        
        // Store generated assets in registry
        this.storeAssetsInRegistry();
        
        // Initialize audio system
        this.initializeAudioSystem();
        
        // Set up global event handlers
        this.setupGlobalEvents();
        
        // Proceed to next scene based on game type
        this.proceedToGame();
    }

    detectGameType(data) {
        if (data?.gameType) return data.gameType;
        
        const sceneKey = this.scene.key;
        if (sceneKey.includes('Blackjack')) return 'blackjack';
        if (sceneKey.includes('Baccarat')) return 'baccarat';
        if (sceneKey.includes('Roulette')) return 'roulette';
        if (sceneKey.includes('Poker')) return 'poker';
        
        return 'generic';
    }

    setupGameRegistry(data) {
        const gameConfigs = {
            blackjack: {
                cardWidth: 80,
                cardHeight: 116,
                positions: {
                    dealer: { x: 400, y: 150 },
                    player: [
                        { x: 400, y: 400 },
                        { x: 200, y: 400 },
                        { x: 600, y: 400 }
                    ]
                }
            },
            baccarat: {
                cardWidth: 70,
                cardHeight: 100,
                positions: {
                    player: { x: 300, y: 300 },
                    banker: { x: 500, y: 300 }
                }
            },
            roulette: {
                wheelRadius: 120,
                wheelCenter: { x: 200, y: 200 },
                tablePosition: { x: 500, y: 200 }
            },
            poker: {
                seatPositions: [
                    { x: 400, y: 450 },
                    { x: 200, y: 400 },
                    { x: 100, y: 300 },
                    { x: 150, y: 200 },
                    { x: 300, y: 120 },
                    { x: 500, y: 120 },
                    { x: 650, y: 200 },
                    { x: 700, y: 300 },
                    { x: 600, y: 400 }
                ]
            }
        };

        const config = gameConfigs[this.gameType] || {};
        this.registry.set('gameConfig', { ...config, ...data });
        this.registry.set('gameType', this.gameType);
    }

    createBootScreen() {
        const { width, height } = this.cameras.main;
        
        // Dark green casino background
        this.add.rectangle(width / 2, height / 2, width, height, 0x0d5016);
        
        // Game logo area
        this.createGameLogo();
        
        // Loading bar
        this.createLoadingBar();
        
        // Casino ambiance text
        this.add.text(width / 2, height - 50, 'Kingpin Casino - Premium Gaming Experience', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'italic'
        }).setOrigin(0.5);
    }

    createGameLogo() {
        const { width, height } = this.cameras.main;
        
        const logoConfig = {
            blackjack: { icon: '♠♥', title: 'BLACKJACK', subtitle: 'Beat the Dealer' },
            baccarat: { icon: '♣♦', title: 'BACCARAT', subtitle: 'Player vs Banker' },
            roulette: { icon: '⚫', title: 'ROULETTE', subtitle: 'Spin to Win' },
            poker: { icon: '♠♥♣♦', title: 'POKER', subtitle: 'Texas Hold\'em' },
            generic: { icon: '♠♥♣♦', title: 'CASINO', subtitle: 'Premium Gaming' }
        };

        const config = logoConfig[this.gameType];
        
        // Icon
        this.logoIcon = this.add.text(width / 2, height / 2 - 100, config.icon, {
            fontSize: '64px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Title
        this.logoTitle = this.add.text(width / 2, height / 2 - 20, config.title, {
            fontSize: '32px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold',
            stroke: '#000000',
            strokeThickness: 2
        }).setOrigin(0.5);
        
        // Subtitle
        this.logoSubtitle = this.add.text(width / 2, height / 2 + 20, config.subtitle, {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#CCCCCC',
            fontStyle: 'italic'
        }).setOrigin(0.5);
        
        // Animated glow effect
        this.tweens.add({
            targets: this.logoIcon,
            alpha: 0.7,
            duration: 1500,
            yoyo: true,
            repeat: -1,
            ease: 'Power2'
        });
    }

    createLoadingBar() {
        const { width, height } = this.cameras.main;
        
        // Loading bar background
        this.loadingBg = this.add.rectangle(width / 2, height / 2 + 100, 300, 10, 0x333333);
        this.loadingBg.setStrokeStyle(2, 0xFFD700);
        
        // Loading bar fill
        this.loadingBar = this.add.rectangle(width / 2 - 150, height / 2 + 100, 0, 6, 0xFFD700);
        this.loadingBar.setOrigin(0, 0.5);
        
        // Loading text
        this.loadingText = this.add.text(width / 2, height / 2 + 130, 'Loading...', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF'
        }).setOrigin(0.5);
        
        // Progress percentage
        this.progressText = this.add.text(width / 2, height / 2 + 80, '0%', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFD700'
        }).setOrigin(0.5);
    }

    setupProgressTracking() {
        this.load.on('progress', (progress) => {
            this.updateProgress(progress);
        });
        
        this.load.on('complete', () => {
            this.loadingComplete();
        });
    }

    updateProgress(progress) {
        // Update loading bar
        this.loadingBar.width = 300 * progress;
        this.progressText.setText(Math.round(progress * 100) + '%');
        
        // Update loading text based on progress
        const progressStages = [
            { threshold: 0.2, text: 'Loading table assets...' },
            { threshold: 0.4, text: 'Loading card graphics...' },
            { threshold: 0.6, text: 'Loading sound effects...' },
            { threshold: 0.8, text: 'Initializing game engine...' },
            { threshold: 1.0, text: 'Ready to play!' }
        ];
        
        const stage = progressStages.find(s => progress <= s.threshold);
        if (stage) {
            this.loadingText.setText(stage.text);
        }
    }

    loadingComplete() {
        // Flash effect
        this.tweens.add({
            targets: [this.loadingBar, this.logoIcon],
            alpha: 0.3,
            duration: 200,
            yoyo: true,
            repeat: 2
        });
        
        this.loadingText.setText('Ready!');
    }

    loadUniversalAssets() {
        // Generate universal textures for all games
        this.generateCardTextures();
        this.generateChipTextures();
        this.generateUITextures();
        this.generateParticleTextures();
    }

    generateCardTextures() {
        const suits = ['hearts', 'diamonds', 'clubs', 'spades'];
        const values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
        const suitSymbols = { hearts: '♥', diamonds: '♦', clubs: '♣', spades: '♠' };
        const suitColors = { hearts: '#FF0000', diamonds: '#FF0000', clubs: '#000000', spades: '#000000' };
        
        // Generate card back
        this.generateCardBack();
        
        // Generate individual cards
        suits.forEach(suit => {
            values.forEach(value => {
                this.generateCard(`card-${value}${suit.charAt(0).toUpperCase()}`, {
                    value,
                    suit: suitSymbols[suit],
                    color: suitColors[suit]
                });
            });
        });
    }

    generateCard(key, cardData) {
        const graphics = this.add.graphics();
        
        // Card background
        graphics.fillStyle(0xFFFFFF);
        graphics.fillRoundedRect(0, 0, 80, 116, 8);
        
        // Card border
        graphics.lineStyle(2, 0x000000);
        graphics.strokeRoundedRect(0, 0, 80, 116, 8);
        
        graphics.generateTexture(key, 80, 116);
        graphics.destroy();
        
        // Add card text
        const text = this.add.text(40, 58, `${cardData.value}\n${cardData.suit}`, {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: cardData.color,
            fontStyle: 'bold',
            align: 'center'
        }).setOrigin(0.5);
        
        text.generateTexture(`${key}-text`, 80, 116);
        text.destroy();
    }

    generateCardBack() {
        const graphics = this.add.graphics();
        
        // Card background
        graphics.fillStyle(0x000080);
        graphics.fillRoundedRect(0, 0, 80, 116, 8);
        
        // Pattern
        graphics.fillStyle(0xFFD700);
        for (let i = 0; i < 6; i++) {
            for (let j = 0; j < 8; j++) {
                graphics.fillCircle(10 + i * 12, 10 + j * 12, 2);
            }
        }
        
        // Border
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRoundedRect(0, 0, 80, 116, 8);
        
        graphics.generateTexture('card-back', 80, 116);
        graphics.destroy();
    }

    generateChipTextures() {
        const chipValues = [1, 5, 25, 100, 500, 1000];
        const chipColors = [0xFFFFFF, 0xFF4444, 0x44AA44, 0x4444FF, 0x000000, 0x800080];
        
        chipValues.forEach((value, index) => {
            this.generateChip(`chip-${value}`, chipColors[index], value);
        });
    }

    generateChip(key, color, value) {
        const graphics = this.add.graphics();
        
        // Chip base
        graphics.fillStyle(color);
        graphics.fillCircle(25, 25, 22);
        
        // Chip rim
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeCircle(25, 25, 22);
        
        // Inner circle
        graphics.lineStyle(1, 0xFFFFFF);
        graphics.strokeCircle(25, 25, 18);
        
        graphics.generateTexture(key, 50, 50);
        graphics.destroy();
        
        // Value text
        const text = this.add.text(25, 25, value.toString(), {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: value === 500 || value === 1000 ? '#FFFFFF' : '#000000',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        text.generateTexture(`${key}-text`, 50, 50);
        text.destroy();
    }

    generateUITextures() {
        // Generate button textures
        const buttons = [
            { key: 'btn-deal', color: 0x4CAF50, text: 'DEAL' },
            { key: 'btn-hit', color: 0x2196F3, text: 'HIT' },
            { key: 'btn-stand', color: 0xFF9800, text: 'STAND' },
            { key: 'btn-double', color: 0x9C27B0, text: 'DOUBLE' },
            { key: 'btn-split', color: 0x607D8B, text: 'SPLIT' },
            { key: 'btn-fold', color: 0xF44336, text: 'FOLD' },
            { key: 'btn-call', color: 0x4CAF50, text: 'CALL' },
            { key: 'btn-raise', color: 0xFF5722, text: 'RAISE' },
            { key: 'btn-spin', color: 0x3F51B5, text: 'SPIN' },
            { key: 'btn-clear', color: 0x795548, text: 'CLEAR' }
        ];
        
        buttons.forEach(btn => this.generateButton(btn.key, btn.color, btn.text));
    }

    generateButton(key, color, text) {
        const graphics = this.add.graphics();
        
        graphics.fillStyle(color);
        graphics.fillRoundedRect(0, 0, 100, 40, 8);
        
        graphics.lineStyle(2, 0xFFFFFF);
        graphics.strokeRoundedRect(0, 0, 100, 40, 8);
        
        graphics.generateTexture(key, 100, 40);
        graphics.destroy();
        
        const buttonText = this.add.text(50, 20, text, {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        buttonText.generateTexture(`${key}-text`, 100, 40);
        buttonText.destroy();
    }

    generateParticleTextures() {
        // Star particle for win effects
        const starGraphics = this.add.graphics();
        starGraphics.fillStyle(0xFFD700);
        starGraphics.beginPath();
        starGraphics.moveTo(5, 0);
        starGraphics.lineTo(6, 3);
        starGraphics.lineTo(10, 3);
        starGraphics.lineTo(7, 6);
        starGraphics.lineTo(8, 10);
        starGraphics.lineTo(5, 7);
        starGraphics.lineTo(2, 10);
        starGraphics.lineTo(3, 6);
        starGraphics.lineTo(0, 3);
        starGraphics.lineTo(4, 3);
        starGraphics.closePath();
        starGraphics.fillPath();
        starGraphics.generateTexture('star-particle', 10, 10);
        starGraphics.destroy();
        
        // Chip particle
        const chipGraphics = this.add.graphics();
        chipGraphics.fillStyle(0xFFD700);
        chipGraphics.fillCircle(5, 5, 3);
        chipGraphics.generateTexture('chip-particle', 10, 10);
        chipGraphics.destroy();
    }

    loadGameSpecificAssets() {
        // Load additional assets based on game type
        switch (this.gameType) {
            case 'blackjack':
                this.loadBlackjackAssets();
                break;
            case 'baccarat':
                this.loadBaccaratAssets();
                break;
            case 'roulette':
                this.loadRouletteAssets();
                break;
            case 'poker':
                this.loadPokerAssets();
                break;
        }
    }

    loadBlackjackAssets() {
        // Generate blackjack table
        this.generateBlackjackTable();
    }

    loadBaccaratAssets() {
        // Generate baccarat table
        this.generateBaccaratTable();
    }

    loadRouletteAssets() {
        // Generate roulette wheel and table
        this.generateRouletteWheel();
        this.generateRouletteTable();
    }

    loadPokerAssets() {
        // Generate poker table
        this.generatePokerTable();
    }

    generateBlackjackTable() {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x0d5016);
        graphics.fillRect(0, 0, 800, 600);
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeRoundedRect(50, 50, 700, 500, 20);
        graphics.generateTexture('blackjack-table', 800, 600);
        graphics.destroy();
    }

    generateBaccaratTable() {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x0d5016);
        graphics.fillRect(0, 0, 800, 600);
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRect(100, 200, 200, 150); // Player area
        graphics.strokeRect(500, 200, 200, 150); // Banker area
        graphics.generateTexture('baccarat-table', 800, 600);
        graphics.destroy();
    }

    generateRouletteWheel() {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x8B4513);
        graphics.fillCircle(100, 100, 90);
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeCircle(100, 100, 90);
        graphics.generateTexture('roulette-wheel', 200, 200);
        graphics.destroy();
    }

    generateRouletteTable() {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x0d5016);
        graphics.fillRect(0, 0, 600, 400);
        graphics.lineStyle(1, 0xFFFFFF);
        // Draw betting grid
        for (let i = 0; i <= 12; i++) {
            graphics.moveTo(i * 40, 0);
            graphics.lineTo(i * 40, 180);
        }
        for (let i = 0; i <= 3; i++) {
            graphics.moveTo(0, i * 60);
            graphics.lineTo(480, i * 60);
        }
        graphics.strokePath();
        graphics.generateTexture('roulette-table', 600, 400);
        graphics.destroy();
    }

    generatePokerTable() {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x0d5016);
        graphics.fillEllipse(400, 300, 700, 400);
        graphics.lineStyle(5, 0xFFD700);
        graphics.strokeEllipse(400, 300, 700, 400);
        graphics.generateTexture('poker-table', 800, 600);
        graphics.destroy();
    }

    storeAssetsInRegistry() {
        this.registry.set('universalAssetsLoaded', true);
        this.registry.set('gameEnhancementsEnabled', true);
    }

    initializeAudioSystem() {
        // Enable audio context if needed
        if (this.sound.context && this.sound.context.state === 'suspended') {
            this.sound.context.resume();
        }
        
        this.registry.set('audioEnabled', true);
    }

    setupGlobalEvents() {
        // Set up global event handlers that work across all games
        this.input.on('pointerdown', () => {
            // Resume audio context on first user interaction
            if (this.sound.context && this.sound.context.state === 'suspended') {
                this.sound.context.resume();
            }
        });
    }

    proceedToGame() {
        const nextScenes = {
            blackjack: 'GameScene',
            baccarat: 'GameScene', 
            roulette: 'RouletteScene',
            poker: 'PokerGameScene',
            generic: 'MainMenuScene'
        };
        
        const nextScene = nextScenes[this.gameType] || 'MainMenuScene';
        
        // Smooth transition
        this.cameras.main.fadeOut(500, 0, 0, 0);
        this.cameras.main.once('camerafadeoutcomplete', () => {
            this.scene.start(nextScene);
        });
    }
}
