/**
 * Comprehensive game effects system for all casino games
 * Elite-level animation and particle system implementation
 */

export class GameEffects {
    constructor(scene) {
        this.scene = scene;
        this.particles = {};
        this.tweens = [];
        this.sounds = scene.game.soundManager;
    }

    // === COIN EFFECTS ===
    createCoinRain(x, y, amount = 10) {
        const coins = [];
        for (let i = 0; i < amount; i++) {
            const coin = this.scene.add.image(x + (Math.random() - 0.5) * 100, y - 50, 'coin');
            coin.setScale(0.5);
            
            this.scene.tweens.add({
                targets: coin,
                y: y + 200 + Math.random() * 100,
                x: coin.x + (Math.random() - 0.5) * 200,
                rotation: Math.random() * Math.PI * 4,
                scale: 0.3,
                alpha: 0,
                duration: 1000 + Math.random() * 500,
                ease: 'Bounce.easeOut',
                onComplete: () => coin.destroy()
            });
            
            coins.push(coin);
        }
        return coins;
    }

    createWinExplosion(x, y, winAmount) {
        // Main explosion effect
        const explosion = this.scene.add.particles(x, y, 'sparkle', {
            speed: { min: 100, max: 300 },
            scale: { start: 0.5, end: 0 },
            blendMode: 'ADD',
            lifespan: 600
        });

        // Win text
        const winText = this.scene.add.text(x, y - 50, `+$${winAmount}`, {
            fontSize: '32px',
            fill: '#FFD700',
            stroke: '#000',
            strokeThickness: 4
        }).setOrigin(0.5);

        this.scene.tweens.add({
            targets: winText,
            y: y - 150,
            scale: 1.5,
            alpha: 0,
            duration: 2000,
            ease: 'Power2.easeOut',
            onComplete: () => {
                winText.destroy();
                explosion.destroy();
            }
        });

        this.sounds?.play('win');
        return { explosion, winText };
    }

    // === CARD EFFECTS ===
    dealCard(card, targetX, targetY, delay = 0) {
        card.setPosition(-100, -100);
        card.setRotation(0.2);
        card.setScale(0.8);

        return this.scene.tweens.add({
            targets: card,
            x: targetX,
            y: targetY,
            rotation: 0,
            scale: 1,
            duration: 300,
            delay: delay,
            ease: 'Back.easeOut'
        });
    }

    flipCard(card, newTexture) {
        return this.scene.tweens.add({
            targets: card,
            scaleX: 0,
            duration: 150,
            onComplete: () => {
                if (newTexture) card.setTexture(newTexture);
                this.scene.tweens.add({
                    targets: card,
                    scaleX: 1,
                    duration: 150,
                    ease: 'Back.easeOut'
                });
            }
        });
    }

    highlightCard(card, color = 0xFFD700) {
        const glow = this.scene.add.graphics();
        glow.lineStyle(4, color, 0.8);
        glow.strokeRoundedRect(card.x - card.width/2 - 5, card.y - card.height/2 - 5, 
                              card.width + 10, card.height + 10, 10);
        
        this.scene.tweens.add({
            targets: glow,
            alpha: 0,
            duration: 1000,
            yoyo: true,
            repeat: 2,
            onComplete: () => glow.destroy()
        });

        return glow;
    }

    // === CHIP EFFECTS ===
    animateChipBet(chip, fromX, fromY, toX, toY) {
        chip.setPosition(fromX, fromY);
        chip.setScale(0.8);

        return this.scene.tweens.add({
            targets: chip,
            x: toX,
            y: toY,
            scale: 1,
            duration: 500,
            ease: 'Power2.easeOut'
        });
    }

    collectChips(chips, targetX, targetY) {
        const promises = chips.map((chip, index) => {
            return new Promise(resolve => {
                this.scene.tweens.add({
                    targets: chip,
                    x: targetX,
                    y: targetY,
                    scale: 0.5,
                    alpha: 0.7,
                    duration: 600,
                    delay: index * 50,
                    ease: 'Power2.easeIn',
                    onComplete: () => {
                        chip.destroy();
                        resolve();
                    }
                });
            });
        });

        return Promise.all(promises);
    }

    // === SLOT EFFECTS ===
    spinReel(reel, symbols, duration = 1000) {
        const originalY = reel.y;
        
        return this.scene.tweens.add({
            targets: reel,
            y: originalY + symbols.length * 100,
            duration: duration,
            ease: 'Power2.easeOut',
            onUpdate: () => {
                // Update symbol visibility during spin
                symbols.forEach((symbol, index) => {
                    const symbolY = originalY + (index * 100) + (reel.y - originalY) % (symbols.length * 100);
                    symbol.setPosition(reel.x, symbolY);
                });
            }
        });
    }

    createPaylineFlash(payline, symbols) {
        symbols.forEach((symbol, index) => {
            this.scene.tweens.add({
                targets: symbol,
                scaleX: 1.2,
                scaleY: 1.2,
                alpha: 0.8,
                duration: 300,
                delay: index * 100,
                yoyo: true,
                repeat: 3
            });
        });

        // Draw payline
        const line = this.scene.add.graphics();
        line.lineStyle(5, 0xFFD700, 0.8);
        line.beginPath();
        line.moveTo(symbols[0].x, symbols[0].y);
        symbols.forEach(symbol => line.lineTo(symbol.x, symbol.y));
        line.strokePath();

        this.scene.tweens.add({
            targets: line,
            alpha: 0,
            duration: 2000,
            onComplete: () => line.destroy()
        });
    }

    // === ROULETTE EFFECTS ===
    spinWheel(wheel, finalAngle, duration = 3000) {
        const startAngle = wheel.rotation;
        const totalRotation = finalAngle + Math.PI * 8; // Multiple full rotations

        return this.scene.tweens.add({
            targets: wheel,
            rotation: startAngle + totalRotation,
            duration: duration,
            ease: 'Power3.easeOut'
        });
    }

    dropBall(ball, wheel, finalAngle, duration = 3000) {
        const radius = 180;
        const finalX = wheel.x + Math.cos(finalAngle) * radius;
        const finalY = wheel.y + Math.sin(finalAngle) * radius;

        // Ball bouncing effect
        return this.scene.tweens.add({
            targets: ball,
            x: finalX,
            y: finalY,
            duration: duration,
            ease: 'Bounce.easeOut'
        });
    }

    // === PLINKO EFFECTS ===
    dropPlinkoDisc(disc, pegs, multipliers) {
        const path = this.calculatePlinkoPath(pegs);
        let currentIndex = 0;

        const animateToNextPeg = () => {
            if (currentIndex >= path.length) {
                // Disc reached bottom
                const multiplier = this.getRandomMultiplier(multipliers);
                this.createWinExplosion(disc.x, disc.y, multiplier);
                return;
            }

            const target = path[currentIndex];
            this.scene.tweens.add({
                targets: disc,
                x: target.x,
                y: target.y,
                duration: 200,
                ease: 'Power2.easeIn',
                onComplete: () => {
                    // Bounce effect at peg
                    this.scene.tweens.add({
                        targets: disc,
                        scaleX: 1.2,
                        scaleY: 0.8,
                        duration: 100,
                        yoyo: true,
                        onComplete: () => {
                            currentIndex++;
                            animateToNextPeg();
                        }
                    });
                }
            });
        };

        animateToNextPeg();
    }

    calculatePlinkoPath(pegs) {
        // Simplified path calculation - in practice this would be more complex
        return pegs.slice(0, 8).map((peg, index) => ({
            x: peg.x + (Math.random() - 0.5) * 50,
            y: peg.y
        }));
    }

    getRandomMultiplier(multipliers) {
        return multipliers[Math.floor(Math.random() * multipliers.length)];
    }

    // === PARTICLE SYSTEMS ===
    createFireworks(x, y) {
        const colors = [0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00, 0xFF00FF];
        
        colors.forEach((color, index) => {
            setTimeout(() => {
                const firework = this.scene.add.particles(x, y, 'sparkle', {
                    speed: { min: 200, max: 400 },
                    scale: { start: 0.8, end: 0 },
                    tint: color,
                    blendMode: 'ADD',
                    lifespan: 1000,
                    quantity: 15
                });

                setTimeout(() => firework.destroy(), 2000);
            }, index * 200);
        });
    }

    createConfetti(x, y) {
        const confetti = this.scene.add.particles(x, y, 'confetti', {
            speed: { min: 100, max: 200 },
            gravityY: 300,
            scale: { min: 0.3, max: 0.8 },
            rotate: { min: 0, max: 360 },
            lifespan: 3000,
            quantity: 20
        });

        setTimeout(() => confetti.destroy(), 4000);
        return confetti;
    }

    // === SCREEN SHAKE ===
    screenShake(intensity = 5, duration = 300) {
        this.scene.cameras.main.shake(duration, intensity);
    }

    // === CLEANUP ===
    destroy() {
        this.tweens.forEach(tween => {
            if (tween && tween.destroy) tween.destroy();
        });
        
        Object.values(this.particles).forEach(particle => {
            if (particle && particle.destroy) particle.destroy();
        });

        this.tweens = [];
        this.particles = {};
    }
}

// Export for use in scenes
export default GameEffects;
