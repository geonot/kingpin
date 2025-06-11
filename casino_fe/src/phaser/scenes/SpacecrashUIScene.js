import Phaser from 'phaser';

export default class SpacecrashUIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SpacecrashUIScene', active: false });
    // Simplified - only handle internal game events, no UI rendering
    this.gameIsOver = true;
  }

  create() {
    console.log('SpacecrashUIScene: create - minimal UI scene for event handling');

    // Initialize state
    this.gameIsOver = true;

    // Listen for events from GameScene for internal coordination
    const gameScene = this.scene.get('SpacecrashGameScene');

    // Bind context for handlers
    this.handleGameStarted = this.handleGameStarted.bind(this);
    this.handleGameOver = this.handleGameOver.bind(this);
    this.handleResetUiView = this.handleResetUiView.bind(this);

    if (gameScene) { // It's good practice to check if scene exists
      gameScene.events.on('GAME_STARTED', this.handleGameStarted, this);
      gameScene.events.on('GAME_OVER', this.handleGameOver, this);
      // Note: RESET_GAME_VIEW is on gameScene.registry.events, not gameScene.events
      gameScene.registry.events.on('RESET_GAME_VIEW', this.handleResetUiView, this);
    } else {
      console.warn('SpacecrashUIScene: SpacecrashGameScene not found at create time.');
    }
  }

  handleGameStarted() {
    console.log('SpacecrashUIScene: GAME_STARTED event received');
    this.gameIsOver = false;
  }

  handleGameOver({ crashPoint }) {
    console.log('SpacecrashUIScene: GAME_OVER event received', crashPoint);
    this.gameIsOver = true;
  }

  handleResetUiView() {
    console.log('SpacecrashUIScene: RESET_GAME_VIEW event received by UI scene');
    this.gameIsOver = true;
  }

  update() {
    // Minimal update - most logic handled by Vue now
  }

  shutdown() {
    console.log('SpacecrashUIScene: shutdown');
    const gameScene = this.scene.get('SpacecrashGameScene');

    if (gameScene) {
      gameScene.events.off('GAME_STARTED', this.handleGameStarted, this);
      gameScene.events.off('GAME_OVER', this.handleGameOver, this);
      gameScene.registry.events.off('RESET_GAME_VIEW', this.handleResetUiView, this);
    }
    // No registry events were directly on this.registry.events to clean up
  }
}
