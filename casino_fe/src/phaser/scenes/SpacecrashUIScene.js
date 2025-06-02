import Phaser from 'phaser';

export default class SpacecrashUIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SpacecrashUIScene', active: false }); // Set active: false if launched, true if started
    // this.gameInfoText = null; // Example for other UI text elements
    // this.playerBetsText = null;
    this.multiplierText = null; // This scene's own multiplier display
    this.ejectButton = null;
    this.gameIsOver = true; // Game starts in a "not running" state for UI
  }

  create() {
    console.log('SpacecrashUIScene: create');

    // Multiplier display (can be different style/position from GameScene's)
    this.multiplierText = this.add.text(
      this.cameras.main.width - 10, 
      10, 
      '1.00x', 
      { 
        fontSize: '24px', 
        fill: '#00ff00', // Green for emphasis
        fontFamily: 'Arial, sans-serif',
        align: 'right',
        stroke: '#000000',
        strokeThickness: 3
      }
    ).setOrigin(1, 0); // Align to top-right

    // Eject Button
    this.ejectButton = this.add.text(
      this.cameras.main.width / 2, 
      this.cameras.main.height - 40, // Positioned lower part of the screen
      'EJECT', 
      { 
        fontSize: '28px', 
        fill: '#00ff00', 
        backgroundColor: '#333333', 
        padding: { x: 20, y: 10 },
        fontFamily: 'Arial Black, sans-serif', // Bolder font
        stroke: '#000000',
        strokeThickness: 2
      }
    ).setOrigin(0.5).setInteractive({ useHandCursor: true });

    this.ejectButton.on('pointerdown', () => {
      if (!this.gameIsOver) { // Only allow eject if game is running
        console.log('SpacecrashUIScene: Eject button clicked');
        this.registry.events.emit('PLAYER_EJECT'); // Emit event for Vue component to handle API call
        this.ejectButton.setVisible(false); // Hide button immediately after click
        // Optionally play an eject sound directly here or wait for Vue confirmation
        // try { this.sound.play('eject_sound', { volume: 0.4 }); } catch (e) { console.warn("Could not play eject_sound", e); }
      }
    });
    this.ejectButton.setVisible(false); // Initially hidden

    // Initialize state
    this.gameIsOver = true;

    // Listen for events from GameScene
    const gameScene = this.scene.get('SpacecrashGameScene');

    gameScene.events.on('MULTIPLIER_UPDATE', (multiplier) => {
      if (!this.gameIsOver) { // Only update if game is active
        this.multiplierText.setText(multiplier.toFixed(2) + 'x');
      }
    }, this);

    gameScene.events.on('GAME_STARTED', () => {
      console.log('SpacecrashUIScene: GAME_STARTED event received');
      this.ejectButton.setVisible(true);
      this.gameIsOver = false;
      this.multiplierText.setText('1.00x').setFill('#00ff00'); // Reset color to green
    }, this);

    gameScene.events.on('GAME_OVER', ({ crashPoint }) => {
      console.log('SpacecrashUIScene: GAME_OVER event received', crashPoint);
      this.ejectButton.setVisible(false);
      this.gameIsOver = true;
      this.multiplierText.setText('CRASHED @ ' + crashPoint.toFixed(2) + 'x').setFill('#ff0000'); // Red color for crash
    }, this);

    // Listen for RESET_GAME_VIEW from GameScene (which might be triggered by Vue)
     gameScene.registry.events.on('RESET_GAME_VIEW', () => {
        console.log('SpacecrashUIScene: RESET_GAME_VIEW event received');
        this.multiplierText.setText('1.00x').setFill('#00ff00');
        this.ejectButton.setVisible(false);
        this.gameIsOver = true;
    }, this);
  }

  // updateGameInfo(gameData) { ... } // Placeholder if more complex UI text needed
  // updatePlayerBets(bets) { ... } // Placeholder

  update() {
    // The UI elements are mostly event-driven from GameScene or Vue.
  }
}
