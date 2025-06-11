import Phaser from 'phaser';

export default class SpacecrashPreloadScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SpacecrashPreloadScene' });
  }

  preload() {
    console.log('SpacecrashPreloadScene: preload');

    // Display a loading message or progress bar
    const { width, height } = this.cameras.main;
    const loadingText = this.make.text({
      x: width / 2,
      y: height / 2 - 50,
      text: 'Loading...',
      style: {
        font: '20px monospace',
        fill: '#ffffff'
      }
    });
    loadingText.setOrigin(0.5, 0.5);

    const percentText = this.make.text({
        x: width / 2,
        y: height / 2,
        text: '0%',
        style: {
            font: '18px monospace',
            fill: '#ffffff'
        }
    });
    percentText.setOrigin(0.5, 0.5);

    this.load.on('progress', (value) => {
        percentText.setText(parseInt(value * 100) + '%');
    });

    this.load.on('complete', () => {
        loadingText.destroy();
        percentText.destroy();
        console.log('SpacecrashPreloadScene: asset loading complete');
    });

    // Placeholder for loading game assets:
    // Images
    // this.load.image('rocket', 'assets/images/rocket.png');
    // this.load.image('particle_star', 'assets/images/star_particle.png');
    // this.load.spritesheet('explosion', 'assets/spritesheets/explosion.png', { frameWidth: 64, frameHeight: 64 });
    
    // Sounds
    // this.load.audio('rocket_launch', 'assets/sounds/launch.mp3');
    // this.load.audio('explosion_sound', 'assets/sounds/explosion.wav');
    // this.load.audio('bet_placed_sound', 'assets/sounds/bet.mp3');
    // this.load.audio('eject_sound', 'assets/sounds/eject.mp3');

    // UI elements (if any are images/spritesheets)
    // this.load.image('button_background', 'assets/ui/button_bg.png');

    // For now, let's load a placeholder image to test the loader
    // this.load.image('logo', 'https://labs.phaser.io/assets/sprites/phaser3-logo.png'); // Example asset

    // Load game assets
    this.load.image('rocket', 'assets/space/rocket.png');
    this.load.spritesheet('explosion', 'assets/space/explosion.png', { frameWidth: 1, frameHeight: 1 });

    // Load sound effects (placeholder paths)
    this.load.audio('rocket_launch', ['assets/sounds/launch.mp3', 'assets/sounds/launch.ogg']); // Provide multiple formats for compatibility
    this.load.audio('explosion_sound', ['assets/sounds/explosion.mp3', 'assets/sounds/explosion.ogg']);
    this.load.audio('eject_sound', ['assets/sounds/eject.mp3', 'assets/sounds/eject.ogg']);
  }

  create() {
    console.log('SpacecrashPreloadScene: create - starting GameScene and UIScene');
    // Start the main game scene
    this.scene.start('SpacecrashGameScene');
    // Launch the UI scene to run in parallel
    this.scene.launch('SpacecrashUIScene');
  }
}
