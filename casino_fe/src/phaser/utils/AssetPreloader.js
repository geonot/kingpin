import Phaser from 'phaser';

export default class AssetPreloader {
    constructor(scene) {
        this.scene = scene;
        this.gameType = scene.registry.get('gameType') || 'generic';
        this.assetQueue = [];
        this.generatedAssets = new Map();
    }

    // Main method to load all assets for a game
    loadGameAssets() {
        console.log(`AssetPreloader: Loading assets for ${this.gameType}`);
        
        this.loadUniversalAssets();
        this.loadGameSpecificAssets();
        this.loadAudioAssets();
        this.processAssetQueue();
    }

    loadUniversalAssets() {
        // Playing cards (standard 52-card deck)
        this.generatePlayingCards();
        
        // Casino chips
        this.generateCasinoChips();
        
        // UI elements
        this.generateUIElements();
        
        // Particle effects
        this.generateParticleTextures();
        
        // Table backgrounds
        this.generateTableBackgrounds();
    }

    generatePlayingCards() {
        const suits = [
            { name: 'hearts', symbol: '♥', color: '#FF0000' },
            { name: 'diamonds', symbol: '♦', color: '#FF0000' },
            { name: 'clubs', symbol: '♣', color: '#000000' },
            { name: 'spades', symbol: '♠', color: '#000000' }
        ];
        
        const ranks = [
            { name: 'A', display: 'A' },
            { name: '2', display: '2' },
            { name: '3', display: '3' },
            { name: '4', display: '4' },
            { name: '5', display: '5' },
            { name: '6', display: '6' },
            { name: '7', display: '7' },
            { name: '8', display: '8' },
            { name: '9', display: '9' },
            { name: '10', display: '10' },
            { name: 'J', display: 'J' },
            { name: 'Q', display: 'Q' },
            { name: 'K', display: 'K' }
        ];

        // Generate card back
        this.generateCardBack();

        // Generate each card
        suits.forEach(suit => {
            ranks.forEach(rank => {
                const cardKey = `card-${rank.name}${suit.name.charAt(0).toUpperCase()}`;
                this.generateSingleCard(cardKey, {
                    rank: rank.display,
                    suit: suit.symbol,
                    color: suit.color,
                    suitName: suit.name
                });
            });
        });
    }

    generateSingleCard(key, cardData) {
        const graphics = this.scene.add.graphics();
        const width = 70;
        const height = 100;
        
        // Card background
        graphics.fillStyle(0xFFFFF0);
        graphics.fillRoundedRect(0, 0, width, height, 6);
        
        // Card border
        graphics.lineStyle(1, 0x000000);
        graphics.strokeRoundedRect(0, 0, width, height, 6);
        
        // Corner decorations
        graphics.lineStyle(1, 0xDDDDDD);
        graphics.strokeRoundedRect(2, 2, width - 4, height - 4, 4);
        
        graphics.generateTexture(key, width, height);
        graphics.destroy();
        
        // Add rank and suit text
        const text = this.scene.add.text(width/2, height/2, `${cardData.rank}\n${cardData.suit}`, {
            fontSize: cardData.rank === '10' ? '14px' : '16px',
            fontFamily: 'Arial',
            fill: cardData.color,
            fontStyle: 'bold',
            align: 'center'
        }).setOrigin(0.5);
        
        text.generateTexture(`${key}-content`, width, height);
        text.destroy();
        
        // Store card info for later use
        this.generatedAssets.set(key, {
            type: 'card',
            data: cardData,
            width,
            height
        });
    }

    generateCardBack() {
        const graphics = this.scene.add.graphics();
        const width = 70;
        const height = 100;
        
        // Base color
        graphics.fillStyle(0x000080);
        graphics.fillRoundedRect(0, 0, width, height, 6);
        
        // Decorative pattern
        graphics.fillStyle(0xFFD700);
        for (let i = 1; i < 6; i++) {
            for (let j = 1; j < 8; j++) {
                if ((i + j) % 2 === 0) {
                    graphics.fillRect(i * 10, j * 10, 8, 8);
                }
            }
        }
        
        // Border
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRoundedRect(0, 0, width, height, 6);
        
        graphics.generateTexture('card-back', width, height);
        graphics.destroy();
    }

    generateCasinoChips() {
        const chipConfigs = [
            { value: 1, color: 0xFFFFFF, textColor: '#000000' },
            { value: 5, color: 0xFF4444, textColor: '#FFFFFF' },
            { value: 25, color: 0x44AA44, textColor: '#FFFFFF' },
            { value: 100, color: 0x4444FF, textColor: '#FFFFFF' },
            { value: 500, color: 0x800080, textColor: '#FFFFFF' },
            { value: 1000, color: 0x000000, textColor: '#FFD700' },
            { value: 5000, color: 0xFF8800, textColor: '#000000' }
        ];

        chipConfigs.forEach(config => {
            this.generateChip(config.value, config.color, config.textColor);
        });
    }

    generateChip(value, color, textColor) {
        const graphics = this.scene.add.graphics();
        const radius = 20;
        
        // Main chip body
        graphics.fillStyle(color);
        graphics.fillCircle(radius, radius, radius - 2);
        
        // Outer ring
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeCircle(radius, radius, radius - 2);
        
        // Inner ring
        graphics.lineStyle(1, 0xFFFFFF, 0.7);
        graphics.strokeCircle(radius, radius, radius - 6);
        
        // Dot pattern around edge
        for (let i = 0; i < 8; i++) {
            const angle = (i / 8) * Math.PI * 2;
            const x = radius + Math.cos(angle) * (radius - 4);
            const y = radius + Math.sin(angle) * (radius - 4);
            graphics.fillStyle(0xFFFFFF);
            graphics.fillCircle(x, y, 1);
        }
        
        graphics.generateTexture(`chip-${value}`, radius * 2, radius * 2);
        graphics.destroy();
        
        // Value text
        const text = this.scene.add.text(radius, radius, value.toString(), {
            fontSize: value >= 1000 ? '10px' : '12px',
            fontFamily: 'Arial',
            fill: textColor,
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        text.generateTexture(`chip-${value}-text`, radius * 2, radius * 2);
        text.destroy();
    }

    generateUIElements() {
        // Generate various UI buttons and elements
        const buttons = [
            { key: 'btn-deal', text: 'DEAL', color: 0x4CAF50, width: 80, height: 35 },
            { key: 'btn-hit', text: 'HIT', color: 0x2196F3, width: 80, height: 35 },
            { key: 'btn-stand', text: 'STAND', color: 0xFF9800, width: 80, height: 35 },
            { key: 'btn-double', text: 'DOUBLE', color: 0x9C27B0, width: 80, height: 35 },
            { key: 'btn-split', text: 'SPLIT', color: 0x607D8B, width: 80, height: 35 },
            { key: 'btn-fold', text: 'FOLD', color: 0xF44336, width: 80, height: 35 },
            { key: 'btn-call', text: 'CALL', color: 0x4CAF50, width: 80, height: 35 },
            { key: 'btn-raise', text: 'RAISE', color: 0xFF5722, width: 80, height: 35 },
            { key: 'btn-bet', text: 'BET', color: 0x3F51B5, width: 80, height: 35 },
            { key: 'btn-check', text: 'CHECK', color: 0x009688, width: 80, height: 35 },
            { key: 'btn-spin', text: 'SPIN', color: 0xE91E63, width: 100, height: 40 },
            { key: 'btn-clear', text: 'CLEAR', color: 0x795548, width: 80, height: 35 },
            { key: 'btn-max-bet', text: 'MAX BET', color: 0xFF6F00, width: 90, height: 35 }
        ];

        buttons.forEach(btn => {
            this.generateButton(btn.key, btn.text, btn.color, btn.width, btn.height);
        });

        // Generate other UI elements
        this.generateChipStack();
        this.generateBettingArea();
        this.generatePlayerInfo();
    }

    generateButton(key, text, color, width, height) {
        const graphics = this.scene.add.graphics();
        
        // Button background with gradient effect
        graphics.fillGradientStyle(color, color, color * 0.8, color * 0.8);
        graphics.fillRoundedRect(0, 0, width, height, 8);
        
        // Button border
        graphics.lineStyle(2, 0xFFFFFF, 0.8);
        graphics.strokeRoundedRect(0, 0, width, height, 8);
        
        // Inner highlight
        graphics.lineStyle(1, 0xFFFFFF, 0.3);
        graphics.strokeRoundedRect(2, 2, width - 4, height - 4, 6);
        
        graphics.generateTexture(key, width, height);
        graphics.destroy();
        
        // Button text
        const buttonText = this.scene.add.text(width/2, height/2, text, {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        buttonText.generateTexture(`${key}-text`, width, height);
        buttonText.destroy();
    }

    generateChipStack() {
        const graphics = this.scene.add.graphics();
        
        // Draw a stack of chips
        for (let i = 0; i < 5; i++) {
            const y = 30 - i * 3;
            graphics.fillStyle(0x444444);
            graphics.fillEllipse(15, y, 30, 8);
            graphics.fillStyle(0x666666);
            graphics.fillEllipse(15, y - 1, 30, 8);
        }
        
        graphics.generateTexture('chip-stack', 30, 35);
        graphics.destroy();
    }

    generateBettingArea() {
        const graphics = this.scene.add.graphics();
        
        // Betting circle
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeCircle(50, 50, 40);
        
        // Inner circle
        graphics.lineStyle(1, 0xFFFFFF, 0.5);
        graphics.strokeCircle(50, 50, 35);
        
        graphics.generateTexture('betting-area', 100, 100);
        graphics.destroy();
    }

    generatePlayerInfo() {
        const graphics = this.scene.add.graphics();
        
        // Player info panel background
        graphics.fillStyle(0x000000, 0.7);
        graphics.fillRoundedRect(0, 0, 200, 60, 8);
        
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRoundedRect(0, 0, 200, 60, 8);
        
        graphics.generateTexture('player-info-panel', 200, 60);
        graphics.destroy();
    }

    generateParticleTextures() {
        // Star particle for celebrations
        this.generateStarParticle();
        
        // Chip particle for betting effects
        this.generateChipParticle();
        
        // Sparkle particle for wins
        this.generateSparkleParticle();
        
        // Smoke particle for card effects
        this.generateSmokeParticle();
    }

    generateStarParticle() {
        const graphics = this.scene.add.graphics();
        
        graphics.fillStyle(0xFFD700);
        graphics.beginPath();
        
        // 5-pointed star
        for (let i = 0; i < 5; i++) {
            const angle = (i * 144 - 90) * Math.PI / 180;
            const x = 8 + Math.cos(angle) * 6;
            const y = 8 + Math.sin(angle) * 6;
            
            if (i === 0) graphics.moveTo(x, y);
            else graphics.lineTo(x, y);
            
            const innerAngle = ((i * 144 + 72) - 90) * Math.PI / 180;
            const innerX = 8 + Math.cos(innerAngle) * 3;
            const innerY = 8 + Math.sin(innerAngle) * 3;
            graphics.lineTo(innerX, innerY);
        }
        
        graphics.closePath();
        graphics.fillPath();
        
        graphics.generateTexture('star-particle', 16, 16);
        graphics.destroy();
    }

    generateChipParticle() {
        const graphics = this.scene.add.graphics();
        
        graphics.fillStyle(0xFFD700);
        graphics.fillCircle(4, 4, 3);
        
        graphics.lineStyle(1, 0xFFFFFF);
        graphics.strokeCircle(4, 4, 3);
        
        graphics.generateTexture('chip-particle', 8, 8);
        graphics.destroy();
    }

    generateSparkleParticle() {
        const graphics = this.scene.add.graphics();
        
        graphics.fillStyle(0xFFFFFF);
        graphics.fillRect(3, 0, 2, 8);
        graphics.fillRect(0, 3, 8, 2);
        
        graphics.generateTexture('sparkle-particle', 8, 8);
        graphics.destroy();
    }

    generateSmokeParticle() {
        const graphics = this.scene.add.graphics();
        
        graphics.fillStyle(0xCCCCCC, 0.6);
        graphics.fillCircle(4, 4, 3);
        
        graphics.generateTexture('smoke-particle', 8, 8);
        graphics.destroy();
    }

    generateTableBackgrounds() {
        // Generate different table surfaces for each game type
        this.generateFeltBackground();
        this.generateWoodBackground();
        this.generateMarbleBackground();
    }

    generateFeltBackground() {
        const graphics = this.scene.add.graphics();
        
        // Green felt texture
        graphics.fillGradientStyle(0x0d5016, 0x0d5016, 0x0a4013, 0x0a4013);
        graphics.fillRect(0, 0, 800, 600);
        
        // Subtle pattern
        graphics.fillStyle(0x0f6018, 0.3);
        for (let i = 0; i < 20; i++) {
            for (let j = 0; j < 15; j++) {
                if ((i + j) % 3 === 0) {
                    graphics.fillRect(i * 40, j * 40, 2, 2);
                }
            }
        }
        
        graphics.generateTexture('felt-background', 800, 600);
        graphics.destroy();
    }

    generateWoodBackground() {
        const graphics = this.scene.add.graphics();
        
        // Wood grain effect
        graphics.fillGradientStyle(0x8B4513, 0x8B4513, 0x654321, 0x654321);
        graphics.fillRect(0, 0, 800, 600);
        
        // Wood lines
        graphics.lineStyle(1, 0x654321, 0.3);
        for (let i = 0; i < 600; i += 20) {
            graphics.moveTo(0, i);
            graphics.lineTo(800, i + 10);
        }
        graphics.strokePath();
        
        graphics.generateTexture('wood-background', 800, 600);
        graphics.destroy();
    }

    generateMarbleBackground() {
        const graphics = this.scene.add.graphics();
        
        // Marble base
        graphics.fillStyle(0xF5F5DC);
        graphics.fillRect(0, 0, 800, 600);
        
        // Marble veining
        graphics.lineStyle(2, 0xD3D3D3, 0.4);
        for (let i = 0; i < 10; i++) {
            graphics.beginPath();
            graphics.moveTo(Math.random() * 800, Math.random() * 600);
            graphics.bezierCurveTo(
                Math.random() * 800, Math.random() * 600,
                Math.random() * 800, Math.random() * 600,
                Math.random() * 800, Math.random() * 600
            );
            graphics.strokePath();
        }
        
        graphics.generateTexture('marble-background', 800, 600);
        graphics.destroy();
    }

    loadGameSpecificAssets() {
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
        // Blackjack-specific elements
        this.generateBlackjackTable();
        this.generateBlackjackUI();
    }

    loadBaccaratAssets() {
        // Baccarat-specific elements
        this.generateBaccaratTable();
        this.generateBaccaratUI();
    }

    loadRouletteAssets() {
        // Roulette-specific elements
        this.generateRouletteWheel();
        this.generateRouletteBall();
        this.generateRouletteTable();
    }

    loadPokerAssets() {
        // Poker-specific elements
        this.generatePokerTable();
        this.generatePokerChips();
        this.generateDealerButton();
    }

    generateBlackjackTable() {
        const graphics = this.scene.add.graphics();
        
        // Table outline
        graphics.fillStyle(0x0d5016);
        graphics.fillRect(0, 0, 800, 600);
        
        // Dealer area
        graphics.fillStyle(0x0a4013);
        graphics.fillRoundedRect(200, 50, 400, 100, 20);
        
        // Player areas
        graphics.fillRoundedRect(150, 400, 150, 120, 15);
        graphics.fillRoundedRect(325, 400, 150, 120, 15);
        graphics.fillRoundedRect(500, 400, 150, 120, 15);
        
        // Table border
        graphics.lineStyle(5, 0xFFD700);
        graphics.strokeRoundedRect(50, 50, 700, 500, 30);
        
        graphics.generateTexture('blackjack-table', 800, 600);
        graphics.destroy();
    }

    generateBaccaratTable() {
        const graphics = this.scene.add.graphics();
        
        graphics.fillStyle(0x0d5016);
        graphics.fillRect(0, 0, 800, 600);
        
        // Player betting area
        graphics.fillStyle(0x0a4013);
        graphics.fillRoundedRect(100, 300, 200, 150, 15);
        
        // Banker betting area
        graphics.fillRoundedRect(500, 300, 200, 150, 15);
        
        // Tie betting area
        graphics.fillRoundedRect(350, 500, 100, 80, 10);
        
        graphics.generateTexture('baccarat-table', 800, 600);
        graphics.destroy();
    }

    // ... Additional generation methods for other game types

    loadAudioAssets() {
        // Note: In a real implementation, you would load actual audio files
        // For now, we'll set up the sound keys that the SoundManager will use
        const audioKeys = [
            'card-deal', 'card-flip', 'card-shuffle',
            'chip-place', 'chip-click', 'chip-stack',
            'wheel-spin', 'ball-roll', 'roulette-win',
            'button-click', 'button-hover',
            'win', 'lose', 'big-win', 'jackpot',
            'ambient-casino'
        ];
        
        // Register audio keys for later use by SoundManager
        this.scene.registry.set('audioKeys', audioKeys);
    }

    processAssetQueue() {
        // Process any queued asset operations
        this.assetQueue.forEach(operation => {
            operation();
        });
        
        this.assetQueue = [];
    }

    // Utility method to get generated asset info
    getAssetInfo(key) {
        return this.generatedAssets.get(key);
    }

    // Cleanup method
    destroy() {
        this.assetQueue = [];
        this.generatedAssets.clear();
    }
}
