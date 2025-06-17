// Enhanced game utilities for polish and user experience
import Phaser from 'phaser';

export default class GameEnhancer {
    constructor(scene) {
        this.scene = scene;
        this.particles = {};
        this.animations = {};
        this.effects = {};
    }

    // Particle Effects
    createChipParticles(x, y, count = 5) {
        if (!this.scene.add.particles) return null;
        
        const particles = this.scene.add.particles(x, y, 'chip-particle', {
            speed: { min: 50, max: 150 },
            scale: { start: 0.5, end: 0 },
            lifespan: 600,
            alpha: { start: 1, end: 0 },
            quantity: count,
            tint: [0xFFD700, 0xFFA500, 0xFF4500]
        });
        
        // Auto-destroy after animation
        this.scene.time.delayedCall(1000, () => {
            if (particles && particles.destroy) {
                particles.destroy();
            }
        });
        
        return particles;
    }

    createWinParticles(x, y, type = 'normal') {
        if (!this.scene.add.particles) return null;
        
        const config = {
            normal: {
                count: 10,
                colors: [0xFFD700, 0xFFA500],
                speed: { min: 100, max: 200 },
                scale: { start: 0.8, end: 0.1 }
            },
            big: {
                count: 20,
                colors: [0xFFD700, 0xFF6B6B, 0x4ECDC4],
                speed: { min: 150, max: 300 },
                scale: { start: 1.2, end: 0.1 }
            },
            jackpot: {
                count: 50,
                colors: [0xFFD700, 0xFF6B6B, 0x4ECDC4, 0xFFE66D],
                speed: { min: 200, max: 400 },
                scale: { start: 1.5, end: 0.1 }
            }
        };
        
        const settings = config[type] || config.normal;
        
        const particles = this.scene.add.particles(x, y, 'star-particle', {
            speed: settings.speed,
            scale: settings.scale,
            lifespan: 1200,
            alpha: { start: 1, end: 0 },
            quantity: settings.count,
            tint: settings.colors,
            emitZone: { type: 'edge', source: new Phaser.Geom.Circle(0, 0, 50), quantity: 24 }
        });
        
        this.scene.time.delayedCall(2000, () => {
            if (particles && particles.destroy) {
                particles.destroy();
            }
        });
        
        return particles;
    }

    createCardDealEffect(startX, startY, endX, endY, cardTexture = 'card-back') {
        const card = this.scene.add.image(startX, startY, cardTexture)
            .setScale(0.8)
            .setAlpha(0.9);
        
        // Deal animation with card flip
        this.scene.tweens.add({
            targets: card,
            x: endX,
            y: endY,
            scale: 1,
            alpha: 1,
            duration: 500,
            ease: 'Power2',
            onComplete: () => {
                // Flip animation
                this.scene.tweens.add({
                    targets: card,
                    scaleX: 0,
                    duration: 100,
                    onComplete: () => {
                        card.setTexture(cardTexture);
                        this.scene.tweens.add({
                            targets: card,
                            scaleX: 1,
                            duration: 100
                        });
                    }
                });
            }
        });
        
        return card;
    }

    // Enhanced button animations
    createPulsingButton(button, pulseScale = 1.1) {
        if (!button) return;
        
        button.setInteractive();
        
        // Hover effects
        button.on('pointerover', () => {
            this.scene.tweens.add({
                targets: button,
                scale: pulseScale,
                duration: 200,
                ease: 'Power2'
            });
        });
        
        button.on('pointerout', () => {
            this.scene.tweens.add({
                targets: button,
                scale: 1,
                duration: 200,
                ease: 'Power2'
            });
        });
        
        button.on('pointerdown', () => {
            this.scene.tweens.add({
                targets: button,
                scale: 0.95,
                duration: 100,
                yoyo: true,
                ease: 'Power2'
            });
        });
        
        return button;
    }

    // Screen shake effect
    shakeScreen(intensity = 5, duration = 300) {
        if (!this.scene.cameras.main) return;
        
        this.scene.cameras.main.shake(duration, intensity);
    }

    // Flash effect for wins
    flashScreen(color = 0xFFFFFF, alpha = 0.3, duration = 200) {
        const flash = this.scene.add.rectangle(
            this.scene.cameras.main.centerX,
            this.scene.cameras.main.centerY,
            this.scene.cameras.main.width,
            this.scene.cameras.main.height,
            color,
            alpha
        ).setScrollFactor(0);
        
        this.scene.tweens.add({
            targets: flash,
            alpha: 0,
            duration: duration,
            onComplete: () => flash.destroy()
        });
        
        return flash;
    }

    // Number count-up animation
    animateNumber(textObject, startValue, endValue, duration = 1000, prefix = '', suffix = '') {
        if (!textObject) return;
        
        const valueObject = { value: startValue };
        
        this.scene.tweens.add({
            targets: valueObject,
            value: endValue,
            duration: duration,
            ease: 'Power2',
            onUpdate: () => {
                const currentValue = Math.floor(valueObject.value);
                textObject.setText(`${prefix}${currentValue.toLocaleString()}${suffix}`);
            }
        });
    }

    // Coin flip animation
    createCoinFlip(x, y, duration = 1000) {
        const coin = this.scene.add.image(x, y, 'coin-heads')
            .setScale(1);
        
        let isHeads = true;
        const flipInterval = setInterval(() => {
            coin.setTexture(isHeads ? 'coin-tails' : 'coin-heads');
            isHeads = !isHeads;
        }, 100);
        
        this.scene.tweens.add({
            targets: coin,
            y: y - 100,
            duration: duration / 2,
            ease: 'Power2',
            yoyo: true,
            onComplete: () => {
                clearInterval(flipInterval);
                // Final result
                coin.setTexture(Math.random() > 0.5 ? 'coin-heads' : 'coin-tails');
            }
        });
        
        return coin;
    }

    // Progressive reveal animation for slot reels
    createSlotReelSpin(reel, symbols, finalSymbol, duration = 2000) {
        if (!reel || !symbols) return;
        
        const spinSpeed = 50;
        let currentIndex = 0;
        
        const spinInterval = setInterval(() => {
            reel.setTexture(symbols[currentIndex % symbols.length]);
            currentIndex++;
        }, spinSpeed);
        
        this.scene.time.delayedCall(duration, () => {
            clearInterval(spinInterval);
            reel.setTexture(finalSymbol);
            
            // Bounce effect on stop
            this.scene.tweens.add({
                targets: reel,
                scaleY: 1.2,
                duration: 100,
                yoyo: true,
                ease: 'Power2'
            });
        });
    }

    // Create floating text effect
    createFloatingText(x, y, text, color = '#FFD700', duration = 2000) {
        const floatingText = this.scene.add.text(x, y, text, {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: color,
            fontStyle: 'bold',
            stroke: '#000000',
            strokeThickness: 2
        }).setOrigin(0.5);
        
        this.scene.tweens.add({
            targets: floatingText,
            y: y - 100,
            alpha: 0,
            scale: 1.5,
            duration: duration,
            ease: 'Power2',
            onComplete: () => floatingText.destroy()
        });
        
        return floatingText;
    }

    // Cleanup method
    destroy() {
        // Clean up any active animations or effects
        Object.values(this.particles).forEach(particle => {
            if (particle && particle.destroy) {
                particle.destroy();
            }
        });
        
        Object.values(this.effects).forEach(effect => {
            if (effect && effect.destroy) {
                effect.destroy();
            }
        });
        
        this.particles = {};
        this.animations = {};
        this.effects = {};
    }
}
