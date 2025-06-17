import Phaser from 'phaser';

export default class PokerBootScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PokerBootScene' });
    }

    preload() {
        // Load poker assets
        this.loadPokerAssets();
        
        // Create loading bar
        this.createLoadingBar();
    }

    loadPokerAssets() {
        // Generate card textures if not available
        this.generateCardTextures();
        
        // Generate chip textures
        this.generateChipTextures();
        
        // Generate table texture
        this.generateTableTexture();
        
        // Generate sound assets (placeholders)
        this.generateSoundAssets();
    }

    generateCardTextures() {
        const suits = ['H', 'D', 'C', 'S'];
        const ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'];
        const cardWidth = 60;
        const cardHeight = 84;
        
        suits.forEach(suit => {
            ranks.forEach(rank => {
                const graphics = this.add.graphics();
                
                // Card background
                graphics.fillStyle(0xFFFFFF);
                graphics.fillRoundedRect(0, 0, cardWidth, cardHeight, 8);
                graphics.lineStyle(2, 0x000000);
                graphics.strokeRoundedRect(0, 0, cardWidth, cardHeight, 8);
                
                // Card text
                const isRed = suit === 'H' || suit === 'D';
                const color = isRed ? '#FF0000' : '#000000';
                const suitSymbol = { 'H': '♥', 'D': '♦', 'C': '♣', 'S': '♠' }[suit];
                
                this.add.text(8, 8, rank, {
                    fontSize: '14px',
                    fontFamily: 'Arial',
                    fill: color,
                    fontStyle: 'bold'
                });
                
                this.add.text(8, 25, suitSymbol, {
                    fontSize: '16px',
                    fontFamily: 'Arial',
                    fill: color
                });
                
                this.add.text(cardWidth - 8, cardHeight - 20, rank, {
                    fontSize: '14px',
                    fontFamily: 'Arial',
                    fill: color,
                    fontStyle: 'bold'
                }).setOrigin(1, 0).setRotation(Math.PI);
                
                this.add.text(cardWidth - 8, cardHeight - 37, suitSymbol, {
                    fontSize: '16px',
                    fontFamily: 'Arial',
                    fill: color
                }).setOrigin(1, 0).setRotation(Math.PI);
                
                graphics.generateTexture(`card-${rank}${suit}`, cardWidth, cardHeight);
                graphics.destroy();
            });
        });
        
        // Card back
        const backGraphics = this.add.graphics();
        backGraphics.fillStyle(0x000080);
        backGraphics.fillRoundedRect(0, 0, cardWidth, cardHeight, 8);
        backGraphics.lineStyle(2, 0xFFD700);
        backGraphics.strokeRoundedRect(0, 0, cardWidth, cardHeight, 8);
        
        // Pattern
        backGraphics.lineStyle(1, 0xFFD700);
        for (let i = 0; i < 5; i++) {
            for (let j = 0; j < 7; j++) {
                backGraphics.strokeCircle(12 + i * 10, 12 + j * 10, 3);
            }
        }
        
        backGraphics.generateTexture('card-back', cardWidth, cardHeight);
        backGraphics.destroy();
    }

    generateChipTextures() {
        const chipValues = [25, 100, 500, 1000, 5000];
        const chipColors = [0x008000, 0x000080, 0x800080, 0x8B0000, 0xFF4500];
        
        chipValues.forEach((value, index) => {
            const graphics = this.add.graphics();
            
            // Chip base
            graphics.fillStyle(chipColors[index]);
            graphics.fillCircle(25, 25, 24);
            graphics.lineStyle(3, 0x000000);
            graphics.strokeCircle(25, 25, 24);
            
            // Inner ring
            graphics.lineStyle(2, 0xFFFFFF);
            graphics.strokeCircle(25, 25, 18);
            
            // Value text
            this.add.text(25, 25, value.toString(), {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            graphics.generateTexture(`chip-${value}`, 50, 50);
            graphics.destroy();
        });
    }

    generateTableTexture() {
        const graphics = this.add.graphics();
        
        // Table felt
        graphics.fillStyle(0x0F4A0F);
        graphics.fillEllipse(400, 300, 780, 580);
        
        // Table border
        graphics.lineStyle(8, 0x8B4513);
        graphics.strokeEllipse(400, 300, 780, 580);
        
        // Community card area
        graphics.fillStyle(0x228B22, 0.3);
        graphics.fillRoundedRect(250, 220, 300, 100, 10);
        graphics.lineStyle(2, 0xFFD700);
        graphics.strokeRoundedRect(250, 220, 300, 100, 10);
        
        graphics.generateTexture('poker-table', 800, 600);
        graphics.destroy();
    }

    generateSoundAssets() {
        // Create silent audio contexts for sound placeholders
        // In a real implementation, these would be actual audio files
        const context = this.sound.context;
        if (context) {
            // Placeholder - would load actual sound files
        }
    }

    createLoadingBar() {
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        // Loading text
        this.add.text(centerX, centerY - 50, 'Loading Poker Table...', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Loading bar background
        const barBg = this.add.rectangle(centerX, centerY, 400, 20, 0x333333);
        barBg.setStrokeStyle(2, 0xFFFFFF);
        
        // Loading bar fill
        const barFill = this.add.rectangle(centerX - 200, centerY, 0, 16, 0x00FF00);
        
        // Animate loading
        this.tweens.add({
            targets: barFill,
            width: 400,
            duration: 2000,
            ease: 'Power2',
            onComplete: () => {
                this.scene.start('PokerGameScene');
            }
        });
    }
}
