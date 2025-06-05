import Phaser from 'phaser';

export default class UIScene extends Phaser.Scene {
    constructor() {
        super({ key: 'UIScene', active: false });
        this.eventBus = null;
        this.gameConfig = null;
        // betting state
        // this.currentBet = { player: 0, banker: 0, tie: 0, total: 0 };
        // this.selectedChipValue = 100; // default chip
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameConfig = this.registry.get('gameDefinition');
        // this.userBalance = this.registry.get('userBalance');
    }

    create() {
        // TODO: Create UI elements: betting spots, chips, buttons, text displays
        // Betting spots (Player, Banker, Tie) - make them interactive
        // Chip selection buttons
        // Deal/Rebet button, Clear Bet button
        // Balance, Current Bet, Last Win text displays

        // Example: Handle bet placement
        // const playerBetSpot = this.add.rectangle(...).setInteractive();
        // playerBetSpot.on('pointerdown', () => {
        //    this.placeBet('player', this.selectedChipValue);
        // });

        // Example: Handle "Deal" button click
        // const dealButton = this.add.text(...).setInteractive();
        // dealButton.on('pointerdown', () => {
        //    if (this.currentBet.total > 0) {
        //        this.eventBus.emit('blackjackDealRequest', { betAmount: this.currentBet.total }); // Adapt for Baccarat bets
        //    }
        // });

        // Listen for updates from GameScene or Vue (e.g., balance update)
        // this.eventBus.on('updateBalance', (newBalance) => { this.userBalance = newBalance; /* update text */ }, this);
    }

    // placeBet(area, amount) {
        // TODO: Update this.currentBet
        // Visually add chip to betting area
        // Update bet display text
    // }

    update() {
        // TODO: UI updates if any
    }
}
