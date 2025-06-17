import Phaser from 'phaser';
import AssetPreloader from '../../phaser/utils/AssetPreloader';

export default class PokerPreloadScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PokerPreloadScene' });
        this.assetPreloader = new AssetPreloader();
    }

    preload() {
        console.log('PokerPreloadScene: Loading poker assets');
        
        // Create loading screen
        this.createLoadingScreen();
        
        // Load poker-specific assets
        this.loadPokerAssets();
        
        // Update loading progress
        this.load.on('progress', (progress) => {
            this.updateLoadingProgress(progress);
        });
        
        this.load.on('complete', () => {
            console.log('PokerPreloadScene: Assets loaded');
            this.time.delayedCall(500, () => {
                this.scene.start('PokerGameScene');
                this.scene.start('PokerUIScene');
            });
        });
    }

    createLoadingScreen() {
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        // Background
        this.add.rectangle(centerX, centerY, 800, 600, 0x0d4016);
        
        // Title
        this.add.text(centerX, centerY - 100, 'TEXAS HOLD\'EM POKER', {
            fontSize: '36px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Loading text
        this.loadingText = this.add.text(centerX, centerY + 50, 'Loading...', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFFFFF'
        }).setOrigin(0.5);
        
        // Progress bar background
        this.progressBg = this.add.rectangle(centerX, centerY + 100, 400, 20, 0x333333);
        
        // Progress bar fill
        this.progressFill = this.add.rectangle(centerX - 200, centerY + 100, 0, 16, 0xFFD700)
            .setOrigin(0, 0.5);
    }

    updateLoadingProgress(progress) {
        const percentage = Math.round(progress * 100);
        this.loadingText.setText(`Loading... ${percentage}%`);
        this.progressFill.width = 400 * progress;
    }

    loadPokerAssets() {
        // Generate playing cards if not already present
        this.assetPreloader.generatePlayingCards(this);
        
        // Generate poker chips
        this.assetPreloader.generatePokerChips(this);
        
        // Generate UI elements
        this.generateActionButtons();
        this.generateBetSlider();
        this.generatePlayerPanels();
        
        // Load sound assets
        this.loadSoundAssets();
        
        // Generate particle textures
        this.assetPreloader.generateParticleTextures(this);
    }

    generateActionButtons() {
        const buttonConfigs = [
            { key: 'fold-btn', color: 0xff4444, text: 'FOLD' },
            { key: 'check-btn', color: 0x44aa44, text: 'CHECK' },
            { key: 'call-btn', color: 0x44aa44, text: 'CALL' },
            { key: 'bet-btn', color: 0x4444ff, text: 'BET' },
            { key: 'raise-btn', color: 0x4444ff, text: 'RAISE' },
            { key: 'allin-btn', color: 0xff8800, text: 'ALL-IN' }
        ];

        buttonConfigs.forEach(config => {
            const graphics = this.add.graphics();
            
            // Button background
            graphics.fillStyle(config.color);
            graphics.fillRoundedRect(0, 0, 120, 40, 8);
            
            // Button border
            graphics.lineStyle(2, 0xffffff);
            graphics.strokeRoundedRect(0, 0, 120, 40, 8);
            
            // Highlight effect
            graphics.fillStyle(0xffffff, 0.2);
            graphics.fillRoundedRect(2, 2, 116, 36, 6);
            
            graphics.generateTexture(config.key, 120, 40);
            graphics.destroy();
        });
    }

    generateBetSlider() {
        const graphics = this.add.graphics();
        
        // Slider track
        graphics.fillStyle(0x333333);
        graphics.fillRoundedRect(0, 15, 200, 10, 5);
        
        // Slider thumb
        graphics.fillStyle(0xFFD700);
        graphics.fillCircle(10, 20, 12);
        graphics.lineStyle(2, 0x000000);
        graphics.strokeCircle(10, 20, 12);
        
        graphics.generateTexture('bet-slider', 220, 40);
        graphics.destroy();
    }

    generatePlayerPanels() {
        const graphics = this.add.graphics();
        
        // Player info panel
        graphics.fillStyle(0x2a2a2a, 0.9);
        graphics.fillRoundedRect(0, 0, 150, 80, 8);
        graphics.lineStyle(2, 0x666666);
        graphics.strokeRoundedRect(0, 0, 150, 80, 8);
        
        // Active player highlight
        graphics.lineStyle(3, 0xFFD700);
        graphics.strokeRoundedRect(1, 1, 148, 78, 8);
        
        graphics.generateTexture('player-panel', 150, 80);
        
        graphics.clear();
        
        // Active player panel (highlighted)
        graphics.fillStyle(0x3a4a3a, 0.9);
        graphics.fillRoundedRect(0, 0, 150, 80, 8);
        graphics.lineStyle(3, 0x00ff00);
        graphics.strokeRoundedRect(0, 0, 150, 80, 8);
        
        graphics.generateTexture('player-panel-active', 150, 80);
        graphics.destroy();
    }

    loadSoundAssets() {
        // For now, we'll use placeholder sounds or generate simple tones
        // In a real implementation, you'd load actual audio files
        
        // Create simple audio buffers for poker sounds
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        // Generate simple card deal sound
        this.generateCardDealSound(audioContext);
        
        // Generate chip sounds
        this.generateChipSounds(audioContext);
    }

    generateCardDealSound(audioContext) {
        // Simple card deal sound - quick "snap" effect
        const buffer = audioContext.createBuffer(1, audioContext.sampleRate * 0.1, audioContext.sampleRate);
        const data = buffer.getChannelData(0);
        
        for (let i = 0; i < data.length; i++) {
            data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3) * 0.3;
        }
        
        // Store as base64 data URL for Phaser
        // This is a simplified approach - in production you'd use actual audio files
    }

    generateChipSounds(audioContext) {
        // Simple chip sound - multiple short clicks
        const buffer = audioContext.createBuffer(1, audioContext.sampleRate * 0.2, audioContext.sampleRate);
        const data = buffer.getChannelData(0);
        
        for (let i = 0; i < data.length; i++) {
            const t = i / audioContext.sampleRate;
            data[i] = Math.sin(2 * Math.PI * 800 * t) * Math.exp(-t * 20) * 0.3;
        }
    }
}
