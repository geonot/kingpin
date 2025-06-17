// Integration utility for enhancing all casino games with unified features
import SoundManager from './SoundManager';
import GameEnhancer from './GameEnhancer';

export default class CasinoGameIntegrator {
    constructor(scene) {
        this.scene = scene;
        this.soundManager = new SoundManager(scene);
        this.gameEnhancer = new GameEnhancer(scene);
        this.gameType = this.detectGameType();
        
        this.initializeGameSpecificFeatures();
    }

    detectGameType() {
        const sceneKey = this.scene.scene.key;
        if (sceneKey.includes('Blackjack') || sceneKey === 'GameScene') return 'blackjack';
        if (sceneKey.includes('Baccarat')) return 'baccarat';
        if (sceneKey.includes('Roulette')) return 'roulette';
        if (sceneKey.includes('Poker')) return 'poker';
        return 'generic';
    }

    initializeGameSpecificFeatures() {
        switch (this.gameType) {
            case 'blackjack':
                this.setupBlackjackEnhancements();
                break;
            case 'baccarat':
                this.setupBaccaratEnhancements();
                break;
            case 'roulette':
                this.setupRouletteEnhancements();
                break;
            case 'poker':
                this.setupPokerEnhancements();
                break;
            default:
                this.setupGenericEnhancements();
        }
    }

    // Blackjack-specific enhancements
    setupBlackjackEnhancements() {
        // Enhanced card deal animations
        this.originalCardDeal = this.scene.animateCardDeal?.bind(this.scene);
        if (this.scene.animateCardDeal) {
            this.scene.animateCardDeal = this.enhancedCardDeal.bind(this);
        }

        // Enhanced outcome display
        this.originalDisplayOutcome = this.scene.displayRoundOutcome?.bind(this.scene);
        if (this.scene.displayRoundOutcome) {
            this.scene.displayRoundOutcome = this.enhancedBlackjackOutcome.bind(this);
        }
    }

    enhancedCardDeal(cardSprite, finalX, finalY, delay, container) {
        // Add card flip sound
        this.soundManager.playSound('cardDeal', { 
            delay: delay / 1000,
            rate: 0.9 + Math.random() * 0.2 
        });

        // Enhanced animation with particle effect
        const startX = 400; // Center of table
        const startY = 100;
        
        cardSprite.setPosition(startX, startY);
        cardSprite.setScale(0.8);
        cardSprite.setAlpha(0.9);

        this.scene.tweens.add({
            targets: cardSprite,
            x: finalX,
            y: finalY,
            scale: 1,
            alpha: 1,
            duration: 500,
            delay: delay,
            ease: 'Power2',
            onStart: () => {
                // Card trail effect
                this.gameEnhancer.createChipParticles(startX, startY, 2);
            },
            onComplete: () => {
                // Landing effect
                this.gameEnhancer.createChipParticles(finalX, finalY, 1);
                this.scene.tweens.add({
                    targets: cardSprite,
                    scaleY: 1.1,
                    duration: 100,
                    yoyo: true,
                    ease: 'Power2'
                });
            }
        });

        if (this.originalCardDeal) {
            this.originalCardDeal(cardSprite, finalX, finalY, delay, container);
        }
    }

    enhancedBlackjackOutcome(outcomeData) {
        const hasBlackjack = outcomeData.player_hands.some(hand => hand.outcome === 'blackjack');
        const hasWin = outcomeData.player_hands.some(hand => hand.outcome === 'win');
        
        if (hasBlackjack) {
            this.gameEnhancer.flashScreen(0xFFD700, 0.4, 500);
            this.gameEnhancer.shakeScreen(5, 300);
            this.soundManager.playSound('blackjack');
            
            // Fireworks effect
            setTimeout(() => {
                this.gameEnhancer.createWinParticles(400, 300, 'jackpot');
            }, 200);
        } else if (hasWin) {
            this.gameEnhancer.flashScreen(0x4CAF50, 0.2, 300);
            this.soundManager.playSound('win');
            this.gameEnhancer.createWinParticles(400, 300, 'normal');
        } else {
            this.soundManager.playSound('lose');
        }

        if (this.originalDisplayOutcome) {
            this.originalDisplayOutcome(outcomeData);
        }
    }

    // Baccarat-specific enhancements
    setupBaccaratEnhancements() {
        // Enhance card dealing
        if (this.scene.dealCardAnimation) {
            this.originalBaccaratDeal = this.scene.dealCardAnimation.bind(this.scene);
            this.scene.dealCardAnimation = this.enhancedBaccaratDeal.bind(this);
        }

        // Enhance outcome display
        if (this.scene.showOutcomeAnimation) {
            this.originalBaccaratOutcome = this.scene.showOutcomeAnimation.bind(this.scene);
            this.scene.showOutcomeAnimation = this.enhancedBaccaratOutcome.bind(this);
        }
    }

    enhancedBaccaratDeal(animation) {
        const { targetX, targetY, card, isPlayer } = animation;
        
        // Enhanced deal sound
        this.soundManager.playSound('cardDeal', { 
            rate: isPlayer ? 1.0 : 0.9,
            volume: 0.6 
        });

        // Particle trail
        this.gameEnhancer.createChipParticles(400, 200, 3);

        if (this.originalBaccaratDeal) {
            this.originalBaccaratDeal(animation);
        }
    }

    enhancedBaccaratOutcome(outcome) {
        const outcomeEffects = {
            'Player': { color: 0x4CAF50, sound: 'playerWin', particles: 'normal' },
            'Banker': { color: 0x2196F3, sound: 'bankerWin', particles: 'normal' },
            'Tie': { color: 0xFFD700, sound: 'tie', particles: 'big' }
        };

        const effect = outcomeEffects[outcome];
        if (effect) {
            this.gameEnhancer.flashScreen(effect.color, 0.3, 400);
            this.soundManager.playSound(effect.sound);
            this.gameEnhancer.createWinParticles(400, 300, effect.particles);
        }

        if (this.originalBaccaratOutcome) {
            this.originalBaccaratOutcome(outcome);
        }
    }

    // Roulette-specific enhancements
    setupRouletteEnhancements() {
        // Enhance wheel spin
        if (this.scene.startSpin) {
            this.originalStartSpin = this.scene.startSpin.bind(this.scene);
            this.scene.startSpin = this.enhancedRouletteSpin.bind(this);
        }

        // Enhance result display
        if (this.scene.handleSpinResult) {
            this.originalSpinResult = this.scene.handleSpinResult.bind(this.scene);
            this.scene.handleSpinResult = this.enhancedRouletteResult.bind(this);
        }
    }

    enhancedRouletteSpin() {
        // Build-up sound effect
        this.soundManager.playSound('wheelSpin');
        
        // Visual enhancement - screen darkening for focus
        const overlay = this.scene.add.rectangle(
            this.scene.cameras.main.centerX,
            this.scene.cameras.main.centerY,
            this.scene.cameras.main.width,
            this.scene.cameras.main.height,
            0x000000,
            0
        ).setScrollFactor(0);

        this.scene.tweens.add({
            targets: overlay,
            alpha: 0.3,
            duration: 1000,
            onComplete: () => {
                this.scene.tweens.add({
                    targets: overlay,
                    alpha: 0,
                    duration: 2000,
                    onComplete: () => overlay.destroy()
                });
            }
        });

        if (this.originalStartSpin) {
            this.originalStartSpin();
        }
    }

    enhancedRouletteResult() {
        const winnings = this.scene.calculateWinnings ? this.scene.calculateWinnings() : 0;
        
        // Ball landing sound
        this.soundManager.playSound('ballRoll');
        
        // Result announcement
        setTimeout(() => {
            if (winnings > 0) {
                const winLevel = winnings > 1000 ? 'jackpot' : winnings > 100 ? 'big' : 'normal';
                this.gameEnhancer.createWinParticles(200, 150, winLevel);
                this.soundManager.playSound('win');
                
                // Winning number highlight effect
                this.gameEnhancer.flashScreen(0xFFD700, 0.2, 300);
            } else {
                this.soundManager.playSound('lose');
            }
        }, 1000);

        if (this.originalSpinResult) {
            this.originalSpinResult();
        }
    }

    // Poker-specific enhancements
    setupPokerEnhancements() {
        // Enhance action animations
        if (this.scene.showActionAnimation) {
            this.originalPokerAction = this.scene.showActionAnimation.bind(this.scene);
            this.scene.showActionAnimation = this.enhancedPokerAction.bind(this);
        }

        // Enhance hand results
        if (this.scene.updateGameDisplay) {
            this.originalGameDisplay = this.scene.updateGameDisplay.bind(this.scene);
            this.scene.updateGameDisplay = this.enhancedPokerDisplay.bind(this);
        }
    }

    enhancedPokerAction(data) {
        const actionSounds = {
            'fold': 'fold',
            'call': 'call',
            'raise': 'raise',
            'bet': 'chipPlace',
            'all_in': 'allIn'
        };

        const sound = actionSounds[data.action];
        if (sound) {
            this.soundManager.playSound(sound);
        }

        // Chip animation for betting actions
        if (['bet', 'raise', 'call'].includes(data.action)) {
            this.gameEnhancer.createChipParticles(data.playerX || 400, data.playerY || 300, 3);
        }

        if (this.originalPokerAction) {
            this.originalPokerAction(data);
        }
    }

    enhancedPokerDisplay(gameState) {
        // Check for significant game events
        if (gameState.phase === 'showdown') {
            this.soundManager.playSound('cardFlip');
        } else if (gameState.phase === 'preflop' && gameState.hand_number !== this.lastHandNumber) {
            this.soundManager.playSound('cardShuffle');
            this.lastHandNumber = gameState.hand_number;
        }

        if (this.originalGameDisplay) {
            this.originalGameDisplay(gameState);
        }
    }

    // Generic enhancements for all games
    setupGenericEnhancements() {
        this.addGlobalEnhancements();
    }

    addGlobalEnhancements() {
        // Add ambient casino sounds
        this.soundManager.playSound('ambient', { loop: true, volume: 0.1 });

        // Add global UI sound feedback
        this.scene.input.on('pointerdown', (pointer, gameObject) => {
            if (gameObject && gameObject.length > 0) {
                this.soundManager.playSound('buttonClick', { volume: 0.3 });
            }
        });

        // Add hover sounds for interactive objects
        this.scene.input.on('pointerover', (pointer, gameObject) => {
            if (gameObject && gameObject.length > 0 && gameObject[0].input) {
                this.soundManager.playSound('hover', { volume: 0.2 });
            }
        });
    }

    // Utility methods for all games
    celebrateWin(amount, position = { x: 400, y: 300 }) {
        const winLevel = amount > 10000 ? 'jackpot' : amount > 1000 ? 'big' : 'normal';
        
        this.gameEnhancer.createWinParticles(position.x, position.y, winLevel);
        this.gameEnhancer.createFloatingText(position.x, position.y - 50, `+${amount}`, '#4CAF50');
        
        if (winLevel === 'jackpot') {
            this.soundManager.playSound('jackpot');
            this.gameEnhancer.shakeScreen(8, 500);
            this.gameEnhancer.flashScreen(0xFFD700, 0.5, 700);
        } else if (winLevel === 'big') {
            this.soundManager.playSound('bigWin');
            this.gameEnhancer.flashScreen(0x4CAF50, 0.3, 400);
        } else {
            this.soundManager.playSound('win');
        }
    }

    // Cleanup
    destroy() {
        if (this.soundManager) {
            this.soundManager.stopAllSounds();
        }
        
        if (this.gameEnhancer) {
            this.gameEnhancer.destroy();
        }
    }
}
