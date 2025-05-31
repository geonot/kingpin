import Phaser from 'phaser';
import BootScene from './scenes/BootScene';
import PreloadScene from './scenes/PreloadScene';
import GameScene from './scenes/GameScene';
import UIScene from './scenes/UIScene';

// Default game configuration
const defaultConfig = {
  // Card configuration
  cards: {
    suits: ['hearts', 'diamonds', 'clubs', 'spades'],
    values: ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
  },
  
  // Table rules
  rules: {
    blackjackPayout: 1.5,      // Blackjack pays 3:2
    dealerStandsOn: 'soft17',  // Dealer stands on soft 17
    doubleAfterSplit: true,    // Can double after split
    hitSplitAces: false,       // Cannot hit split aces
    maxSplitHands: 4,          // Maximum number of hands after splits
    insurance: true,           // Insurance offered
    surrenderAllowed: false    // Surrender not allowed
  },
  
  // Betting options
  settings: {
    betOptions: [10, 20, 50, 100, 200, 500, 1000, 2000, 5000], // Bet amounts in satoshis
    defaultBet: 100,           // Default bet amount
    minBet: 10,                // Minimum bet
    maxBet: 5000,              // Maximum bet
    chipValues: [10, 20, 50, 100, 500, 1000] // Chip denominations
  },
  
  // UI positions and styles
  ui: {
    balance: {
      position: { x: 150, y: 550 },
      style: { font: 'bold 24px Arial', color: '#ffffff', align: 'center' }
    },
    bet: {
      position: { x: 650, y: 550 },
      style: { font: 'bold 24px Arial', color: '#ffffff', align: 'center' }
    },
    win: {
      position: { x: 400, y: 550 },
      style: { font: 'bold 24px Arial', color: '#FFD700', align: 'center' }
    },
    buttons: {
      deal: { x: 400, y: 450 },
      hit: { x: 300, y: 450 },
      stand: { x: 400, y: 450 },
      double: { x: 500, y: 450 },
      split: { x: 600, y: 450 }
    }
  },
  
  // Card positions
  positions: {
    dealer: {
      x: 400,
      y: 150,
      spacing: 30
    },
    player: {
      x: 400,
      y: 350,
      spacing: 30,
      hands: {
        spacing: 200 // Spacing between split hands
      }
    }
  },
  
  // Animation settings
  animations: {
    dealSpeed: 300,           // Card deal animation duration in ms
    flipSpeed: 200,           // Card flip animation duration in ms
    moveSpeed: 300            // Card movement animation duration in ms
  }
};

// Phaser game configuration
const config = {
  type: Phaser.AUTO,
  width: 800,
  height: 600,
  backgroundColor: '#2d2d2d',
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH
  },
  physics: {
    default: 'arcade',
    arcade: {
      gravity: { y: 0 },
      debug: false
    }
  },
  scene: [BootScene, PreloadScene, GameScene, UIScene],
  // Callbacks will be set by the Vue component
  callbacks: {
    preBoot: null,
    postBoot: null
  },
  // Game-specific configuration
  gameConfig: defaultConfig
};

export default config;