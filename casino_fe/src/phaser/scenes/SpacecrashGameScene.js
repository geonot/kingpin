import Phaser from 'phaser';

export default class SpacecrashGameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SpacecrashGameScene' });
    this.rocket = null;
    // this.starsEmitter = null; // Example for particles
    this.currentMultiplier = 1.00;
    this.startTime = 0; // Phaser game time when current round started
    this.gameStarted = false; // Is the rocket currently flying?
    this.gameOver = false;    // Has the game crashed?
    // this.multiplierText = null; // Removed as Vue handles UI display
  }

  preload() {
    // Assets are loaded in PreloadScene
    console.log('SpacecrashGameScene: preload');
  }

  create() {
    console.log('SpacecrashGameScene: create');
    this.cameras.main.setBackgroundColor('#000022');

    this.rocket = this.add.sprite(this.cameras.main.width / 2, this.cameras.main.height - 50, 'rocket').setOrigin(0.5, 1);
    this.rocket.setVisible(false); // Initially hidden until game starts

    // Initialize game state variables
    this.gameStarted = false;
    this.gameOver = false;
    this.currentMultiplier = 1.00;
    this.startTime = 0;

    // Listen for game events from Vue (via registry)
    this.registry.events.on('START_GAME', this.startGame, this);
    this.registry.events.on('CRASH_AT', this.triggerExplosion, this);
    
    // Reset for a new round (e.g. if coming from a previous game)
    this.registry.events.on('RESET_GAME_VIEW', () => {
        this.gameOver = false;
        this.gameStarted = false;
        this.currentMultiplier = 1.00;
        this.rocket.setVisible(false).setPosition(this.cameras.main.width / 2, this.cameras.main.height - 50).setAlpha(1).setScale(1);
        // Stop any explosion animations if they were ongoing
        if (this.rocket.anims.exists('explodeAnim')) {
            this.rocket.anims.stop('explodeAnim');
        }
    }, this);
  }

  startGame(initialBetData) { // initialBetData might not be directly used here but good for event consistency
    console.log('SpacecrashGameScene: START_GAME event received', initialBetData);
    if (this.gameStarted || this.gameOver) { // Prevent starting if already started or over
        this.registry.events.emit('RESET_GAME_VIEW'); // Ensure clean state if re-starting quickly
    }

    this.gameStarted = true;
    this.gameOver = false;
    this.currentMultiplier = 1.00;
    this.startTime = this.time.now; // Use Phaser's internal time

    this.rocket.setVisible(true)
               .setPosition(this.cameras.main.width / 2, this.cameras.main.height - 50)
               .setAlpha(1)
               .setScale(1); // Reset scale if changed during explosion

    // Stop any previous explosion animation just in case
    if (this.rocket.anims.exists('explodeAnim')) {
        this.rocket.anims.stop('explodeAnim');
    }


    try {
      this.sound.play('rocket_launch', { volume: 0.5 });
    } catch (e) { console.warn("Could not play rocket_launch sound", e); }

    // this.multiplierText.setText('1.00x'); // Removed as Vue handles UI display
    this.events.emit('GAME_STARTED'); // Emit to UIScene
  }

  triggerExplosion({ crashPoint }) {
    console.log(`SpacecrashGameScene: CRASH_AT event received - Crash Point: ${crashPoint}`);
    if (this.gameOver) return; // Prevent multiple explosions

    this.gameOver = true;
    this.gameStarted = false;
    this.currentMultiplier = crashPoint; // Set final multiplier
    // this.multiplierText.setText(this.currentMultiplier.toFixed(2) + 'x'); // Removed as Vue handles UI display

    // Explosion animation
    // Assuming 'explosion' spritesheet has an animation key 'explodeAnim'
    if (!this.anims.exists('explodeAnim')) { // Define animation if not already defined
        this.anims.create({
            key: 'explodeAnim',
            frames: this.anims.generateFrameNumbers('explosion', { start: 0, end: 15 }), // Adjust frame count
            frameRate: 20,
            repeat: 0, // Play once
            hideOnComplete: true 
        });
    }
    
    // Play explosion at rocket's last position
    const explosionSprite = this.add.sprite(this.rocket.x, this.rocket.y, 'explosion').setOrigin(0.5, 0.5);
    explosionSprite.play('explodeAnim');
    explosionSprite.on('animationcomplete', () => {
        explosionSprite.destroy(); // Clean up sprite after animation
    });


    this.rocket.setVisible(false); // Hide original rocket

    try {
      this.sound.play('explosion_sound', { volume: 0.7 });
    } catch (e) { console.warn("Could not play explosion_sound", e); }

    this.events.emit('GAME_OVER', { crashPoint }); // Emit to UIScene
    this.registry.events.emit('PHASER_GAME_OVER', { crashPoint }); // Emit to Vue component
  }

  update(time, delta) {
    if (!this.gameStarted || this.gameOver) {
      return;
    }

    const elapsedSeconds = (time - this.startTime) / 1000;
    // Using the same formula as backend for consistency (1.00 * Math.pow(1.07, elapsedSeconds))
    // For a smoother visual update, can use a slightly different curve or ensure frequent updates.
    // The backend calculation is king for actual game outcome.
    // The handler uses: 1.00 * math.pow(1.015, elapsedSeconds * 5) -> 1.015^(elapsedSeconds*5)
    // Let's try to match that:
    let newMultiplier = 1.00 * Math.pow(1.015, elapsedSeconds * 5); 
    newMultiplier = Math.min(newMultiplier, 9999.00); // Cap it

    this.currentMultiplier = parseFloat(newMultiplier.toFixed(2));
    // this.multiplierText.setText(this.currentMultiplier.toFixed(2) + 'x'); // Removed as Vue handles UI display

    // Move rocket up - speed can increase with multiplier or time
    // Simple upward movement, adjust factor for desired speed
    // Example: rocket.y -= (base_speed + multiplier_factor * this.currentMultiplier) * (delta / 1000);
    this.rocket.y -= (1 + (this.currentMultiplier / 10)) * (delta / 16); // Adjust 16 for frame rate delta
    
    // Ensure rocket doesn't go off screen too fast (optional, or handle via camera)
    if (this.rocket.y < -this.rocket.height) {
      this.rocket.y = -this.rocket.height; // Keep it at top edge if it flies off
    }

    this.events.emit('MULTIPLIER_UPDATE', this.currentMultiplier); // Emit to UIScene
  }
}
