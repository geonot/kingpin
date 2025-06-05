import Phaser from 'phaser';

// Import scenes - these files will be created in the next steps
import BootScene from './scenes/BootScene';
import PreloadScene from './scenes/PreloadScene';
import GameScene from './scenes/GameScene';
import UIScene from './scenes/UIScene';

const defaultGameConfig = {
    gameTitle: 'Phaser Baccarat',
    version: '0.0.1',
    cards: {
        width: 100, // Example card width
        height: 140, // Example card height
        atlas: 'cards', // Assuming a texture atlas named 'cards'
        suits: ['H', 'D', 'C', 'S'], // Hearts, Diamonds, Clubs, Spades
        values: ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K']
    },
    table: {
        width: 1200, // Example table background width
        height: 800, // Example table background height
    },
    positions: {
        playerCards: { x: 400, y: 600, spacing: 120, maxCards: 3 },
        bankerCards: { x: 400, y: 200, spacing: 120, maxCards: 3 },
        shoe: { x: 1050, y: 150 },
        discardPile: { x: 150, y: 150 },
        bettingSpots: {
            player: { x: 400, y: 450, width: 150, height: 100, label: "PLAYER" },
            banker: { x: 600, y: 450, width: 150, height: 100, label: "BANKER" },
            tie:    { x: 800, y: 450, width: 150, height: 100, label: "TIE" }
        },
        chipPlacementArea: { // Area where player's committed chips for a bet are shown
            player: { x: 400, y: 400 },
            banker: { x: 600, y: 400 },
            tie:    { x: 800, y: 400 }
        },
        scoreDisplay: {
            player: { x: 400, y: 700, style: { fontSize: '32px', fill: '#fff' } },
            banker: { x: 400, y: 100, style: { fontSize: '32px', fill: '#fff' } }
        },
        messageDisplay: { x: 600, y: 350, style: { fontSize: '48px', fill: '#ff0', stroke: '#000', strokeThickness: 4 } } // For "Player Wins", "Banker Wins", "Tie"
    },
    ui: {
        balanceText: { position: { x: 100, y: 50 }, style: { fontSize: '24px', fill: '#fff' } },
        totalBetText: { position: { x: 100, y: 80 }, style: { fontSize: '24px', fill: '#fff' } },
        winText: { position: { x: 600, y: 50 }, style: { fontSize: '28px', fill: '#ffd700' } },
        chipStackArea: { x: 150, y: 700, spacing: 80 }, // Where available chips are shown
        buttonPositions: {
            deal: { x: 1050, y: 700 },
            clear: { x: 900, y: 700 },
            // Rebet could be added if logic supports it
        }
    },
    animations: {
        dealSpeed: 250, // ms per card
        chipSpeed: 200, // ms for chip movement
        cardFlipSpeed: 150 // ms for card flip
    },
    betting: {
        chipValues: [100, 500, 1000, 5000, 10000], // Satoshi values
        // minBet and maxBet will typically come from tableInfo passed from Vue
        defaultMinBet: 100,
        defaultMaxBet: 100000,
        defaultMaxTieBet: 10000
    },
    sounds: {
        dealCard: 'dealCardSound',
        chipPlace: 'chipPlaceSound',
        cardFlip: 'cardFlipSound',
        win: 'winSound',
        lose: 'loseSound',
        push: 'pushSound', // For tie pushes if specific sound needed
        buttonClick: 'buttonClickSound'
    },
    timeouts: {
        showOutcomeMessage: 3000 // ms to show "Player Wins" etc.
    }
};

const config = {
    type: Phaser.AUTO,
    width: defaultGameConfig.table.width,  // Use table width for game width
    height: defaultGameConfig.table.height, // Use table height for game height
    backgroundColor: '#2c522d', // A dark green, common for card tables
    parent: 'phaser-baccarat-container', // Default parent, Vue will override
    scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
    },
    physics: { // Basic physics, might not be heavily used but good to have
        default: 'arcade',
        arcade: {
            gravity: { y: 0 },
            debug: false // Set to true for debugging physics bodies
        }
    },
    scene: [
        BootScene,
        PreloadScene,
        GameScene,
        UIScene
    ],
    callbacks: {
        preBoot: null, // Vue component will set this if needed
        postBoot: null // Vue component will set this if needed
    },
    gameConfig: defaultGameConfig // Embed Baccarat specific configurations
};

export default config;
