import Phaser from 'phaser';

const CARD_WIDTH = 70;
const CARD_HEIGHT = 100;

export default class GameScene extends Phaser.Scene {
    constructor() {
        super('GameScene');
        this.eventBus = null;
        this.gameConfig = null;
        this.tableAPIData = null;
        
        // Game objects
        this.tableBackground = null;
        this.playerCardArea = null;
        this.bankerCardArea = null;
        this.playerCards = [];
        this.bankerCards = [];
        this.playerScoreText = null;
        this.bankerScoreText = null;
        this.outcomeText = null;
        this.animationQueue = [];
        this.isAnimating = false;
        
        // Current hand data
        this.currentHandData = null;
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameConfig = this.registry.get('gameDefinition');
        this.tableAPIData = this.registry.get('tableData');
    }

    create() {
        console.log('Baccarat GameScene: create()');
        
        if (!this.eventBus || !this.gameConfig) {
            console.error('Baccarat GameScene: Critical data missing');
            return;
        }

        this.setupTable();
        this.setupCardAreas();
        this.setupEventListeners();
        
        this.eventBus.emit('baccaratGameReady');
        console.log('Baccarat GameScene: Ready');
    }

    setupTable() {
        // Table background
        this.tableBackground = this.add.rectangle(
            this.cameras.main.centerX, 
            this.cameras.main.centerY, 
            this.cameras.main.width, 
            this.cameras.main.height, 
            0x0d5016
        );
        
        // Table areas
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        // Player area
        this.add.rectangle(centerX - 200, centerY + 100, 280, 140, 0x228B22, 0.3)
            .setStrokeStyle(2, 0xFFD700);
        this.add.text(centerX - 200, centerY + 170, 'PLAYER', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Banker area  
        this.add.rectangle(centerX + 200, centerY + 100, 280, 140, 0x228B22, 0.3)
            .setStrokeStyle(2, 0xFFD700);
        this.add.text(centerX + 200, centerY + 170, 'BANKER', {
            fontSize: '18px',
            fontFamily: 'Arial', 
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Title
        this.add.text(centerX, centerY - 200, 'BACCARAT', {
            fontSize: '32px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
    }

    setupCardAreas() {
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        // Score display areas
        this.playerScoreText = this.add.text(centerX - 200, centerY + 50, '', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.bankerScoreText = this.add.text(centerX + 200, centerY + 50, '', {
            fontSize: '24px', 
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Outcome text
        this.outcomeText = this.add.text(centerX, centerY - 100, '', {
            fontSize: '28px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold',
            stroke: '#000000',
            strokeThickness: 2
        }).setOrigin(0.5).setVisible(false);
    }

    setupEventListeners() {
        this.eventBus.on('baccaratHandResult', this.handleHandResult, this);
    }

    handleHandResult(data) {
        if (!data.success || !data.hand) {
            console.error('Baccarat: Invalid hand result data');
            return;
        }
        
        this.currentHandData = data.hand;
        this.clearPreviousHand();
        this.animateHand(data.hand);
    }

    clearPreviousHand() {
        // Clear previous cards
        this.playerCards.forEach(card => card.destroy());
        this.bankerCards.forEach(card => card.destroy());
        this.playerCards = [];
        this.bankerCards = [];
        
        // Clear texts
        this.playerScoreText.setText('');
        this.bankerScoreText.setText('');
        this.outcomeText.setVisible(false);
    }

    animateHand(handData) {
        console.log('Animating baccarat hand:', handData);
        
        // Queue animations
        this.animationQueue = [];
        
        // Deal player cards
        handData.player_cards.forEach((card, index) => {
            this.animationQueue.push({
                type: 'dealCard',
                card: card,
                area: 'player',
                index: index,
                delay: index * 300
            });
        });
        
        // Deal banker cards
        handData.banker_cards.forEach((card, index) => {
            this.animationQueue.push({
                type: 'dealCard', 
                card: card,
                area: 'banker',
                index: index,
                delay: (handData.player_cards.length + index) * 300
            });
        });
        
        // Show scores
        this.animationQueue.push({
            type: 'showScores',
            delay: (handData.player_cards.length + handData.banker_cards.length) * 300 + 500
        });
        
        // Show outcome
        this.animationQueue.push({
            type: 'showOutcome',
            delay: (handData.player_cards.length + handData.banker_cards.length) * 300 + 1000
        });
        
        this.processAnimationQueue();
    }

    processAnimationQueue() {
        if (this.animationQueue.length === 0) {
            this.isAnimating = false;
            return;
        }
        
        this.isAnimating = true;
        const animation = this.animationQueue.shift();
        
        this.time.delayedCall(animation.delay, () => {
            this.executeAnimation(animation);
        });
    }

    executeAnimation(animation) {
        switch (animation.type) {
            case 'dealCard':
                this.dealCardAnimation(animation);
                break;
            case 'showScores':
                this.showScoresAnimation();
                break;
            case 'showOutcome':
                this.showOutcomeAnimation();
                break;
        }
        
        // Continue queue
        this.processAnimationQueue();
    }

    dealCardAnimation(animation) {
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        const isPlayer = animation.area === 'player';
        const targetX = centerX + (isPlayer ? -200 : 200) + (animation.index * 30);
        const targetY = centerY;
        
        // Create card with enhanced styling
        const card = this.add.rectangle(centerX, centerY - 150, CARD_WIDTH, CARD_HEIGHT, 0xFFFFFF)
            .setStrokeStyle(3, 0x000000)
            .setScale(0.1);
        
        // Card text
        const cardText = this.add.text(targetX, targetY, this.formatCard(animation.card), {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: this.getCardColor(animation.card),
            fontStyle: 'bold'
        }).setOrigin(0.5).setVisible(false);
        
        // Enhanced card movement with scale animation
        this.tweens.add({
            targets: card,
            x: targetX,
            y: targetY,
            scale: 1,
            duration: 600,
            ease: 'Back.easeOut',
            onComplete: () => {
                cardText.setVisible(true);
                this.createCardLandEffect(targetX, targetY);
                this.playCardSound();
            }
        });
        
        // Store card references
        if (isPlayer) {
            this.playerCards.push(card);
            this.playerCards.push(cardText);
        } else {
            this.bankerCards.push(card);
            this.bankerCards.push(cardText);
        }
    }

    createCardLandEffect(x, y) {
        // Subtle sparkle effect when card lands
        const sparkles = [];
        for (let i = 0; i < 6; i++) {
            const sparkle = this.add.circle(
                x + Phaser.Math.Between(-20, 20),
                y + Phaser.Math.Between(-20, 20),
                2,
                0xFFD700
            );
            sparkles.push(sparkle);
            
            this.tweens.add({
                targets: sparkle,
                alpha: 0,
                scale: 2,
                duration: 400,
                delay: i * 50,
                onComplete: () => sparkle.destroy()
            });
        }
    }

    showScoresAnimation() {
        if (!this.currentHandData) return;
        
        this.playerScoreText.setText(`Score: ${this.currentHandData.player_score}`);
        this.bankerScoreText.setText(`Score: ${this.currentHandData.banker_score}`);
        
        // Enhanced score appearance with glow effect
        this.tweens.add({
            targets: [this.playerScoreText, this.bankerScoreText],
            alpha: { from: 0, to: 1 },
            scale: { from: 1.8, to: 1 },
            duration: 500,
            ease: 'Back.easeOut'
        });
        
        // Add glow effect to scores
        this.createScoreGlow(this.playerScoreText);
        this.createScoreGlow(this.bankerScoreText);
    }

    createScoreGlow(textObject) {
        const glow = this.add.circle(textObject.x, textObject.y, 40, 0xFFD700, 0.2);
        this.tweens.add({
            targets: glow,
            scale: { from: 0.5, to: 1.5 },
            alpha: { from: 0.3, to: 0 },
            duration: 800,
            onComplete: () => glow.destroy()
        });
    }

    showOutcomeAnimation() {
        if (!this.currentHandData) return;
        
        let outcomeMessage = '';
        let outcomeColor = '#FFD700';
        
        if (this.currentHandData.outcome === 'player') {
            outcomeMessage = 'PLAYER WINS';
            outcomeColor = '#00FF00';
        } else if (this.currentHandData.outcome === 'banker') {
            outcomeMessage = 'BANKER WINS';
            outcomeColor = '#FF4444';
        } else if (this.currentHandData.outcome === 'tie') {
            outcomeMessage = 'TIE';
            outcomeColor = '#FFFF00';
        }
        
        this.outcomeText.setText(outcomeMessage)
            .setFill(outcomeColor)
            .setVisible(true)
            .setAlpha(0)
            .setScale(0.5);
        
        // Enhanced outcome animation with celebration
        this.tweens.add({
            targets: this.outcomeText,
            alpha: 1,
            scale: 1.3,
            duration: 700,
            ease: 'Back.easeOut',
            onComplete: () => {
                // Create win celebration for winning outcomes
                if (this.currentHandData.outcome !== 'tie') {
                    this.createWinCelebration();
                }
                
                // Scale back down
                this.tweens.add({
                    targets: this.outcomeText,
                    scale: 1,
                    duration: 300,
                    ease: 'Power2'
                });
            }
        });
        
        this.playOutcomeSound(this.currentHandData.outcome);
    }

    createWinCelebration() {
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        // Golden particle explosion
        const particles = [];
        for (let i = 0; i < 15; i++) {
            const angle = (i / 15) * Math.PI * 2;
            const distance = 100;
            const x = centerX + Math.cos(angle) * distance;
            const y = centerY + Math.sin(angle) * distance;
            
            const particle = this.add.circle(centerX, centerY - 100, 4, 0xFFD700);
            particles.push(particle);
            
            this.tweens.add({
                targets: particle,
                x: x,
                y: y,
                alpha: 0,
                scale: 2,
                duration: 800,
                delay: i * 30,
                ease: 'Power2',
                onComplete: () => particle.destroy()
            });
        }
        
        // Screen flash effect
        const flash = this.add.rectangle(centerX, centerY, this.cameras.main.width, this.cameras.main.height, 0xFFFFFF, 0.3);
        this.tweens.add({
            targets: flash,
            alpha: 0,
            duration: 200,
            onComplete: () => flash.destroy()
        });
    }

    formatCard(card) {
        // Convert card notation (e.g., "AS", "KH") to display format
        const rank = card[0];
        const suit = card[1];
        
        const suitSymbols = {
            'H': '♥',
            'D': '♦', 
            'C': '♣',
            'S': '♠'
        };
        
        return `${rank}${suitSymbols[suit] || suit}`;
    }

    getCardColor(card) {
        const suit = card[1];
        return (suit === 'H' || suit === 'D') ? '#FF0000' : '#000000';
    }

    playCardSound() {
        if (this.sound.get('dealCard')) {
            this.sound.play('dealCard', { volume: 0.3 });
        }
    }

    playOutcomeSound(outcome) {
        let soundKey = 'push';
        if (outcome === 'player' || outcome === 'banker') {
            soundKey = 'win';
        }
        
        if (this.sound.get(soundKey)) {
            this.sound.play(soundKey, { volume: 0.5 });
        }
    }

    shutdown() {
        if (this.eventBus) {
            this.eventBus.off('baccaratHandResult', this.handleHandResult, this);
        }
    }
}
