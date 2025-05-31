import Phaser from 'phaser';
import EventBus from '@/event-bus'; // For emitting setting changes

export default class SettingsModalScene extends Phaser.Scene {
  constructor() {
    super({ key: 'SettingsModalScene' });
    this.soundEnabled = true; // Default state
    this.turboEnabled = false; // Default state
  }

  init(data) {
    // Receive initial settings from UIScene or registry
    this.soundEnabled = data?.soundEnabled ?? this.game.registry.get('soundEnabled') ?? true;
    this.turboEnabled = data?.turboEnabled ?? this.game.registry.get('turboEnabled') ?? false;
  }

  create() {
    const centerX = this.cameras.main.width / 2;
    const centerY = this.cameras.main.height / 2;

    // 1. Semi-transparent background overlay
    const overlay = this.add.rectangle(centerX, centerY, this.cameras.main.width, this.cameras.main.height, 0x000000, 0.7);
    overlay.setInteractive(); // Prevent clicking through to scenes below
    overlay.on('pointerdown', () => { /* Optional: Close modal on overlay click? */ });

    // 2. Modal Background Panel
    const panelWidth = 400;
    const panelHeight = 300;
    // Use 9-slice sprite or graphics for a nicer panel
    const panel = this.add.graphics();
    panel.fillStyle(0x2a2a4a, 1); // Dark blue/purple background
    panel.lineStyle(3, 0xffd700, 1); // Gold border
    panel.fillRoundedRect(centerX - panelWidth / 2, centerY - panelHeight / 2, panelWidth, panelHeight, 10);
    panel.strokeRoundedRect(centerX - panelWidth / 2, centerY - panelHeight / 2, panelWidth, panelHeight, 10);
    panel.setDepth(1); // Ensure panel is above overlay

    // 3. Title
    this.add.text(centerX, centerY - panelHeight / 2 + 30, 'Settings', {
      font: 'bold 28px Arial',
      fill: '#FFD700', // Gold color
      align: 'center',
      stroke: '#000000',
      strokeThickness: 2
    }).setOrigin(0.5).setDepth(2);

    // 4. Close Button (Top Right)
    const closeButton = this.add.text(centerX + panelWidth / 2 - 25, centerY - panelHeight / 2 + 25, 'X', {
      font: 'bold 24px Arial',
      fill: '#ff6666', // Reddish color
      backgroundColor: '#444444',
      padding: { x: 8, y: 4 },
    }).setOrigin(0.5).setDepth(2).setInteractive({ useHandCursor: true });

    closeButton.on('pointerover', () => closeButton.setFill('#ff0000'));
    closeButton.on('pointerout', () => closeButton.setFill('#ff6666'));
    closeButton.on('pointerdown', () => {
      this.closeModal();
    });

    // 5. Settings Options
    const startY = centerY - 60;
    const spacingY = 70;
    const labelStyle = { font: '20px Arial', fill: '#eeeeee' };
    const valueStyle = { font: 'bold 20px Arial', fill: '#ffffff' };
    const toggleX = centerX + 80;

    // --- Sound Toggle ---
    this.add.text(centerX - 100, startY, 'Sound:', labelStyle).setOrigin(0, 0.5).setDepth(2);
    this.soundValueText = this.add.text(centerX, startY, this.soundEnabled ? 'ON' : 'OFF', valueStyle).setOrigin(0, 0.5).setDepth(2);
    const soundToggle = this.createToggleButton(toggleX, startY, this.soundEnabled, this.toggleSound);
    soundToggle.setDepth(2);

    // --- Turbo Spin Toggle ---
    this.add.text(centerX - 100, startY + spacingY, 'Turbo Spin:', labelStyle).setOrigin(0, 0.5).setDepth(2);
    this.turboValueText = this.add.text(centerX, startY + spacingY, this.turboEnabled ? 'ON' : 'OFF', valueStyle).setOrigin(0, 0.5).setDepth(2);
    const turboToggle = this.createToggleButton(toggleX, startY + spacingY, this.turboEnabled, this.toggleTurbo);
    turboToggle.setDepth(2);

    // --- Optional: Full Screen Button ---
     // this.add.text(centerX - 100, startY + spacingY * 2, 'Full Screen:', labelStyle).setOrigin(0, 0.5).setDepth(2);
     // const fsButton = this.add.text(centerX, startY + spacingY * 2, 'Toggle', valueStyle)
     //    .setOrigin(0, 0.5).setDepth(2).setInteractive({useHandCursor: true})
     //    .on('pointerdown', () => {
     //        if (this.scale.isFullscreen) { this.scale.stopFullscreen(); }
     //        else { this.scale.startFullscreen(); }
     //    });


    // Make the panel interactive to stop clicks propagating, but don't add actions here
    const panelInteractiveZone = this.add.zone(centerX, centerY, panelWidth, panelHeight).setInteractive();
    panelInteractiveZone.setDepth(0); // Behind elements but above overlay

     // Close modal if 'ESC' key is pressed
     this.input.keyboard.on('keydown-ESC', this.closeModal, this);
  }

  createToggleButton(x, y, initialState, callback) {
    const width = 60;
    const height = 30;
    const radius = height / 2;
    const grooveColor = initialState ? 0x4caf50 : 0x757575; // Green for ON, Gray for OFF
    const handleColor = 0xffffff; // White handle

    const groove = this.add.graphics().setDepth(1);
    groove.fillStyle(grooveColor, 1);
    groove.fillRoundedRect(x - width / 2, y - height / 2, width, height, radius);

    const handleX = initialState ? x + width / 2 - radius : x - width / 2 + radius;
    const handle = this.add.circle(handleX, y, radius - 3, handleColor).setDepth(2);

    // Add invisible interactive zone over the toggle
    const zone = this.add.zone(x, y, width, height).setInteractive({ useHandCursor: true });

    zone.on('pointerdown', () => {
      const newState = !this[`${callback.name.includes('Sound') ? 'sound' : 'turbo'}Enabled`]; // Check current state via variable name hack (improve this)
      callback.call(this, newState, groove, handle); // Call the specific toggle function
    });

    return { groove, handle, zone }; // Return parts if needed elsewhere
  }

  toggleSound(newState, groove, handle) {
    this.soundEnabled = newState;
    this.soundValueText.setText(this.soundEnabled ? 'ON' : 'OFF');
    this.updateToggleVisuals(this.soundEnabled, groove, handle);
    this.game.registry.set('soundEnabled', this.soundEnabled); // Update registry
    EventBus.$emit('soundSettingChanged', this.soundEnabled); // Notify other scenes/Vue
    // Apply sound change (mute/unmute master volume)
    this.sound.mute = !this.soundEnabled;
  }

  toggleTurbo(newState, groove, handle) {
    this.turboEnabled = newState;
    this.turboValueText.setText(this.turboEnabled ? 'ON' : 'OFF');
    this.updateToggleVisuals(this.turboEnabled, groove, handle);
    this.game.registry.set('turboEnabled', this.turboEnabled); // Update registry
    EventBus.$emit('turboSettingChanged', this.turboEnabled); // Notify other scenes/Vue
  }

  updateToggleVisuals(isOn, groove, handle) {
      const width = 60;
      const height = 30;
      const radius = height / 2;
      const targetX = isOn ? handle.x + width - 2 * radius : handle.x - width + 2 * radius;
      const grooveColor = isOn ? 0x4caf50 : 0x757575;

      // Animate handle position
      this.tweens.add({
          targets: handle,
          x: targetX,
          duration: 150,
          ease: 'Linear'
      });

      // Change groove color instantly (or tween color if desired)
      groove.clear();
      groove.fillStyle(grooveColor, 1);
      groove.fillRoundedRect(handle.x - targetX + (isOn ? -width/2 + radius : width/2 - radius) , handle.y - radius, width, height, radius); // Recalculate rect position based on handle's frame position
       // Re-calculate x for groove based on handle's current position and direction
      const grooveX = handle.x - (isOn ? (width / 2 - radius) : (-width / 2 + radius));
      groove.fillRoundedRect(grooveX - width / 2, handle.y - height / 2, width, height, radius);

  }


  closeModal() {
    // Clean up listeners specific to this scene before stopping
    this.input.keyboard.off('keydown-ESC', this.closeModal, this);
    // Resume the scenes that were paused (UIScene, GameScene)
    this.scene.resume('UIScene');
    this.scene.resume('GameScene');
    this.scene.stop(); // Stop this settings scene
  }
}


