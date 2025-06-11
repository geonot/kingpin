import Phaser from 'phaser';

export default class SpacecrashGameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SpacecrashGameScene' });
    this.rocket = null;
    this.stars = null;
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

    // Starfield
    this.stars = this.add.group();
    const starCount = 200; // Number of stars
    const gameWidth = this.cameras.main.width;
    const gameHeight = this.cameras.main.height;

    for (let i = 0; i < starCount; i++) {
      const x = Phaser.Math.Between(0, gameWidth);
      const y = Phaser.Math.Between(0, gameHeight);
      const size = Phaser.Math.Between(1, 3); // Star size
      const star = this.add.circle(x, y, size / 2, 0xffffff); // radius is size/2
      this.stars.add(star);
    }

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
    this.registry.events.on('PLAYER_SUCCESSFULLY_EJECTED', this.handlePlayerEjectedVisuals, this);
    
    // Reset for a new round (e.g. if coming from a previous game)
    this.handleResetGameView = this.handleResetGameView.bind(this); // Bind context for the handler
    this.registry.events.on('RESET_GAME_VIEW', this.handleResetGameView, this);
  }

  handleResetGameView() {
    console.log('SpacecrashGameScene: handleResetGameView');
    this.gameOver = false;
    this.gameStarted = false;
    this.currentMultiplier = 1.00;
    if (this.rocket) {
        this.rocket.setVisible(false)
                   .setPosition(this.cameras.main.width / 2, this.cameras.main.height - 50)
                   .setAlpha(1)
                   .setScale(1)
                   .clearTint(); // Ensure tint is cleared
        // Stop any explosion animations if they were ongoing
        if (this.rocket.anims.exists('explodeAnim')) {
            this.rocket.anims.stop('explodeAnim');
        }
    }
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
               .setScale(1) // Reset scale if changed during explosion
               .clearTint(); // Ensure tint is cleared

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
    explosionSprite.setScale(64); // Make the 1x1 animation more visible
    explosionSprite.play('explodeAnim');
    explosionSprite.on('animationcomplete', () => {
        explosionSprite.destroy(); // Clean up sprite after animation
    });

    this.cameras.main.flash(100, 255, 0, 0); // Flash red for 100ms

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
    
    // Rocket wobble
    // The initial x position is this.cameras.main.width / 2
    this.rocket.x = (this.cameras.main.width / 2) + Math.sin(time * 0.005) * 5; // Wobble 5 pixels left/right

    // Ensure rocket doesn't go off screen too fast (optional, or handle via camera)
    if (this.rocket.y < -this.rocket.height) {
      this.rocket.y = -this.rocket.height; // Keep it at top edge if it flies off
    }

    // Update stars
    const gameHeight = this.cameras.main.height;
    const gameWidth = this.cameras.main.width;
    this.stars.children.iterate((star) => {
      if (star) { // Check if star exists, as it might be destroyed elsewhere if needed
        star.y += star.radius * 0.1 * (delta / 16); // Move star based on its size and delta
        if (star.y > gameHeight + star.radius) {
          star.y = -star.radius;
          star.x = Phaser.Math.Between(0, gameWidth);
        }
      }
    });

    this.events.emit('MULTIPLIER_UPDATE', this.currentMultiplier); // Emit to UIScene
  }

  handlePlayerEjectedVisuals() {
    console.log('SpacecrashGameScene: PLAYER_SUCCESSFULLY_EJECTED event received');
    if (this.rocket && this.rocket.visible) {
      // Brief tint effect
      this.rocket.setTint(0x00ff00); // Green tint

      this.time.delayedCall(300, () => { // Duration of the tint
        if (this.rocket) { // Check if rocket still exists (scene might have changed)
          this.rocket.clearTint();
        }
      }, [], this);
    }

    try {
      this.sound.play('eject_sound', { volume: 0.6 });
    } catch (e) { console.warn("Could not play eject_sound", e); }

    // Potentially add other visual cues here, like a small "Ejected!" text popup
  }

  shutdown() {
    console.log('SpacecrashGameScene: shutdown');
    // Remove event listeners
    this.registry.events.off('START_GAME', this.startGame, this);
    this.registry.events.off('CRASH_AT', this.triggerExplosion, this);
    this.registry.events.off('PLAYER_SUCCESSFULLY_EJECTED', this.handlePlayerEjectedVisuals, this);
    this.registry.events.off('RESET_GAME_VIEW', this.handleResetGameView, this);

    // Clean up any other resources, like groups or timers, if necessary
    if (this.stars) {
      this.stars.destroy(true); // true for children and texture
      this.stars = null;
    }
    // Note: Rocket and explosion sprites are typically managed by their animations or direct destruction.
  }
}
