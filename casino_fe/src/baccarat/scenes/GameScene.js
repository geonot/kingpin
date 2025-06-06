import Phaser from 'phaser';

export default class GameScene extends Phaser.Scene {
    constructor() {
        super('GameScene');
        this.eventBus = null;
        this.gameConfig = null;
    }

    init(data) {
        // Initialize data passed from Vue component via registry
        this.eventBus = this.registry.get('eventBus');
        this.gameConfig = this.registry.get('gameDefinition'); // From baccarat/main.js
        // this.tableAPIData = this.registry.get('tableAPIData');
    }

    /**
     * GameScene Event Emitters:
     * - phaserGameReady: Signals that Phaser components are initialized.
     * - outOfCards: When the deck runs out of cards.
     * - roundInProgress: When card dealing/animation starts.
     * - handResult: { playerHand, bankerHand, playerScore, bankerScore, winner } - After scores are calculated.
     * - roundConcluded: After all game logic for the round is finished and results are sent.
     *
     * GameScene Event Listeners:
     * - dealButtonPressed: { bets } - From UIScene, to start a new round.
     */
    create() {
        // Setup game table, card groups, initial state
        this.add.image(this.cameras.main.centerX, this.cameras.main.centerY, 'baccarat_table');

        this.initializeDeck(); // Client-side deck for now

        // TODO: BACKEND INTEGRATION: GameScene should listen for an event from the backend
        // (e.g., via Vue/WebSocket bridge) that provides the cards for Player and Banker.
        // This event would contain card details (suit, rank, frame, Baccarat value).
        // Example: this.eventBus.on('backendHandData', this.handleBackendHandData, this);
        // For now, using client-side event from UIScene to trigger dealing.
        this.eventBus.on('dealButtonPressed', this.startNewRound, this);

        this.eventBus.emit('phaserGameReady');
    }

    // TODO: BACKEND INTEGRATION: This method would be triggered by an event from the backend
    // after it has processed the bet and dealt the cards.
    // handleBackendHandData(data) {
    //     // data might look like: { playerHand: [{...}, {...}], bankerHand: [{...}, {...}], thirdCardRulesApplied: true/false, scores: {}, winner: '' }
    //     console.log("GameScene: Received hand data from backend", data);
    //     this.playerHand = data.playerHand;
    //     this.bankerHand = data.bankerHand;
    //
    //     // Clear existing cards on table
    //     this.playerCardSprites.forEach(sprite => sprite.destroy());
    //     this.playerCardSprites = [];
    //     this.bankerCardSprites.forEach(sprite => sprite.destroy());
    //     this.bankerCardSprites = [];
    //
    //     // Display cards received from backend
    //     // This would need a loop and potentially staggered display like in displayCard
    //     // this.playerHand.forEach((card, index) => this.displayCard(card, index, 'player', index*2));
    //     // this.bankerHand.forEach((card, index) => this.displayCard(card, index, 'banker', index*2+1));
    //
    //     // Backend provides scores and winner
    //     this.eventBus.emit('handResult', {
    //         playerHand: data.playerHand,
    //         bankerHand: data.bankerHand,
    //         playerScore: data.scores.player,
    //         bankerScore: data.scores.banker,
    //         winner: data.winner
    //     });
    //     this.eventBus.emit('roundConcluded', { winner: data.winner, playerScore: data.scores.player, bankerScore: data.scores.banker });
    // }

    initializeDeck() {
        // TODO: BACKEND INTEGRATION: The client-side deck and card dealing logic
        // (initializeDeck, dealInitialCards, shuffling etc.) will be replaced.
        // Cards will be dealt by the backend. GameScene will receive card data via events/API.
        this.deck = [
            { suit: 'spades', rank: 'A', value: 1, frame: 'spades_A' },
            { suit: 'hearts', rank: '2', value: 2, frame: 'hearts_2' },
            { suit: 'clubs', rank: 'K', value: 0, frame: 'clubs_K' },
            { suit: 'diamonds', rank: 'J', value: 0, frame: 'diamonds_J' },
            { suit: 'spades', rank: '7', value: 7, frame: 'spades_7' },
            { suit: 'hearts', rank: '8', value: 8, frame: 'hearts_8' },
            { suit: 'diamonds', rank: 'Q', value: 0, frame: 'diamonds_Q' },
            { suit: 'clubs', rank: '3', value: 3, frame: 'clubs_3' },
            { suit: 'spades', rank: '9', value: 9, frame: 'spades_9' },
            { suit: 'hearts', rank: 'K', value: 0, frame: 'hearts_K' },
        ];
        // In a real game, you'd shuffle the deck here. For now, fixed order for predictability.
        // Phaser.Utils.Array.Shuffle(this.deck);

        this.playerHand = [];
        this.bankerHand = [];
        this.playerCardSprites = [];
        this.bankerCardSprites = [];
    }

    startNewRound(betData) {
        console.log('GameScene: Starting new round with client-side bets:', betData);

        // Clear cards from the previous round
        this.playerHand = [];
        this.bankerHand = [];
        this.playerCardSprites.forEach(sprite => sprite.destroy());
        this.playerCardSprites = []; // Reset array
        this.bankerCardSprites.forEach(sprite => sprite.destroy());
        this.bankerCardSprites = []; // Reset array

        // Clear any score displays or messages from previous round (these would be Phaser Text objects)
        // e.g., this.playerScoreText.setText(''); this.bankerScoreText.setText(''); this.resultText.setText('');

        // Re-initialize deck if it's empty (for testing purposes with client-side deck)
        if (this.deck.length < 4) {
            console.warn("GameScene: Deck is low, re-initializing for testing.");
            this.initializeDeck();
        }

        this.dealInitialCards(); // Client-side dealing
    }

    dealInitialCards() {
        // TODO: BACKEND INTEGRATION: This entire method will be replaced by logic
        // that waits for and processes card data from the backend.
        if (this.deck.length < 4) {
            console.error("Not enough cards in deck to deal.");
            this.eventBus.emit('outOfCards'); // Notify UI
            return;
        }

        // Deal cards: Player 1st, Banker 1st, Player 2nd, Banker 2nd
        this.playerHand.push(this.deck.pop());
        this.bankerHand.push(this.deck.pop());
        this.playerHand.push(this.deck.pop());
        this.bankerHand.push(this.deck.pop());

        // Display cards
        this.displayCard(this.playerHand[0], 0, 'player', 0); // Player card 1
        this.time.delayedCall(200, () => this.displayCard(this.bankerHand[0], 0, 'banker', 1)); // Banker card 1
        this.time.delayedCall(400, () => this.displayCard(this.playerHand[1], 1, 'player', 2)); // Player card 2
        this.time.delayedCall(600, () => {
            this.displayCard(this.bankerHand[1], 1, 'banker', 3); // Banker card 2
            console.log("GameScene: Initial cards dealt (client-side). Player:", this.playerHand, "Banker:", this.bankerHand);
            this.eventBus.emit('roundInProgress'); // Notify UI to disable controls
            this.determineOutcome(); // Client-side outcome calculation
        });
    }

    calculateBaccaratScore(hand) {
        // TODO: BACKEND INTEGRATION: Baccarat score calculation, third-card drawing rules,
        // and final winner determination will ideally be handled by the backend.
        // This function would be deprecated if backend sends final scores.
        // If backend only sends cards, this remains, and third-card logic needs full implementation.
        let score = 0;
        hand.forEach(card => {
            score += card.value;
        });
        return score % 10;
    }

    determineOutcome() {
        // TODO: BACKEND INTEGRATION: This method (or its parts like score calculation and winner logic)
        // will be replaced if the backend determines the full outcome.
        // If backend only provides cards, this method needs full Baccarat third-card rules.
        const playerScore = this.calculateBaccaratScore(this.playerHand);
        const bankerScore = this.calculateBaccaratScore(this.bankerHand);

        let winner = '';
        // Simplified Baccarat rules (Naturals, then simple comparison - no third card logic)
        if (playerScore >= 8 || bankerScore >= 8) { // Natural check
            if (playerScore > bankerScore) winner = 'Player';
            else if (bankerScore > playerScore) winner = 'Banker';
            else winner = 'Tie';
        } else { // No naturals, compare scores (no third cards drawn in this version)
            if (playerScore > bankerScore) winner = 'Player';
            else if (bankerScore > playerScore) winner = 'Banker';
            else winner = 'Tie';
        }

        console.log(`GameScene: Player Score: ${playerScore}, Banker Score: ${bankerScore}, Winner: ${winner} (client-calculated)`);

        this.eventBus.emit('handResult', {
            playerHand: [...this.playerHand], // Send copies
            bankerHand: [...this.bankerHand],
            playerScore: playerScore,
            bankerScore: bankerScore,
            winner: winner
        });

        // Signal that GameScene has completed its processing for the round.
        // UIScene will use this to re-enable betting controls.
        this.eventBus.emit('roundConcluded', { winner: winner, playerScore: playerScore, bankerScore: bankerScore });
    }

    displayCard(cardData, cardIndex, handType, positionIndex) {
        // Basic positioning - adjust as needed for your table layout
        const cardSpacing = 80; // Horizontal spacing between cards
        const playerXStart = this.cameras.main.centerX - cardSpacing * 1.5;
        const bankerXStart = this.cameras.main.centerX + cardSpacing * 0.5;
        const cardY = this.cameras.main.centerY - 50; // Y position for cards

        let x, y = cardY;

        if (handType === 'player') {
            x = playerXStart + cardIndex * cardSpacing;
        } else { // banker
            x = bankerXStart + cardIndex * cardSpacing;
        }

        // Placeholder for card back if needed, then reveal
        // const cardSprite = this.add.image(x, y, 'cards_atlas', 'card_back');
        // this.time.delayedCall(100 * positionIndex, () => { // Stagger reveal
        // cardSprite.setTexture('cards_atlas', cardData.frame); // Reveal if started with card_back
        // });
        const cardSprite = this.add.image(x, y, 'cards_atlas', cardData.frame);
        cardSprite.setScale(0.8);

        if (handType === 'player') {
            this.playerCardSprites.push(cardSprite);
        } else {
            this.bankerCardSprites.push(cardSprite);
        }
    }

    update() {
        // Game loop updates if any (e.g., continuous animations not handled by tweens)
    }
}
