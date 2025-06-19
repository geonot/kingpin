import Phaser from 'phaser';

export default class AstroMinerXScene extends Phaser.Scene {
    constructor() {
        super({ key: 'AstroMinerXScene' });
        this.vueComponent = null;
        this.expeditionId = null;
        this.initialAsteroidsData = []; // [{id: 1}, {id: 2}, ...]
        this.player = null;
        this.cursors = null;
        this.spaceKey = null;
        this.asteroidsGroup = null;
        this.scanRange = 150; // Pixels for scan
        this.isScanning = false; // Prevent multiple scan attempts
        this.laserBeamGfx = null;

        // HUD Text (managed by Phaser, updated from Vue data via update loop)
        this.timerText = null;
        this.haulText = null;
        this.statusPhaserText = null; // For general status messages within Phaser
    }

    init(data) {
        console.log('AstroMinerXScene init data:', data);
        this.vueComponent = data.vueComponent;
        this.expeditionId = data.expeditionId;
        this.initialAsteroidsData = data.initialAsteroids || [];
        this.input.keyboard.enabled = true; // Ensure keyboard is enabled on scene start/restart
        this.physics.resume();
    }

    preload() {
        console.log('AstroMinerXScene: Preloading assets...');
        // Visual assets
        this.load.image('space_background', '/assets/space/space_background.png'); // Assuming path relative to public
        this.load.image('player_ship', '/assets/space/ship.png');
        this.load.image('asteroid', '/assets/space/asteroid_placeholder.png'); // Using placeholder as 'asteroid.png' might be too specific
        this.load.image('laser_beam', '/assets/space/laser_beam_placeholder.png'); // Placeholder
        this.load.spritesheet('explosion', '/assets/space/explosion_spritesheet_placeholder.png', { frameWidth: 64, frameHeight: 64 });

        // Sound assets
        this.load.audio('laser_sound', ['/assets/sounds/laser_placeholder.ogg', '/assets/sounds/laser_placeholder.mp3']);
        this.load.audio('scan_success_sound', ['/assets/sounds/collect_placeholder.ogg', '/assets/sounds/collect_placeholder.mp3']);
        this.load.audio('scan_empty_sound', ['/assets/sounds/error_placeholder.ogg', '/assets/sounds/error_placeholder.mp3']);
        this.load.audio('scan_hazard_sound', ['/assets/sounds/warning_placeholder.ogg', '/assets/sounds/warning_placeholder.mp3']);
        this.load.audio('explosion_sound', ['/assets/sounds/explosion_placeholder.ogg', '/assets/sounds/explosion_placeholder.mp3']);
        this.load.audio('background_music', ['/assets/sounds/background_music_placeholder.mp3']);
    }

    create() {
        console.log('AstroMinerXScene: Creating scene objects for Expedition ID:', this.expeditionId);
        this.cameras.main.setBackgroundColor('#000020');

        // Background
        if (this.textures.exists('space_background')) {
            this.add.image(this.cameras.main.width / 2, this.cameras.main.height / 2, 'space_background').setDisplaySize(this.cameras.main.width, this.cameras.main.height);
        }

        // Player Ship
        const shipX = this.cameras.main.width / 2;
        const shipY = this.cameras.main.height - 70; // Positioned lower
        if (this.textures.exists('player_ship')) {
            this.player = this.physics.add.sprite(shipX, shipY, 'player_ship').setScale(0.4).setDepth(10);
        } else {
            this.player = this.physics.add.sprite(shipX, shipY, 'default'); // Phaser's default texture
            this.player.setDisplaySize(40,40).setTint(0x00ff00);
            console.warn("Player ship texture not found. Using default.");
        }
        this.player.setCollideWorldBounds(true);
        this.player.setDamping(true);
        this.player.setDrag(0.97);
        this.player.setMaxVelocity(250);


        // Controls
        this.cursors = this.input.keyboard.createCursorKeys();
        this.spaceKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);

        // Asteroid Group
        this.asteroidsGroup = this.physics.add.group();
        this.generateAsteroids(this.initialAsteroidsData);

        // Laser Graphics (for placeholder laser beam)
        this.laserBeamGfx = this.add.graphics().setDepth(5);

        // HUD Text (updated via `update` from Vue component's data)
        this.timerText = this.add.text(10, 10, 'Time: 00:00', { font: '16px Arial', fill: '#ffffff' }).setScrollFactor(0).setDepth(100);
        this.haulText = this.add.text(this.cameras.main.width - 150, 10, 'Haul: 0 sats', { font: '16px Arial', fill: '#ffffff', align: 'right' }).setOrigin(0,0).setScrollFactor(0).setDepth(100);
        this.statusPhaserText = this.add.text(this.cameras.main.width / 2, 20, 'Expedition Started!', { font: '18px Arial', fill: '#00ff00'}).setOrigin(0.5).setScrollFactor(0).setDepth(100);


        // Animations
        if (this.textures.exists('explosion')) {
            this.anims.create({
                key: 'explode_anim',
                frames: this.anims.generateFrameNumbers('explosion', { start: 0, end: 15 }), // Assuming 16 frames
                frameRate: 20,
                hideOnComplete: true
            });
        } else {
            console.warn("Explosion spritesheet not found.");
        }

        // Background Music
        if (this.sound.get('background_music')) {
             if (!this.sound.get('background_music').isPlaying) { // Play only if not already playing (e.g. on scene restart)
                this.sound.play('background_music', { loop: true, volume: 0.2 });
            }
        } else {
            console.warn("Background music not loaded.");
        }

        this.isScanning = false;
        this.input.keyboard.enabled = true;
        this.physics.resume();


        if (this.vueComponent && typeof this.vueComponent.phaserSceneReady === 'function') {
            this.vueComponent.phaserSceneReady(this);
        }
        console.log('AstroMinerXScene create complete.');
    }

    generateAsteroids(asteroidsData) {
        if (!asteroidsData || asteroidsData.length === 0) {
            console.warn("No initial asteroid data to display in Phaser.");
            return;
        }
        this.asteroidsGroup.clear(true, true); // Clear previous asteroids if any

        asteroidsData.forEach((asteroidInfo) => { // asteroidInfo is {id: X, ...other backend data}
            const x = Phaser.Math.Between(50, this.cameras.main.width - 50);
            const y = Phaser.Math.Between(50, this.cameras.main.height - 250); // Keep away from player start

            let asteroidSprite;
            if (this.textures.exists('asteroid')) {
                asteroidSprite = this.asteroidsGroup.create(x, y, 'asteroid');
                asteroidSprite.setScale(Phaser.Math.FloatBetween(0.3, 0.7));
            } else {
                asteroidSprite = this.asteroidsGroup.create(x,y, 'default');
                asteroidSprite.setDisplaySize(Phaser.Math.Between(30,60), Phaser.Math.Between(30,60)).setTint(0x888888);
                if(this.asteroidsGroup.getLength() <=1) console.warn("Asteroid texture not found. Using default.");
            }

            asteroidSprite.setData('id', asteroidInfo.id); // Store backend ID
            asteroidSprite.setData('scanned', false);
            asteroidSprite.setInteractive();
            asteroidSprite.setAngularVelocity(Phaser.Math.Between(-50, 50)); // Random rotation
            // asteroidSprite.setVelocity(Phaser.Math.Between(-20, 20), Phaser.Math.Between(-20, 20)); // Slow drift
            // asteroidSprite.setCollideWorldBounds(true);
            // asteroidSprite.setBounce(0.5);


            asteroidSprite.on('pointerover', () => { if(!asteroidSprite.getData('scanned')) asteroidSprite.setTint(0xaaaaff); });
            asteroidSprite.on('pointerout', () => { if(!asteroidSprite.getData('scanned')) asteroidSprite.clearTint(); });
            // Click to scan is removed, scanning is now spacebar based on proximity.
        });
    }

    update(time, delta) {
        if (!this.player || !this.input.keyboard.enabled) return;

        // Player movement
        const speed = 300;
        this.player.setVelocity(0);
        if (this.cursors.left.isDown) this.player.setVelocityX(-speed);
        else if (this.cursors.right.isDown) this.player.setVelocityX(speed);
        if (this.cursors.up.isDown) this.player.setVelocityY(-speed);
        else if (this.cursors.down.isDown) this.player.setVelocityY(speed);

        // Scan action
        if (Phaser.Input.Keyboard.JustDown(this.spaceKey)) {
            this.attemptScan();
        }

        // Update HUD from Vue component's data
        if (this.vueComponent) {
            const minutes = Math.floor(this.vueComponent.expeditionTimeLeft / 60);
            const seconds = this.vueComponent.expeditionTimeLeft % 60;
            this.timerText.setText(`Time: ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`);
            this.haulText.setText(`Haul: ${this.vueComponent.currentExpeditionHaul.toLocaleString()} sats`);
        }
    }

    attemptScan() {
        if (this.isScanning || !this.player) return;

        let closestAsteroid = null;
        let minDistance = this.scanRange;

        this.asteroidsGroup.getChildren().forEach(asteroid => {
            if (!asteroid.getData('scanned')) {
                const distance = Phaser.Math.Distance.Between(this.player.x, this.player.y, asteroid.x, asteroid.y);
                if (distance < minDistance) {
                    minDistance = distance;
                    closestAsteroid = asteroid;
                }
            }
        });

        if (closestAsteroid) {
            this.isScanning = true;
            closestAsteroid.setData('scanned', true); // Mark as "being scanned"
            this.statusPhaserText.setText(`Scanning asteroid ID: ${closestAsteroid.getData('id')}...`);

            // Play laser beam animation
            this.laserBeamGfx.clear();
            this.laserBeamGfx.lineStyle(2, 0x00ff00, 0.7); // Green laser
            this.laserBeamGfx.beginPath();
            this.laserBeamGfx.moveTo(this.player.x, this.player.y - this.player.height/2); // From ship's nose
            this.laserBeamGfx.lineTo(closestAsteroid.x, closestAsteroid.y);
            this.laserBeamGfx.strokePath();
            this.time.delayedCall(200, () => this.laserBeamGfx.clear());


            if (this.sound.get('laser_sound')) this.sound.play('laser_sound', {volume: 0.5});

            this.vueComponent.handleScanAsteroid(closestAsteroid.getData('id'))
                .then(apiResponse => { // apiResponse is what handleScanAsteroid in Vue resolves with
                    this.handleScanResult(closestAsteroid, apiResponse.scan_result); // scan_result is the asteroid data from API
                })
                .catch(error => {
                    console.error('Scan API call failed from Phaser for asteroid ID:', closestAsteroid.getData('id'), error);
                    this.statusPhaserText.setText(`Scan failed for ID: ${closestAsteroid.getData('id')}.`);
                    closestAsteroid.setData('scanned', false); // Allow retry
                    // Optionally add visual feedback for error here
                    closestAsteroid.setTint(0xff0000); // Temporary red tint for error
                    this.time.delayedCall(1000, () => closestAsteroid.clearTint());
                })
                .finally(() => {
                    this.isScanning = false;
                });
        } else {
            this.statusPhaserText.setText('No asteroids in scan range.');
            this.time.delayedCall(1500, () => {
                if(this.statusPhaserText.text === 'No asteroids in scan range.') this.statusPhaserText.setText('');
            });
        }
    }

    handleScanResult(asteroidSprite, scanApiData) {
        // scanApiData is expected to be: { value, type (asteroid_type), is_empty, is_hazard, id }
        if (!asteroidSprite || !asteroidSprite.active) { // Check if sprite is still valid (not destroyed)
            console.warn("Attempted to handle scan result for an invalid sprite.");
            return;
        }

        this.statusPhaserText.setText(`Scan of ${scanApiData.asteroid_type} complete.`);

        if (this.textures.exists('explosion') && this.anims.exists('explode_anim')) {
            const explosion = this.add.sprite(asteroidSprite.x, asteroidSprite.y, 'explosion').play('explode_anim');
            if(this.sound.get('explosion_sound')) this.sound.play('explosion_sound', {volume: 0.3});
        } else { // Fallback visual feedback
            const emitter = this.add.particles(0, 0, 'default', { // Assuming 'default' texture exists or use a specific small particle image
                frame: { frames: [ 'red', 'yellow', 'green', 'blue' ], cycle: true }, // Example particle colors if using a spritesheet for particles
                lifespan: 400,
                speed: { min: 150, max: 250 },
                scale: { start: 0.6, end: 0 },
                gravityY: 0, // No gravity in space
                blendMode: 'ADD', // Bright particles
                emitting: false
            });
            emitter.explode(30, asteroidSprite.x, asteroidSprite.y); // Explode 30 particles
            this.time.delayedCall(500, () => emitter.destroy());
        }


        let infoMsg = "";
        if (scanApiData.is_hazard) {
            asteroidSprite.setTint(0xff3333); // Bright Red for hazard
            if(this.sound.get('scan_hazard_sound')) this.sound.play('scan_hazard_sound');
            infoMsg = 'HAZARD!';
        } else if (scanApiData.is_empty) {
            asteroidSprite.setTint(0x777777); // Darker Gray for empty
             if(this.sound.get('scan_empty_sound')) this.sound.play('scan_empty_sound');
            infoMsg = 'Empty Rock';
        } else if (scanApiData.value > 0) {
            asteroidSprite.setTint(0x33ff33); // Bright Green for valuable
            if(this.sound.get('scan_success_sound')) this.sound.play('scan_success_sound');
            infoMsg = `+${scanApiData.value} sats (${scanApiData.asteroid_type})`;
        } else {
            asteroidSprite.setTint(0xaaaaaa); // Light gray for non-valuable, non-hazard, non-empty
            infoMsg = `${scanApiData.asteroid_type}`;
        }

        const infoText = this.add.text(asteroidSprite.x, asteroidSprite.y - 40, infoMsg, {
            font: '14px Arial',
            fill: '#ffffff',
            backgroundColor: 'rgba(0,0,0,0.5)',
            padding: {x:5, y:2}
        }).setOrigin(0.5).setDepth(20);
        this.time.delayedCall(2500, () => infoText.destroy());

        // Optionally, make the asteroid non-interactive or visually distinct permanently after scan
        asteroidSprite.disableInteractive(); // Already done in attemptScan's optimistic update.
        // asteroidSprite.setAlpha(0.6); // Keep it slightly visible but faded
        // Or destroy it if collected immediately
        // this.time.delayedCall(1000, () => asteroidSprite.destroy());
    }

    endExpedition() {
        console.log("AstroMinerXScene: Expedition ending command received.");
        this.statusPhaserText.setText("Expedition Over. Finalizing...");
        this.input.keyboard.enabled = false;
        this.physics.pause();

        if (this.sound.get('background_music') && this.sound.get('background_music').isPlaying) {
            this.sound.get('background_music').stop();
        }

        this.asteroidsGroup.getChildren().forEach(asteroid => {
            asteroid.disableInteractive();
            // Optionally, animate them drifting away or fading
            this.tweens.add({ targets: asteroid, alpha: 0, duration: 1000, delay: Math.random() * 500 });
        });
        if(this.player) {
            this.tweens.add({ targets: this.player, alpha: 0, y: this.player.y - 50, duration: 1500, onComplete: () => {
                if (this.player) this.player.destroy();
                this.player = null;
            }});
        }
        this.time.delayedCall(2000, () => {
             if (this.statusPhaserText) this.statusPhaserText.setText("Awaiting next launch command from mothership.");
        });
    }

    shutdown() {
        console.log("AstroMinerXScene: Shutting down resources...");
        if (this.sound.get('background_music') && this.sound.get('background_music').isPlaying) {
            this.sound.get('background_music').stop(); // Ensure music stops
        }
        this.input.keyboard.resetKeys(); // Important for re-entry

        // Destroy groups and game objects if not handled by scene restart process
        if (this.asteroidsGroup) this.asteroidsGroup.destroy(true, true);
        if (this.player) this.player.destroy();
        if (this.laserBeamGfx) this.laserBeamGfx.destroy();
        if (this.timerText) this.timerText.destroy();
        if (this.haulText) this.haulText.destroy();
        if (this.statusPhaserText) this.statusPhaserText.destroy();

        this.asteroidsGroup = null;
        this.player = null;
        this.laserBeamGfx = null;
        this.timerText = null;
        this.haulText = null;
        this.statusPhaserText = null;
        this.cursors = null;
        this.spaceKey = null;
        this.initialAsteroidsData = [];
        // this.vueComponent = null; // Keep vueComponent reference if scene might be reused
        this.isScanning = false;
        console.log("AstroMinerXScene: Shutdown complete.");
    }
}
