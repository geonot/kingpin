import Phaser from 'phaser';
import PokerBootScene from './scenes/PokerBootScene';
import PokerPreloadScene from './scenes/PokerPreloadScene';
import PokerGameScene from './scenes/PokerGameScene';
import PokerUIScene from './scenes/PokerUIScene';

const defaultConfig = {
    // Game configuration
    gameTitle: 'Texas Hold\'em Poker',
    version: '1.0.0',
    gameType: 'poker',
    
    // Table configuration
    table: {
        maxPlayers: 9,
        minPlayers: 2,
        tableType: 'cash',
        stakes: {
            smallBlind: 1,
            bigBlind: 2
        }
    },
    
    // Card configuration
    cards: {
        width: 80,
        height: 116,
        suits: ['hearts', 'diamonds', 'clubs', 'spades'],
        values: ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'],
        backTexture: 'card-back'
    },
    
    // Seat positions for 9-max table
    seatPositions: [
        { x: 400, y: 480, angle: 0, position: 'UTG' },      // Seat 1 (bottom center)
        { x: 200, y: 420, angle: -30, position: 'UTG+1' },  // Seat 2 (bottom left)
        { x: 100, y: 320, angle: -60, position: 'MP1' },    // Seat 3 (left)
        { x: 120, y: 200, angle: -90, position: 'MP2' },    // Seat 4 (top left)
        { x: 280, y: 120, angle: -120, position: 'MP3' },   // Seat 5 (top center left)
        { x: 520, y: 120, angle: 120, position: 'CO' },     // Seat 6 (top center right)
        { x: 680, y: 200, angle: 90, position: 'BTN' },     // Seat 7 (top right)
        { x: 700, y: 320, angle: 60, position: 'SB' },      // Seat 8 (right)
        { x: 600, y: 420, angle: 30, position: 'BB' }       // Seat 9 (bottom right)
    ],
    
    // UI configuration
    ui: {
        actionButtons: {
            fold: { text: 'Fold', color: 0xff4444, textColor: '#ffffff' },
            check: { text: 'Check', color: 0x44aa44, textColor: '#ffffff' },
            call: { text: 'Call', color: 0x44aa44, textColor: '#ffffff' },
            bet: { text: 'Bet', color: 0x4444ff, textColor: '#ffffff' },
            raise: { text: 'Raise', color: 0x4444ff, textColor: '#ffffff' },
            allIn: { text: 'All-In', color: 0xff8800, textColor: '#ffffff' }
        },
        chipValues: [1, 5, 25, 100, 500, 1000],
        chipColors: {
            1: 0xffffff,     // White
            5: 0xff4444,     // Red
            25: 0x44aa44,    // Green
            100: 0x000000,   // Black
            500: 0x800080,   // Purple
            1000: 0xffd700   // Gold
        }
    },
    
    // Animation settings
    animations: {
        cardDeal: {
            duration: 500,
            stagger: 150
        },
        chipAnimation: {
            duration: 300,
            bounce: 0.2
        },
        potCollection: {
            duration: 800,
            ease: 'Power2'
        }
    },
    
    // Audio configuration
    audio: {
        enabled: true,
        volume: 0.7,
        sounds: {
            cardDeal: 'card-deal',
            chipsBet: 'chips-bet',
            chipsPot: 'chips-pot',
            buttonClick: 'button-click',
            playerJoin: 'player-join',
            playerLeave: 'player-leave',
            newHand: 'new-hand',
            showdown: 'showdown'
        }
    },
    
    // Game rules
    rules: {
        maxRaises: 3,
        minRaise: 'bigBlind',
        autoMuck: true,
        showMuckCards: false,
        allInProtection: true
    }
};

// Phaser game configuration
const phaserConfig = {
    type: Phaser.AUTO,
    width: 800,
    height: 600,
    backgroundColor: '#0d4016',
    parent: 'poker-phaser-container',
    scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
        width: 800,
        height: 600
    },
    render: {
        antialias: true,
        pixelArt: false
    },
    scene: [PokerBootScene, PokerPreloadScene, PokerGameScene, PokerUIScene],
    physics: {
        default: 'arcade',
        arcade: {
            debug: false,
            gravity: { y: 0 }
        }
    }
};

export { defaultConfig, phaserConfig };
export default phaserConfig;
