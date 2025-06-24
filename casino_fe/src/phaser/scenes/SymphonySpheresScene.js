// casino_fe/src/phaser/scenes/SymphonySpheresScene.js
import Phaser from 'phaser';
import { apiService } from '@/services/api';
import { EventBus } from '@/event-bus';

export default class SymphonySpheresScene extends Phaser.Scene {
    constructor() {
        super({ key: 'SymphonySpheresScene' });
        this.spheresGroup = null;
        this.gridConfig = {
            width: 10,
            height: 10,
            sphereDiameter: 60,
            padding: 5,
            startX: 0,
            startY: 0
        };
        this.canSpin = true;
        this.gameConfigData = null;
        this.sphereColorMap = new Map();
        this.gridGameObjects = [];
        this.currentPulseData = null; // To store backend response for finalizePulse
    }

    preload() {
        this.load.image('pulse_button', 'assets/ui/spin_button.png');
        this.load.image('particle_glow', 'assets/particles/glow_particle.png');
        this.load.image('prism_particle_spark', 'assets/particles/glow_particle.png');

        this.load.audio('pulse_activate_sound', 'assets/sounds/symphony_pulse_activate.mp3');
        this.load.audio('sphere_disappear_sound', 'assets/sounds/symphony_sphere_disappear.mp3');
        this.load.audio('sphere_land_sound', 'assets/sounds/symphony_sphere_land.mp3');
        this.load.audio('win_event_sound', 'assets/sounds/symphony_win_event.mp3');
        this.load.audio('harmony_event_sound', 'assets/sounds/symphony_harmony_jackpot.mp3');
        this.load.audio('prism_activate_sound', 'assets/sounds/symphony_win_event.mp3');
    }

    _generateSphereTextures() {
        const sphereDiameter = this.gridConfig.sphereDiameter;
        if (this.gameConfigData && this.gameConfigData.config && this.gameConfigData.config.sphere_colors) {
            this.gameConfigData.config.sphere_colors.forEach((color) => {
                const textureKey = `sphere_color_${color.replace('#','')}`;
                this.sphereColorMap.set(color, textureKey);
                let graphics = this.make.graphics({ x: 0, y: 0, add: false });
                try {
                    let phaserColor = Phaser.Display.Color.HexStringToColor(color);
                    graphics.fillStyle(phaserColor.color, 1);
                    graphics.fillCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2);
                    graphics.generateTexture(textureKey, sphereDiameter, sphereDiameter);
                } catch (e) {
                    console.error(`Error processing color ${color}:`, e);
                    let defaultColor = Phaser.Display.Color.HexStringToColor("#CCCCCC");
                    graphics.fillStyle(defaultColor.color, 1);
                    graphics.fillCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2);
                    graphics.generateTexture(textureKey, sphereDiameter, sphereDiameter);
                } finally {
                    graphics.destroy();
                }
            });
        } else {
            const textureKey = 'sphere_default_color';
            this.sphereColorMap.set("#CCCCCC", textureKey);
            let graphics = this.make.graphics({x: 0, y: 0, add: false});
            graphics.fillStyle(0xCCCCCC, 1);
            graphics.fillCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2);
            graphics.generateTexture(textureKey, sphereDiameter, sphereDiameter);
            graphics.destroy();
        }

        const prismTextureKey = 'prism_sphere_texture';
        let prismGraphics = this.make.graphics({x: 0, y: 0, add: false});
        prismGraphics.fillStyle(0xffffff, 1);
        prismGraphics.fillCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2);
        prismGraphics.lineStyle(2, 0xff0000, 1); prismGraphics.strokeCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2 - 2);
        prismGraphics.lineStyle(2, 0x00ff00, 1); prismGraphics.strokeCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2 - 5);
        prismGraphics.lineStyle(2, 0x0000ff, 1); prismGraphics.strokeCircle(sphereDiameter / 2, sphereDiameter / 2, sphereDiameter / 2 - 8);
        prismGraphics.generateTexture(prismTextureKey, sphereDiameter, sphereDiameter);
        prismGraphics.destroy();
        this.sphereColorMap.set('prism', prismTextureKey);
    }

    _getSphereTextureKey(colorString, isPrism = false) {
        if (isPrism) {
            const prismKey = this.sphereColorMap.get('prism');
            return this.textures.exists(prismKey) ? prismKey : (this.sphereColorMap.get("#CCCCCC") || 'sphere_default_color');
        }
        const colorKey = this.sphereColorMap.get(colorString);
        return this.textures.exists(colorKey) ? colorKey : (this.sphereColorMap.get("#CCCCCC") || 'sphere_default_color');
    }

    getSphereAtGrid(r, c) {
        if (this.gridGameObjects && this.gridGameObjects[r] && this.gridGameObjects[r][c]) {
            const sphere = this.gridGameObjects[r][c];
            return sphere.active ? sphere : null;
        }
        return null;
    }

    _calculateGridPositions() {
        const totalGridWidth = this.gridConfig.width * (this.gridConfig.sphereDiameter + this.gridConfig.padding) - this.gridConfig.padding;
        const totalGridHeight = this.gridConfig.height * (this.gridConfig.sphereDiameter + this.gridConfig.padding) - this.gridConfig.padding;
        this.gridConfig.startX = (this.cameras.main.width - totalGridWidth) / 2;
        this.gridConfig.startY = (this.cameras.main.height - totalGridHeight) / 2 - 50;
    }

    create(data) {
        this.gameConfigData = data.gameConfigData;
        if (!this.gameConfigData || !this.gameConfigData.config || !this.gameConfigData.slot_info) {
            this.scene.start('SlotsScene'); return;
        }

        this._generateSphereTextures();
        this._calculateGridPositions();

        this.add.text(this.cameras.main.width / 2, 50, this.gameConfigData.slot_info.name || 'Symphony of Spheres', { fontSize: '32px', fill: '#fff' }).setOrigin(0.5);
        this.pulseButton = this.add.image(this.cameras.main.width / 2, this.cameras.main.height - 100, 'pulse_button').setInteractive({ cursor: 'pointer' }).on('pointerdown', () => this.activatePulse());

        this.spheresGroup = this.add.group();
        this.initializeSphereField();

        EventBus.on('symphony-spheres-pulse-result', this.handlePulseResult, this);
        this.events.on('shutdown', this.shutdown, this);
    }

    initializeSphereField(initialSphereData = null) {
        this.spheresGroup.clear(true, true);
        this.gridGameObjects = Array(this.gridConfig.height).fill(null).map(() => Array(this.gridConfig.width).fill(null));

        if (this.gameConfigData?.config?.base_field_dimensions) {
            this.gridConfig.width = this.gameConfigData.config.base_field_dimensions.width || 10;
            this.gridConfig.height = this.gameConfigData.config.base_field_dimensions.height || 10;
        }

        for (let y = 0; y < this.gridConfig.height; y++) {
            for (let x = 0; x < this.gridConfig.width; x++) {
                const sphereX = this.gridConfig.startX + x * (this.gridConfig.sphereDiameter + this.gridConfig.padding) + this.gridConfig.sphereDiameter / 2;
                const sphereY = this.gridConfig.startY + y * (this.gridConfig.sphereDiameter + this.gridConfig.padding) + this.gridConfig.sphereDiameter / 2;

                let sphereColor, isPrism = false;
                const sphereData = initialSphereData && initialSphereData[y] && initialSphereData[y][x];

                if (sphereData) {
                    sphereColor = sphereData.color;
                    isPrism = sphereData.is_prism === true || sphereData.type === 'prism';
                } else {
                    sphereColor = Phaser.Math.RND.pick(this.gameConfigData.config.sphere_colors || ["#CCCCCC"]);
                }

                const sphereTextureKey = this._getSphereTextureKey(sphereColor, isPrism);

                const sphere = this.add.sprite(sphereX, sphereY, sphereTextureKey);
                sphere.displayWidth = this.gridConfig.sphereDiameter;
                sphere.displayHeight = this.gridConfig.sphereDiameter;
                sphere.setData('gridX', x);
                sphere.setData('gridY', y);
                sphere.setData('isPrism', isPrism);
                this.spheresGroup.add(sphere);
                this.gridGameObjects[y][x] = sphere;
            }
        }
    }

    _generateMockSphereGrid(width, height, type) {
        const grid = [];
        const colors = this.gameConfigData.config.sphere_colors || ["#FF0000", "#00FF00", "#0000FF"];
        const harmonyColor = colors.length > 3 ? colors[3] : colors[0]; // Assuming 4th color is for harmony if available

        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                let color = Phaser.Math.RND.pick(colors);
                let is_prism = false;

                if (type === 'simple_win' && y === 1 && x < 3) {
                    color = colors[0]; // Force first color for a cluster
                } else if (type === 'prism_win' && y === 1 && x === 1) {
                    is_prism = true; // Place a prism sphere
                    color = colors[0]; // Make it part of a potential win with color[0]
                } else if (type === 'prism_win' && y === 1 && (x === 0 || x === 2)) {
                    color = colors[0];
                } else if (type === 'harmony_pattern' && y === 0 && x < 5) {
                    color = harmonyColor;
                }
                row.push({ color: color, texture: 'smooth', is_prism: is_prism });
            }
            grid.push(row);
        }
        return grid;
    }


    async activatePulse() {
        if (!this.canSpin) return;
        this.canSpin = false;
        this.pulseButton.setAlpha(0.5);
        this.sound.play('pulse_activate_sound', { volume: 0.7 });

        const betAmount = Number(localStorage.getItem('currentBetAmount')) || 100;

        // --- Start Mocking ---
        // Comment out the actual API call for testing:
        // try {
        //     const response = await apiService.spinSlot(this.gameConfigData.slot_info.id, betAmount);
        //     if (response.status && response.data) {
        //         EventBus.emit('symphony-spheres-pulse-result', response.data);
        //     } else {
        //         EventBus.emit('show-error-message', response.data?.status_message || 'Pulse failed.');
        //         this.canSpin = true; this.pulseButton.setAlpha(1.0);
        //     }
        // } catch (error) {
        //     EventBus.emit('show-error-message', error.response?.data?.status_message || 'Error during pulse.');
        //     this.canSpin = true; this.pulseButton.setAlpha(1.0);
        // }

        let mockResponseData;
        const scenario = 'simple_win'; // Change to 'no_win', 'simple_win', 'prism_win', 'harmony_win'
        const defaultColors = this.gameConfigData.config.sphere_colors || ["#FF0000", "#00FF00", "#0000FF"];


        const baseUser = { balance: 5000, id: 1, username: 'TestUser' };
        const baseGameSession = {
            bonus_active: false, bonus_spins_remaining: 0, bonus_multiplier: 1.0,
            id: 123, user_id: 1, slot_id: this.gameConfigData.slot_info.id, game_type: 'slot',
            amount_wagered: 0, amount_won: 0, num_spins: 0,
            session_start: new Date().toISOString(), session_end: null
        };

        if (scenario === 'no_win') {
            mockResponseData = {
                status: true,
                data: {
                    result: {
                        final_spheres: this._generateMockSphereGrid(this.gridConfig.width, this.gridConfig.height, 'no_win'),
                        win_amount_sats: 0, winning_events: [], harmony_event_triggered: false, is_cascade_active: false
                    },
                    win_amount: 0, winning_lines: [], bonus_triggered: false,
                    bonus_active: baseGameSession.bonus_active, bonus_spins_remaining: baseGameSession.bonus_spins_remaining,
                    bonus_multiplier: baseGameSession.bonus_multiplier,
                    game_session: { ...baseGameSession, amount_wagered: betAmount, num_spins: baseGameSession.num_spins + 1 },
                    user: { ...baseUser, balance: baseUser.balance - betAmount }
                }
            };
        } else if (scenario === 'simple_win') {
            const winAmount = 250;
            mockResponseData = {
                status: true,
                data: {
                    result: {
                        final_spheres: this._generateMockSphereGrid(this.gridConfig.width, this.gridConfig.height, 'simple_win'),
                        win_amount_sats: winAmount,
                        winning_events: [{ type: 'cluster', spheres: [{r:1,c:0},{r:1,c:1},{r:1,c:2}], color: defaultColors[0] }],
                        harmony_event_triggered: false, is_cascade_active: true
                    },
                    win_amount: winAmount, winning_lines: [{ type: 'cluster', count: 3, symbol_id: defaultColors[0]}], bonus_triggered: false,
                    bonus_active: baseGameSession.bonus_active, bonus_spins_remaining: baseGameSession.bonus_spins_remaining,
                    bonus_multiplier: baseGameSession.bonus_multiplier,
                    game_session: { ...baseGameSession, amount_wagered: betAmount, amount_won: winAmount, num_spins: baseGameSession.num_spins + 1 },
                    user: { ...baseUser, balance: baseUser.balance - betAmount + winAmount }
                }
            };
        } else if (scenario === 'prism_win') { // Prism acts as multiplier here
            const baseWin = 150;
            const prismMultiplier = this.gameConfigData.config.prism_sphere_config?.multiplier_value || 2;
            const finalWin = baseWin * prismMultiplier;
            mockResponseData = {
                status: true,
                data: {
                    result: {
                        final_spheres: this._generateMockSphereGrid(this.gridConfig.width, this.gridConfig.height, 'prism_win'),
                        win_amount_sats: finalWin,
                        winning_events: [
                            { type: 'cluster', spheres: [{r:1,c:0},{r:1,c:1},{r:1,c:2}], color: defaultColors[0] },
                            { type: 'prism_multiplier_applied', position: {r:1,c:1}, multiplier: prismMultiplier }
                        ],
                        harmony_event_triggered: false, is_cascade_active: true
                    },
                    win_amount: finalWin, winning_lines: [{type: 'cluster_with_prism'}], bonus_triggered: false,
                    bonus_active: baseGameSession.bonus_active, bonus_spins_remaining: baseGameSession.bonus_spins_remaining,
                    bonus_multiplier: baseGameSession.bonus_multiplier,
                    game_session: { ...baseGameSession, amount_wagered: betAmount, amount_won: finalWin, num_spins: baseGameSession.num_spins + 1 },
                    user: { ...baseUser, balance: baseUser.balance - betAmount + finalWin }
                }
            };
        } else if (scenario === 'harmony_win') {
            const harmonyWinAmount = 5000;
            mockResponseData = {
                status: true,
                data: {
                    result: {
                        final_spheres: this._generateMockSphereGrid(this.gridConfig.width, this.gridConfig.height, 'harmony_pattern'),
                        win_amount_sats: harmonyWinAmount,
                        winning_events: [{ type: 'harmony', spheres: [{r:0, c:0},{r:0, c:1},{r:0, c:2},{r:0, c:3},{r:0, c:4}] }],
                        harmony_event_triggered: true, is_cascade_active: true
                    },
                    win_amount: harmonyWinAmount, winning_lines: [{ type: 'harmony' }], bonus_triggered: true,
                    bonus_active: baseGameSession.bonus_active, bonus_spins_remaining: baseGameSession.bonus_spins_remaining,
                    bonus_multiplier: baseGameSession.bonus_multiplier,
                    game_session: { ...baseGameSession, amount_wagered: betAmount, amount_won: harmonyWinAmount, num_spins: baseGameSession.num_spins + 1 },
                    user: { ...baseUser, balance: baseUser.balance - betAmount + harmonyWinAmount }
                }
            };
        }

        this.time.delayedCall(300, () => { // Simulate API delay
            if (mockResponseData && mockResponseData.status && mockResponseData.data) {
                EventBus.emit('symphony-spheres-pulse-result', mockResponseData.data);
            } else {
                EventBus.emit('show-error-message', mockResponseData?.data?.status_message || 'Mock pulse activation failed.');
                this.canSpin = true; this.pulseButton.setAlpha(1.0);
            }
        });
        // --- End Mocking ---
    }

    handlePulseResult(data) {
        console.log('Pulse result received:', data);
        this.currentPulseData = data;

        if (data.result?.harmony_event_triggered) {
            this.sound.play('harmony_event_sound', {volume: 0.9});
            this.playHarmonyEventAnimation(() => {
                this._processWinningEventsAndRedraw(data);
            });
        } else {
            this._processWinningEventsAndRedraw(data);
        }
    }

    _processWinningEventsAndRedraw(data) {
        const winningEvents = data.result?.winning_events || [];
        const finalSpheresGrid = data.result?.final_spheres;

        if (winningEvents.length > 0) {
            if(!data.result?.harmony_event_triggered) this.sound.play('win_event_sound', {volume: 0.6}); // Avoid double sound
            this.highlightAndRemoveWinningSpheres(winningEvents, finalSpheresGrid, () => {
                this._redrawGridWithNewSpheres(finalSpheresGrid);
            });
        } else if (finalSpheresGrid) {
            this._redrawGridWithNewSpheres(finalSpheresGrid);
        } else {
            this.initializeSphereField();
            this.finalizePulse();
        }
    }

    highlightAndRemoveWinningSpheres(winningEvents, finalSpheresGrid, onCompleteCallback) {
        let spheresToAnimateDetails = [];

        winningEvents.forEach(event => {
            const eventType = event.type;
            // For prism events, the 'position' field should contain {r, c}
            if ((eventType === 'prism_wild_activation' || eventType === 'prism_multiplier_applied') && event.position) {
                const prismSprite = this.getSphereAtGrid(event.position.r, event.position.c);
                if (prismSprite) spheresToAnimateDetails.push({sprite: prismSprite, eventType: eventType, isPrismEffect: true});
            }
            // For cluster/chain events, 'spheres' is an array of {r, c}
            if (event.spheres && Array.isArray(event.spheres)) {
                event.spheres.forEach(coord => {
                    const sphereSprite = this.getSphereAtGrid(coord.r, coord.c);
                    // Add only if not already added as a prism effect target (to avoid double animation)
                    if (sphereSprite && !spheresToAnimateDetails.some(d => d.sprite === sphereSprite && d.isPrismEffect)) {
                       spheresToAnimateDetails.push({sprite: sphereSprite, eventType: eventType, isPrismEffect: false});
                    }
                });
            }
        });

        const uniqueSpritesToAnimate = [...new Map(spheresToAnimateDetails.map(item => [item.sprite, item])).values()];

        if (uniqueSpritesToAnimate.length === 0) {
            if (onCompleteCallback) onCompleteCallback();
            return;
        }

        let tweensCompleted = 0;
        const totalTweens = uniqueSpritesToAnimate.length;

        uniqueSpritesToAnimate.forEach(({sprite, eventType, isPrismEffect}) => {
            if (!sprite || !sprite.active) {
                tweensCompleted++;
                if (tweensCompleted === totalTweens && onCompleteCallback) onCompleteCallback();
                return;
            }

            let timeline = this.tweens.createTimeline();

            if (isPrismEffect) {
                this.sound.play('prism_activate_sound', { volume: 0.7, detune: Phaser.Math.Between(-200, 0) });
                timeline.add({
                    targets: sprite, angle: 360, scale: sprite.scale * 1.3, yoyo: true, duration: 300, ease: 'Power1',
                    onStart: () => this.createPrismParticleEffect(sprite.x, sprite.y)
                });
            } else {
                 timeline.add({
                    targets: sprite, scale: sprite.scale * 1.2, yoyo: true, duration: 150, ease: 'Sine.easeInOut', repeat: 1
                });
            }

            timeline.add({
                targets: sprite, scale: 0, alpha: 0, duration: 300, ease: 'Power2',
                delay: isPrismEffect ? 100 : 0, // Slight delay if it was a prism so its own animation plays a bit
                onStart: () => {
                    if (!isPrismEffect) {
                        this.sound.play('sphere_disappear_sound', { volume: 0.5 });
                    }
                },
                onComplete: () => {
                    if (sprite.active) {
                        this.createParticleEffect(sprite.x, sprite.y);
                        this.spheresGroup.remove(sprite, true, true);
                        const gx = sprite.getData('gridX');
                        const gy = sprite.getData('gridY');
                        if (this.gridGameObjects[gy] && this.gridGameObjects[gy][gx] === sprite) {
                            this.gridGameObjects[gy][gx] = null;
                        }
                    }
                    tweensCompleted++;
                    if (tweensCompleted === totalTweens && onCompleteCallback) {
                        onCompleteCallback();
                    }
                }
            });
            timeline.play();
        });
    }

    _redrawGridWithNewSpheres(finalSpheresGrid) {
        this.gridGameObjects = Array(this.gridConfig.height).fill(null).map(() => Array(this.gridConfig.width).fill(null));
        this.spheresGroup.clear(true, true); // Clear all existing sprites before redrawing with final state

        const fallDuration = 500;
        let longestDelay = 0;
        let newSpheresAnimated = 0;
        let totalNewSpheres = 0;

        if (!Array.isArray(finalSpheresGrid)) { // Guard against bad data
            this.initializeSphereField(); this.finalizePulse(); return;
        }

        finalSpheresGrid.forEach((row, y) => {
            if (!Array.isArray(row)) return;
            totalNewSpheres += row.length; // Count total spheres to draw
            row.forEach((sphereData, x) => {
                if (!sphereData || typeof sphereData.color === 'undefined') return;

                const isPrism = sphereData.is_prism === true || sphereData.type === 'prism';
                const sphereTextureKey = this._getSphereTextureKey(sphereData.color, isPrism);
                const sphereX = this.gridConfig.startX + x * (this.gridConfig.sphereDiameter + this.gridConfig.padding) + this.gridConfig.sphereDiameter / 2;
                const targetY = this.gridConfig.startY + y * (this.gridConfig.sphereDiameter + this.gridConfig.padding) + this.gridConfig.sphereDiameter / 2;

                const sphere = this.add.sprite(sphereX, this.gridConfig.startY - this.gridConfig.sphereDiameter * (y + 1), sphereTextureKey);
                sphere.displayWidth = this.gridConfig.sphereDiameter;
                sphere.displayHeight = this.gridConfig.sphereDiameter;
                sphere.setAlpha(0);
                sphere.setData('gridX', x); sphere.setData('gridY', y); sphere.setData('isPrism', isPrism);
                this.spheresGroup.add(sphere);
                this.gridGameObjects[y][x] = sphere; // Store new sprite

                const delay = y * 60 + x * 15;
                if(delay > longestDelay) longestDelay = delay;

                this.tweens.add({
                    targets: sphere, y: targetY, alpha: 1, duration: fallDuration, ease: 'Bounce.easeOut', delay: delay,
                    onComplete: () => {
                        newSpheresAnimated++;
                        if (newSpheresAnimated === totalNewSpheres) {
                            this.sound.play('sphere_land_sound', { volume: 0.4 });
                            this.finalizePulse();
                        }
                    }
                });
            });
        });

        if (totalNewSpheres === 0) {
            this.finalizePulse();
        }
    }

    playHarmonyEventAnimation(onCompleteCallback) {
        const harmonyText = this.add.text(this.cameras.main.width / 2, this.cameras.main.height / 2, 'HARMONY!', { fontSize: '64px', fill: '#FFD700', stroke: '#000', strokeThickness: 4 })
            .setOrigin(0.5).setAlpha(0).setScale(0.5);
        this.tweens.add({
            targets: harmonyText,
            alpha: 1, scale: 1.2, duration: 500, ease: 'Bounce.easeOut',
            onComplete: () => this.time.delayedCall(2000, () => { harmonyText.destroy(); if (onCompleteCallback) onCompleteCallback(); })
        });
    }

    createParticleEffect(x, y) {
        let particles = this.add.particles('particle_glow');
        if (!particles || !particles.active) return;
        let emitter = particles.createEmitter({
            speed: { min: 60, max: 150 }, angle: { min: 0, max: 360 }, scale: { start: 0.5, end: 0 },
            alpha: { start: 0.8, end: 0 }, blendMode: 'ADD', lifespan: { min: 300, max: 600 },
            frequency: -1, quantity: 15
        });
        emitter.explode(15, x, y);
        this.time.delayedCall(1000, () => particles.destroy());
    }

    createPrismParticleEffect(x,y) {
        let particles = this.add.particles('prism_particle_spark');
        if (!particles || !particles.active) return;
        let emitter = particles.createEmitter({
            speed: { min: 80, max: 200 }, angle: { min: 0, max: 360 },
            scale: { start: 0.6, end: 0 }, alpha: { start: 1, end: 0 },
            tint: [0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff, 0x00ffff],
            blendMode: 'ADD', lifespan: { min: 400, max: 700 },
            frequency: -1, quantity: 25
        });
        emitter.explode(25, x, y);
        this.time.delayedCall(1200, () => particles.destroy());
    }

    finalizePulse() {
        this.canSpin = true;
        this.pulseButton.setAlpha(1.0);
        if (this.currentPulseData) {
            if (this.currentPulseData.user && this.currentPulseData.user.balance !== undefined) {
                EventBus.emit('update-balance', this.currentPulseData.user.balance);
            }
            if (this.currentPulseData.win_amount > 0 && !this.currentPulseData.result?.harmony_event_triggered) {
                EventBus.emit('show-win-message', `You won ${this.currentPulseData.win_amount} sats!`);
            }
        }
        this.currentPulseData = null;
    }

    update() { /* Game loop updates */ }

    shutdown() {
        console.log('SymphonySpheresScene shutdown');
        EventBus.off('symphony-spheres-pulse-result', this.handlePulseResult, this);
        if (this.spheresGroup) {
            this.spheresGroup.destroy(true, true);
            this.spheresGroup = null;
        }
        this.sphereColorMap.forEach(textureKey => {
            if (this.textures.exists(textureKey)) {
                this.textures.remove(textureKey);
            }
        });
        this.sphereColorMap.clear();
        this.gridGameObjects = [];
    }
}

[end of casino_fe/src/phaser/scenes/SymphonySpheresScene.js]
