import Phaser from 'phaser';

export default class SpacecrashBootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SpacecrashBootScene' });
  }

  preload() {
    // Placeholder for any initial assets needed absolutely critical for the preloader itself
    // For example, a logo or a progress bar background for the PreloadScene
    // Often, this scene can be minimal.
    console.log('SpacecrashBootScene: preload');
  }

  create() {
    console.log('SpacecrashBootScene: create - starting PreloadScene');
    this.scene.start('SpacecrashPreloadScene');
  }
}
