import Phaser from 'phaser';
import RouletteBootScene from './scenes/RouletteBootScene';
import RoulettePreloadScene from './scenes/RoulettePreloadScene';
import RouletteScene from '../phaser/scenes/RouletteScene';

const defaultGameConfig = {
    gameTitle: 'Phaser Roulette',
    version: '1.0.0',
    wheel: {
        radius: 120,
        segments: 37, // European roulette (0-36)
        numbers: [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26],
        colors: {
            0: 'green',
            red: [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36],
            black: [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        }
    },
    table: {
        width: 600,
        height: 400,
        cellWidth: 40,
        cellHeight: 60
    },
    chips: {
        values: [1, 5, 25, 100, 500],
        colors: {
            1: 0xFFFFFF,    // White
            5: 0xFF4444,    // Red
            25: 0x44AA44,   // Green
            100: 0x4444FF,  // Blue
            500: 0x000000   // Black
        }
    },
    betting: {
        minBet: 1,
        maxBet: 1000,
        payouts: {
            straight: 35,      // Single number
            split: 17,         // Two numbers
            street: 11,        // Three numbers
            corner: 8,         // Four numbers
            sixLine: 5,        // Six numbers
            column: 2,         // Column bet
            dozen: 2,          // Dozen bet
            redBlack: 1,       // Red/Black
            evenOdd: 1,        // Even/Odd
            highLow: 1         // 1-18/19-36
        }
    },
    animations: {
        wheelSpin: {
            duration: 3000,
            easing: 'Power2'
        },
        ballSpin: {
            duration: 4000,
            easing: 'Power3'
        },
        chipPlace: {
            duration: 300,
            bounceHeight: 10
        }
    },
    audio: {
        enabled: true,
        volume: 0.5,
        sounds: {
            wheelSpin: 'wheel_spin.mp3',
            ballRoll: 'ball_roll.mp3',
            chipPlace: 'chip_place.mp3',
            win: 'win.mp3',
            lose: 'lose.mp3'
        }
    }
};

// Phaser game configuration
const phaserConfig = {
    type: Phaser.AUTO,
    width: 1000,
    height: 700,
    backgroundColor: '#0d5016',
    parent: 'phaser-roulette-container',
    scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH
    },
    render: {
        antialias: true,
        pixelArt: false
    },
    physics: {
        default: 'arcade',
        arcade: {
            gravity: { y: 0 },
            debug: false
        }
    },
    scene: [RouletteBootScene, RoulettePreloadScene, RouletteScene],
    gameConfig: defaultGameConfig
};

export default phaserConfig;
