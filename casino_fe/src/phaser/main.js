import Phaser from 'phaser';
import BootScene from './scenes/BootScene';
import GameScene from './scenes/GameScene';
import UIScene from './scenes/UIScene';
import SettingsModalScene from './scenes/SettingsModalScene';
import PreloadScene from './scenes/PreloadScene'; // Add PreloadScene

const config = {
  type: Phaser.AUTO, // Auto-detect renderer (WebGL or Canvas)
  width: 800,        // Base width
  height: 600,       // Base height
  backgroundColor: '#000000', // Black background outside game area
  parent: 'phaser-slot-machine', // ID of the DOM element to inject the canvas
  // Use SHOW_ALL scale mode: scales the game keeping aspect ratio, adds letterboxing if needed
  scale: {
    mode: Phaser.Scale.FIT, // FIT ensures it fits within the parent element
    autoCenter: Phaser.Scale.CENTER_BOTH, // Center the game canvas
    width: 800,  // Match base width
    height: 600, // Match base height
  },
  // Improve rendering quality
  render: {
    pixelArt: false, // Set to true if using pixel art assets
    antialias: true, // Smoother edges for vector graphics and scaled bitmaps
    antialiasGL: true, // Antialiasing for WebGL renderer
    // powerPreference: 'high-performance' // Request high performance GPU if available
  },
  physics: {
    default: 'arcade',
    arcade: {
      debug: false, // Set to true to see physics bodies and velocity vectors
      gravity: { y: 0 } // No gravity needed for a slot game usually
    },
  },
  // Define game scenes, order matters (first scene is started first)
  scene: [BootScene, PreloadScene, GameScene, UIScene, SettingsModalScene],

  // Prevent blur on resized textures (important for pixel art if pixelArt: true)
  // Mipmapping can cause blurriness when downscaling
  // Rouding pixels can prevent sub-pixel rendering issues
  // LERP interpolation is often smoother than NEAREST for non-pixel art
  // pipeline: { antialias: true }, // Redundant with render.antialias?
  // roundPixels: true, // Useful for pixel art to avoid sub-pixel aliasing
  // transparent: false, // Set to true if you need transparency behind the canvas

  // Game configuration settings accessible via this.sys.game.config
  gameTitle: 'Kingpin Casino Slot',
  gameVersion: '1.0',
  url: '', // Your game's URL if needed
  input: {
    // Configure input options if needed (e.g., disable context menu)
    // mouse: { preventDefaultWheel: true }
  },
   audio: {
    // Disable audio context until first user interaction (recommended for browsers)
    disableWebAudio: false, // Allow Web Audio
    // noAudio: false // Set to true to disable audio entirely for testing
  },
};

export default config;

