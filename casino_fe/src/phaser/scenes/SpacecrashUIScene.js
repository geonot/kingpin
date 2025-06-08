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

    gameScene.events.on('GAME_STARTED', () => {
      console.log('SpacecrashUIScene: GAME_STARTED event received');
      this.gameIsOver = false;
    }, this);

    gameScene.events.on('GAME_OVER', ({ crashPoint }) => {
      console.log('SpacecrashUIScene: GAME_OVER event received', crashPoint);
      this.gameIsOver = true;
    }, this);

    // Listen for RESET_GAME_VIEW from GameScene
    gameScene.registry.events.on('RESET_GAME_VIEW', () => {
      console.log('SpacecrashUIScene: RESET_GAME_VIEW event received');
      this.gameIsOver = true;
    }, this);

    // Listen for Vue-initiated eject requests and forward them
    this.registry.events.on('VUE_EJECT_REQUEST', () => {
      console.log('SpacecrashUIScene: VUE_EJECT_REQUEST received, forwarding to Vue');
      this.registry.events.emit('PLAYER_EJECT');
    }, this);
  }

  update() {
    // Minimal update - most logic handled by Vue now
  }
}
