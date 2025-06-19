class GameScene extends Phaser.Scene {
    constructor() {
        super({ key: 'GameScene' });
    }

    init() {
        this.playerBalance = 1000;
        this.betAmount = 10;
        this.prizeTexts = [];
        this.notEnoughBalanceText = null;
        this.currentMultiplier = 1;
        this.portalBExitPeg = null;
        this.sounds = {}; // For storing sound instances
    }

    preload() {
        // Optional: Load assets here if not in PreloadScene
    }

    create() {
        const gameWidth = this.sys.game.config.width;
        const gameHeight = this.sys.game.config.height;

        // Create 'pixel' texture for particle effects
        if (!this.textures.exists('pixel')) {
            let graphics = this.make.graphics();
            graphics.fillStyle(0xffffff);
            graphics.fillRect(0, 0, 1, 1);
            graphics.generateTexture('pixel', 1, 1);
            graphics.destroy();
        }

        // Store Sounds
        const soundKeys = ['plink', 'zap', 'collect', 'win', 'drop', 'jackpot_sound', 'portal_activate'];
        soundKeys.forEach(key => {
            if (this.sound.get(key)) { // Check if the sound was loaded
                this.sounds[key] = this.sound.add(key);
            } else {
                console.warn(`Audio file for '${key}' not loaded or missing. Sound effects will be logged.`);
            }
        });

        // Resume Audio Context on first pointer down
        this.input.once('pointerdown', () => {
            if (this.sound.context.state === 'suspended') {
                this.sound.context.resume().then(() => {
                    console.log("Audio context resumed successfully.");
                }).catch(e => {
                    console.error("Error resuming audio context:", e);
                });
            }
        }, this);


        // UI Elements
        this.balanceText = this.add.text(10, 10, 'Balance: ' + this.playerBalance, { fontSize: '16px', fill: '#fff' });
        this.multiplierText = this.add.text(gameWidth - 10, 10, 'Multiplier: 1x', { fontSize: '16px', fill: '#fff', align: 'right' }).setOrigin(1, 0);
        this.updateMultiplierDisplay();

        // Physics Engine
        this.physics.world.setBounds(0, 0, gameWidth, gameHeight);
        this.physics.world.gravity.y = 200;

        // Board Background
        this.add.rectangle(0, 0, gameWidth, gameHeight, 0x000033).setOrigin(0,0);

        // Pegs
        this.pegsGroup = this.physics.add.staticGroup();
        const pegRadius = 8;
        const pegColor = 0xffffff;
        const rows = 10;
        const cols = 7;
        const spacingX = gameWidth / (cols + 1);
        const spacingY = (gameHeight * 0.6) / rows;
        const offsetX = spacingX / 2;
        const startY = 80;

        for (let i = 0; i < rows; i++) {
            const currentColCount = (i % 2 === 0) ? cols : cols - 1;
            const currentOffsetX = (i % 2 === 0) ? spacingX : spacingX + offsetX;
            for (let j = 0; j < currentColCount; j++) {
                let x = (j * spacingX) + currentOffsetX;
                let y = startY + (i * spacingY);
                let peg = this.pegsGroup.create(x, y, undefined);
                peg.setCircle(pegRadius);
                peg.setTint(pegColor); // Store this as originalTint in data if needed
                peg.setData('originalTint', pegColor);
                peg.refreshBody();
                peg.setData('isMultiplier', false);
                peg.setData('isPortal', null);

                if (j === 2 && (i % 2 === 0)) {
                    peg.setTint(0xffaa00);
                    peg.setData('originalTint', 0xffaa00);
                    peg.setData('isMultiplier', true);
                    peg.setData('multiplierValue', 2);
                }

                if (i === 1 && j === 1) {
                    peg.setTint(0x00aaff);
                    peg.setData('originalTint', 0x00aaff);
                    peg.setData('isPortal', 'A');
                } else if (i === rows - 3 && j === Math.floor(currentColCount / 2)) {
                    peg.setTint(0x00aaff);
                    peg.setData('originalTint', 0x00aaff);
                    peg.setData('isPortal', 'B');
                    this.portalBExitPeg = peg;
                }
            }
        }

        // Prize Slots
        this.prizeSlotsGroup = this.physics.add.staticGroup();
        const slotHeight = 30;
        const numSlots = 5;
        const slotWidth = gameWidth / numSlots;
        const slotY = gameHeight - slotHeight / 2;
        // const slotColors = [0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff]; // Colors set by assignPrizeValues tween

        for (let i = 0; i < numSlots; i++) {
            let x = i * slotWidth + slotWidth / 2;
            // Initial color will be set by assignPrizeValues, start with a neutral/default
            let slotGameObject = this.add.rectangle(x, slotY, slotWidth, slotHeight, 0x777777);
            this.prizeSlotsGroup.add(slotGameObject);
            slotGameObject.setData('slotValue', i + 1);
            slotGameObject.setData('originalTint', 0x777777); // Store for tween
            slotGameObject.body.setSize(slotWidth, slotHeight);
            slotGameObject.body.setImmovable(true);
            slotGameObject.body.isSensor = true;
        }

        this.prizeSlotsGroup.getChildren().forEach(slot => {
            const prizeValueText = this.add.text(slot.x, slot.y - 30, '', { fontSize: '14px', fill: '#fff', align: 'center' }).setOrigin(0.5);
            this.prizeTexts.push(prizeValueText);
        });

        this.particleRadius = 6;
        this.particleColor = 0xff0000;
        this.particles = this.physics.add.group();

        this.input.on('pointerdown', (pointer) => {
            if(pointer.y < slotY - 50) { // Only drop if click is above slots
                 this.dropParticle(pointer.x);
            }
        }, this);

        this.physics.add.collider(this.particles, this.pegsGroup, this.handleParticlePegCollision, null, this);
        this.physics.add.overlap(this.particles, this.prizeSlotsGroup, this.handleParticleSlotCollision, null, this);

        this.assignPrizeValues();
    }

    playSound(key) {
       if (this.sounds && this.sounds[key] && this.sound.context.state === 'running') {
           this.sounds[key].play();
       } else {
           let message = `Simulating sound: ${key}`;
           if (this.sound.context.state !== 'running') { // Check if context is not running
               message += ` (AudioContext not running: ${this.sound.context.state})`;
           }
           console.log(message);
       }
    }

    updateBalanceDisplay() {
        if (this.balanceText) this.balanceText.setText('Balance: ' + this.playerBalance);
    }

    updateMultiplierDisplay() {
        if (this.multiplierText) {
            this.multiplierText.setText('Multiplier: ' + this.currentMultiplier + 'x');
        }
    }

    assignPrizeValues() {
        const possiblePrizes = [0, 5, 10, 0, 20, 50, 0, 5, 100];
        const jackpotBaseValue = 250;
        const jackpotChance = 0.10;
        let jackpotAwardedThisRound = false;

        this.prizeSlotsGroup.getChildren().forEach((slot, index) => {
            let currentPrize;
            let isJackpot = false;

            if (!jackpotAwardedThisRound && Phaser.Math.FloatBetween(0, 1) < jackpotChance / (this.prizeSlotsGroup.getLength() - index)) {
                currentPrize = jackpotBaseValue;
                isJackpot = true;
                jackpotAwardedThisRound = true;
            } else {
                currentPrize = Phaser.Math.RND.pick(possiblePrizes);
            }

            slot.setData('currentPrizeValue', currentPrize);
            slot.setData('isJackpot', isJackpot);
            const originalSlotTint = slot.getData('originalTint') || 0x777777; // Fallback

            if (this.prizeTexts[index]) {
                if (isJackpot) {
                    this.prizeTexts[index].setText(`JACKPOT! ${currentPrize}`).setColor('#FFFF00').setFontStyle('bold');
                } else {
                    this.prizeTexts[index].setText(currentPrize > 0 ? currentPrize.toString() : '---').setColor('#FFFFFF').setFontStyle('normal');
                }
            }

            let flashColor = isJackpot ? 0xffff00 : (currentPrize > 0 ? 0x00ff00 : 0xcc0000); // Red for 0 prize
            if(currentPrize === 0) flashColor = 0xaa0000; // Darker red for 0

            slot.setAlpha(1);
            slot.setVisible(true);
            // Tween from current (potentially last tween's end color) to new flash color, then back to its defined original
            const current визуальныйTint = slot.tintTopLeft;
            this.tweens.killTweensOf(slot); // Kill existing tweens on this slot

            slot.setTint(current визуальныйTint); // Ensure it starts from its current actual tint for the tween

            this.tweens.add({
                targets: slot,
                tint: flashColor,
                duration: 150,
                ease: 'Power1',
                onComplete: () => { // Then tween back to its base color (originalTint stored in data)
                    this.tweens.add({
                        targets: slot,
                        tint: originalSlotTint,
                        duration: 350,
                        ease: 'Power1',
                    });
                }
            });
        });
    }


    dropParticle(xPosition, isMultiBallDrop = false) {
        let particle; // Declare particle here to be accessible for effects
        if (!isMultiBallDrop) {
            if (this.notEnoughBalanceText) {
                this.notEnoughBalanceText.destroy();
                this.notEnoughBalanceText = null;
            }
            if (this.playerBalance < this.betAmount) {
                this.notEnoughBalanceText = this.add.text(this.sys.game.config.width / 2, this.sys.game.config.height / 2, 'Not Enough Balance!', { fontSize: '32px', fill: '#ff0000', backgroundColor: '#333333' }).setOrigin(0.5);
                this.time.delayedCall(1500, () => {
                    if(this.notEnoughBalanceText) this.notEnoughBalanceText.destroy();
                    this.notEnoughBalanceText = null;
                });
                return;
            }
            this.playerBalance -= this.betAmount;
            this.updateBalanceDisplay();
            this.currentMultiplier = 1;
            this.updateMultiplierDisplay();
            this.assignPrizeValues();
        }

        const initialY = 50;
        const clampedX = Phaser.Math.Clamp(xPosition, this.particleRadius, this.sys.game.config.width - this.particleRadius);

        particle = this.particles.create(clampedX, initialY, undefined);
        particle.setCircle(this.particleRadius);
        particle.setFillStyle(this.particleColor, 1);
        particle.setDisplaySize(this.particleRadius * 2, this.particleRadius * 2);
        particle.setBounce(0.4, 0.4);
        particle.setCollideWorldBounds(true);
        particle.body.setCircle(this.particleRadius);
        particle.setGravityY(300);

        this.playSound('drop');
        if (this.textures.exists('pixel')) {
            const emitter = this.add.particles(0,0,'pixel', { // Emitter is a GameObject, can be stored or just fire and forget
                x: particle.x, y: particle.y,
                speed: {min: 10, max: 50}, lifespan: 300, quantity: 5, scale: {start: 0.5, end:0}, blendMode: 'ADD',
                emitting: true
            });
            this.time.delayedCall(300, () => emitter.destroy()); // Self-destruct emitter
        }


        if (!isMultiBallDrop && Phaser.Math.FloatBetween(0, 1) < 0.15) {
            this.triggerMultiBall(clampedX);
        }
    }

    triggerMultiBall(originalX) {
        const numberOfExtraBalls = Phaser.Math.Between(1, 2);
        for (let i = 0; i < numberOfExtraBalls; i++) {
            this.time.delayedCall(Phaser.Math.Between(100, 300) * (i + 1), () => {
                let newX = originalX + Phaser.Math.Between(-60, 60);
                newX = Phaser.Math.Clamp(newX, this.particleRadius, this.sys.game.config.width - this.particleRadius);
                this.dropParticle(newX, true);
            });
        }
    }

    handleParticlePegCollision(particle, peg) {
        // HAPTIC (conceptual): if (navigator.vibrate) { navigator.vibrate(20); }
        this.playSound('plink');
        if (this.textures.exists('pixel')) {
            const emitter = this.add.particles(0,0,'pixel', {
                x: particle.x, y: particle.y,
                speed: { min: 30, max: 100 }, angle: { min: 0, max: 360 },
                scale: { start: 0.3, end: 0 }, lifespan: { min: 100, max: 200 },
                blendMode: 'ADD', quantity: Phaser.Math.Between(2, 4), emitting: true
            });
            this.time.delayedCall(200, () => emitter.destroy());
        }

        if (peg.getData('isMultiplier')) {
            this.playSound('zap');
            const multiplierValue = peg.getData('multiplierValue') || 2;
            this.currentMultiplier *= multiplierValue;
            const originalPegTint = peg.getData('originalTint') || 0xffaa00;
            peg.setTint(0xff0000);
            this.time.delayedCall(150, () => { peg.setTint(originalPegTint); });
            this.updateMultiplierDisplay();
        } else if (peg.getData('isPortal') === 'A') {
            this.playSound('portal_activate');
            if (this.portalBExitPeg) {
                if (this.textures.exists('pixel')) {
                    const emitterA = this.add.particles(0,0,'pixel', { x: peg.x, y: peg.y, scale: {start:0.5, end:0}, quantity: 15, speed: 50, lifespan: 400, blendMode: 'ADD', emitting: true});
                    this.time.delayedCall(400, () => emitterA.destroy());
                }
                particle.setPosition(this.portalBExitPeg.x, this.portalBExitPeg.y - 25);
                particle.setVelocity(Phaser.Math.Between(-60, 60), -200);

                particle.setVisible(false);
                this.time.delayedCall(100, () => {
                     particle.setVisible(true);
                     if(this.portalBExitPeg && this.textures.exists('pixel')) {
                        const emitterB = this.add.particles(0,0,'pixel', { x: this.portalBExitPeg.x, y: this.portalBExitPeg.y -15, scale: {start:0.5, end:0}, quantity: 15, speed: 50, lifespan: 400, blendMode: 'ADD', emitting: true});
                        this.time.delayedCall(400, () => emitterB.destroy());
                     }
                });
            }
        } else { // Regular peg hit
            const originalPegTint = peg.getData('originalTint') || 0xffffff;
            peg.setTint(0xaaaaaa);
            this.time.delayedCall(100, () => { peg.setTint(originalPegTint); });
        }
    }

    handleParticleSlotCollision(particle, slot) {
        // HAPTIC (conceptual): if (navigator.vibrate) { navigator.vibrate([100, 30, 100]); }
        this.playSound('collect');
        const prizeWon = slot.getData('currentPrizeValue');
        const isJackpot = slot.getData('isJackpot');
        const finalPrize = prizeWon * this.currentMultiplier;

        if (this.textures.exists('pixel')) {
            const emitter = this.add.particles(0,0,'pixel', {
                x: particle.x, y: slot.y - 10, // Emit slightly above the slot base
                speed: { min: 50, max: 150 }, angle: { start: 240, end: 300 }, // Upwards burst
                scale: { start: 0.6, end: 0 }, alpha: { start: 1, end: 0.3 },
                lifespan: { min: 300, max: 600 }, blendMode: 'ADD',
                quantity: Phaser.Math.Between(10, 20), emitting: true
            });
            this.time.delayedCall(600, () => emitter.destroy());
        }

        if (finalPrize > 0) {
            this.playSound('win');
            this.playerBalance += finalPrize;
            this.updateBalanceDisplay();
            let winMsg = `WIN: ${finalPrize}!`;
            if (this.currentMultiplier > 1) {
                winMsg = `WIN: ${finalPrize}! (${prizeWon} x${this.currentMultiplier})`;
            }
            let winText = this.add.text(slot.x, slot.y - 70, winMsg, { fontSize: '20px', fill: '#ffd700', align: 'center', stroke: '#000', strokeThickness: 2 }).setOrigin(0.5);
            this.time.delayedCall(2000, () => { winText.destroy(); });

            if (isJackpot) {
                this.playSound('jackpot_sound');
                let jackpotWinText = this.add.text(this.sys.game.config.width / 2, this.sys.game.config.height / 2, `!!!JACKPOT ${finalPrize}!!!`, { fontSize: '48px', fill: '#ff00ff', stroke: '#ffffff', strokeThickness: 6 }).setOrigin(0.5);
                this.time.delayedCall(3000, () => { jackpotWinText.destroy(); });

                if (this.textures.exists('pixel')) { // Jackpot screen flash
                    let flash = this.add.rectangle(this.cameras.main.centerX, this.cameras.main.centerY, this.cameras.main.width, this.cameras.main.height, 0xffffff, 0.0);
                    flash.setAlpha(0.4);
                    this.tweens.add({ targets: flash, alpha: 0, duration: 700, ease: 'Cubic.easeOut', onComplete: () => flash.destroy() });
                }
            }

        } else { // No prize or 0 prize
            let noWinText = this.add.text(slot.x, slot.y - 70, '0', { fontSize: '24px', fill: '#aaaaaa', align: 'center', stroke: '#000', strokeThickness:2 }).setOrigin(0.5);
            this.time.delayedCall(1500, () => { noWinText.destroy(); });
        }
        particle.destroy();
    }

    update() {
        // Game logic can be added here if needed
    }
}
