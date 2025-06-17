import Phaser from 'phaser';
import UniversalBootScene from '../../phaser/utils/UniversalBootScene';

export default class PokerBootScene extends UniversalBootScene {
    constructor() {
        super({ key: 'PokerBootScene' });
        this.gameType = 'poker';
    }

    create() {
        console.log('PokerBootScene: Starting boot sequence');
        super.create();
        
        // Poker-specific boot setup
        this.setupPokerConfiguration();
        
        // Generate poker-specific assets
        this.generatePokerAssets();
        
        // Start preload scene
        this.time.delayedCall(1000, () => {
            this.scene.start('PokerPreloadScene');
        });
    }

    setupPokerConfiguration() {
        // Store poker-specific configuration
        this.registry.set('gameType', 'poker');
        this.registry.set('tableType', 'cash');
        this.registry.set('maxPlayers', 9);
        
        // Set poker game rules
        this.registry.set('gameRules', {
            maxRaises: 3,
            minRaise: 'bigBlind',
            autoMuck: true,
            showMuckCards: false,
            allInProtection: true
        });
        
        console.log('PokerBootScene: Poker configuration loaded');
    }

    generatePokerAssets() {
        // Generate poker table
        this.generatePokerTable();
        
        // Generate dealer button
        this.generateDealerButton();
        
        // Generate seat indicators
        this.generateSeatIndicators();
        
        // Generate pot display
        this.generatePotDisplay();
        
        console.log('PokerBootScene: Poker assets generated');
    }

    generatePokerTable() {
        const graphics = this.add.graphics();
        
        // Main table (oval shape)
        graphics.fillStyle(0x0d4016);
        graphics.fillEllipse(400, 300, 600, 350);
        
        // Table border
        graphics.lineStyle(8, 0x8B4513);
        graphics.strokeEllipse(400, 300, 600, 350);
        
        // Inner felt area
        graphics.lineStyle(3, 0x228B22);
        graphics.strokeEllipse(400, 300, 580, 330);
        
        // Community card area
        graphics.fillStyle(0x228B22);
        graphics.fillRoundedRect(250, 250, 300, 100, 10);
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRoundedRect(250, 250, 300, 100, 10);
        
        graphics.generateTexture('poker-table', 800, 600);
        graphics.destroy();
    }

    generateDealerButton() {
        const graphics = this.add.graphics();
        
        // Button background
        graphics.fillStyle(0xFFD700);
        graphics.fillCircle(20, 20, 18);
        graphics.lineStyle(2, 0x000000);
        graphics.strokeCircle(20, 20, 18);
        
        // 'D' text will be added separately
        graphics.generateTexture('dealer-button', 40, 40);
        graphics.destroy();
    }

    generateSeatIndicators() {
        const graphics = this.add.graphics();
        
        // Empty seat
        graphics.fillStyle(0x333333, 0.7);
        graphics.fillCircle(50, 50, 45);
        graphics.lineStyle(3, 0x666666);
        graphics.strokeCircle(50, 50, 45);
        graphics.generateTexture('empty-seat', 100, 100);
        
        graphics.clear();
        
        // Occupied seat
        graphics.fillStyle(0x4a4a4a, 0.9);
        graphics.fillCircle(50, 50, 45);
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeCircle(50, 50, 45);
        graphics.generateTexture('occupied-seat', 100, 100);
        
        graphics.destroy();
    }

    generatePotDisplay() {
        const graphics = this.add.graphics();
        
        // Pot area background
        graphics.fillStyle(0x2a5a2a, 0.8);
        graphics.fillRoundedRect(0, 0, 150, 60, 10);
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRoundedRect(0, 0, 150, 60, 10);
        
        graphics.generateTexture('pot-display', 150, 60);
        graphics.destroy();
    }
}
