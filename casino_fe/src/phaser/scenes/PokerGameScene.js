import Phaser from 'phaser';

export default class PokerGameScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PokerGameScene' });
        
        // Game state
        this.gameState = null;
        this.eventBus = null;
        this.tableAPIData = null;
        this.gameConfig = null;
        
        // Game objects
        this.tableImage = null;
        this.communityCards = [];
        this.playerSeats = [];
        this.potText = null;
        this.gameInfoText = null;
        this.dealerButton = null;
        this.currentPlayerIndicator = null;
        
        // Card animation
        this.dealerPosition = { x: 400, y: 150 };
        this.animationQueue = [];
        this.isAnimating = false;
        
        // Game state tracking
        this.currentHand = null;
        this.communityCardCount = 0;
        this.currentBettingRound = null;
        
        // Seat positions (9-max table)
        this.seatPositions = [
            { x: 400, y: 450, angle: 0 },      // Seat 1 (bottom center)
            { x: 200, y: 400, angle: -30 },   // Seat 2 (bottom left)
            { x: 100, y: 300, angle: -60 },   // Seat 3 (left)
            { x: 150, y: 200, angle: -90 },   // Seat 4 (top left)
            { x: 300, y: 120, angle: -120 },  // Seat 5 (top center left)
            { x: 500, y: 120, angle: 120 },   // Seat 6 (top center right)
            { x: 650, y: 200, angle: 90 },    // Seat 7 (top right)
            { x: 700, y: 300, angle: 60 },    // Seat 8 (right)
            { x: 600, y: 400, angle: 30 }     // Seat 9 (bottom right)
        ];
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameState = this.registry.get('gameState');
        this.tableAPIData = this.registry.get('tableData');
        this.gameConfig = this.registry.get('gameDefinition');
    }

    create() {
        console.log('PokerGameScene: create()');
        
        // Initialize enhancement systems
        this.initializeEnhancements();
        
        this.setupTable();
        this.setupSeats();
        this.setupCommunityArea();
        this.setupUI();
        this.setupEventListeners();
        
        if (this.gameState) {
            this.updateGameDisplay(this.gameState);
        }
        
        // Apply poker-specific enhancements
        this.gameIntegrator.enhancePokerGame(this);
        
        console.log('PokerGameScene: Ready');
    }

    initializeEnhancements() {
        this.gameEnhancer = new GameEnhancer(this);
        this.gameIntegrator = new CasinoGameIntegrator(this);
        this.soundManager = new SoundManager(this);
        
        console.log('PokerGameScene: Enhancement systems initialized');
    }

    setupTable() {
        // Table background with enhancement
        this.tableImage = this.add.image(400, 300, 'poker-table').setOrigin(0.5);
        
        // Add subtle glow effect to table
        this.gameEnhancer.addGlowEffect(this.tableImage, 0x228B22, 0.3);
        
        // Dealer button with animation
        this.dealerButton = this.add.circle(0, 0, 15, 0xFFD700)
            .setVisible(false)
            .setStrokeStyle(2, 0x000000);
            
        const dealerText = this.add.text(0, 0, 'D', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#000000',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Add subtle pulse animation to dealer button
        this.gameEnhancer.addPulseAnimation(this.dealerButton, 1.1, 800);
        
        // Community card area enhancement
        this.communityCardArea = this.add.rectangle(400, 300, 300, 100, 0x228B22, 0.1)
            .setStrokeStyle(2, 0xFFD700, 0.5);
    }

    setupSeats() {
        this.seatPositions.forEach((pos, index) => {
            const seatData = {
                index: index + 1,
                position: pos,
                container: this.add.container(pos.x, pos.y),
                playerInfo: null,
                cards: [],
                actionText: null,
                isEmpty: true
            };
            
            // Seat placeholder
            const seatCircle = this.add.circle(0, 0, 50, 0x333333, 0.5)
                .setStrokeStyle(2, 0x666666);
            seatData.container.add(seatCircle);
            
            // Seat number
            const seatLabel = this.add.text(0, 0, `${index + 1}`, {
                fontSize: '16px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            seatData.container.add(seatLabel);
            
            this.playerSeats.push(seatData);
        });
    }

    setupCommunityArea() {
        const centerX = 400;
        const centerY = 270;
        
        // Community cards area label
        this.add.text(centerX, centerY - 60, 'COMMUNITY CARDS', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Community card placeholders
        for (let i = 0; i < 5; i++) {
            const cardX = centerX - 120 + (i * 60);
            const placeholder = this.add.rectangle(cardX, centerY, 60, 84, 0x444444, 0.3)
                .setStrokeStyle(2, 0x666666);
        }
        
        // Pot display
        this.potText = this.add.text(centerX, centerY + 60, '', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
    }

    setupUI() {
        // Game info area
        this.gameInfoText = this.add.text(50, 50, '', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            backgroundColor: '#000000',
            padding: { x: 10, y: 5 }
        });
    }

    setupEventListeners() {
        if (this.eventBus) {
            this.eventBus.on('pokerGameStateUpdate', this.updateGameDisplay, this);
            this.eventBus.on('pokerHandStarted', this.handleHandStarted, this);
            this.eventBus.on('pokerCardsDealt', this.handleCardsDealt, this);
            this.eventBus.on('pokerActionTaken', this.handleActionTaken, this);
        }
    }

    updateGameDisplay(gameState) {
        this.gameState = gameState;
        
        this.updateSeats(gameState);
        this.updateCommunityCards(gameState);
        this.updatePot(gameState);
        this.updateGameInfo(gameState);
        this.updateDealerButton(gameState);
    }

    updateSeats(gameState) {
        // Clear all seats first
        this.playerSeats.forEach(seat => {
            seat.isEmpty = true;
            if (seat.playerInfo) {
                seat.playerInfo.destroy();
                seat.playerInfo = null;
            }
            seat.cards.forEach(card => card.destroy());
            seat.cards = [];
            if (seat.actionText) {
                seat.actionText.destroy();
                seat.actionText = null;
            }
        });
        
        // Update with current players
        if (gameState.player_states) {
            gameState.player_states.forEach(player => {
                const seatIndex = player.seat_id - 1;
                if (seatIndex >= 0 && seatIndex < this.playerSeats.length) {
                    this.updatePlayerSeat(this.playerSeats[seatIndex], player, gameState);
                }
            });
        }
    }

    updatePlayerSeat(seat, player, gameState) {
        seat.isEmpty = false;
        
        // Player info
        const infoText = `${player.username}\nStack: ${player.stack_sats}\n${player.last_action || 'Waiting'}`;
        seat.playerInfo = this.add.text(0, -80, infoText, {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            backgroundColor: '#000000',
            padding: { x: 5, y: 3 },
            align: 'center'
        }).setOrigin(0.5);
        seat.container.add(seat.playerInfo);
        
        // Highlight current turn
        if (gameState.current_turn_user_id === player.user_id) {
            seat.container.getAt(0).setStrokeStyle(4, 0x00FF00); // Highlight seat circle
        }
        
        // Show hole cards (if visible)
        if (player.hole_cards && player.hole_cards.length > 0) {
            this.showPlayerCards(seat, player.hole_cards, gameState.current_turn_user_id === player.user_id);
        }
    }

    showPlayerCards(seat, cards, isCurrentPlayer) {
        cards.forEach((card, index) => {
            const cardX = -25 + (index * 30);
            const cardY = 30;
            
            let cardTexture;
            if (isCurrentPlayer && card !== 'XX') {
                // Show actual card for current player
                cardTexture = `card-${card}`;
            } else {
                // Show card back for other players
                cardTexture = 'card-back';
            }
            
            const cardSprite = this.add.image(cardX, cardY, cardTexture);
            seat.cards.push(cardSprite);
            seat.container.add(cardSprite);
        });
    }

    updateCommunityCards(gameState) {
        // Clear existing community cards
        this.communityCards.forEach(card => card.destroy());
        this.communityCards = [];
        
        if (gameState.board_cards && gameState.board_cards.length > 0) {
            const centerX = 400;
            const centerY = 270;
            
            gameState.board_cards.forEach((card, index) => {
                const cardX = centerX - 120 + (index * 60);
                const cardSprite = this.add.image(cardX, centerY, `card-${card}`);
                this.communityCards.push(cardSprite);
            });
        }
    }

    updatePot(gameState) {
        if (gameState.pot_size_sats) {
            this.potText.setText(`Pot: ${gameState.pot_size_sats} sats`);
        } else {
            this.potText.setText('');
        }
    }

    updateGameInfo(gameState) {
        let infoText = `Table: ${gameState.table_name || 'Poker Table'}\n`;
        infoText += `Blinds: ${gameState.small_blind}/${gameState.big_blind}\n`;
        
        if (gameState.current_hand_id) {
            infoText += `Hand: ${gameState.current_hand_id}\n`;
            infoText += `Round: ${gameState.current_round || 'Pre-flop'}\n`;
        }
        
        this.gameInfoText.setText(infoText);
    }

    updateDealerButton(gameState) {
        if (gameState.current_dealer_seat_id) {
            const seatIndex = gameState.current_dealer_seat_id - 1;
            if (seatIndex >= 0 && seatIndex < this.playerSeats.length) {
                const seat = this.playerSeats[seatIndex];
                this.dealerButton.setPosition(seat.position.x + 40, seat.position.y - 40);
                this.dealerButton.setVisible(true);
            }
        } else {
            this.dealerButton.setVisible(false);
        }
    }

    handleHandStarted(data) {
        console.log('Hand started:', data);
        this.animateHandStart();
    }

    handleCardsDealt(data) {
        console.log('Cards dealt:', data);
        this.animateCardDealing(data);
    }

    handleActionTaken(data) {
        console.log('Action taken:', data);
        this.showActionAnimation(data);
    }

    animateHandStart() {
        // Clear previous hand visuals
        this.communityCards.forEach(card => card.destroy());
        this.communityCards = [];
        
        // Clear player cards
        this.playerSeats.forEach(seat => {
            seat.cards.forEach(card => card.destroy());
            seat.cards = [];
        });
        
        // Show dealing animation
        this.showDealingAnimation();
    }

    showDealingAnimation() {
        const dealSound = this.sound.get('dealCard');
        if (dealSound) {
            dealSound.play({ volume: 0.3 });
        }
        
        // Animate cards being dealt (placeholder)
        this.tweens.add({
            targets: this.dealerPosition,
            x: this.dealerPosition.x + 10,
            duration: 100,
            yoyo: true,
            repeat: 3
        });
    }

    animateCardDealing(data) {
        // Animate cards appearing with dealing effect
        this.time.delayedCall(500, () => {
            this.updateGameDisplay(this.gameState);
        });
    }

    showActionAnimation(data) {
        if (data.seat_id) {
            const seatIndex = data.seat_id - 1;
            if (seatIndex >= 0 && seatIndex < this.playerSeats.length) {
                const seat = this.playerSeats[seatIndex];
                
                // Show action text
                const actionText = this.add.text(seat.position.x, seat.position.y - 120, data.action.toUpperCase(), {
                    fontSize: '16px',
                    fontFamily: 'Arial',
                    fill: '#FFD700',
                    fontStyle: 'bold',
                    backgroundColor: '#000000',
                    padding: { x: 8, y: 4 }
                }).setOrigin(0.5);
                
                // Animate and remove
                this.tweens.add({
                    targets: actionText,
                    alpha: { from: 1, to: 0 },
                    y: actionText.y - 30,
                    duration: 2000,
                    onComplete: () => actionText.destroy()
                });
                
                // Play sound
                const actionSound = this.sound.get('chipPlace');
                if (actionSound && (data.action === 'bet' || data.action === 'raise')) {
                    actionSound.play({ volume: 0.4 });
                }
            }
        }
    }

    // Enhanced card dealing with effects
    dealCardToPlayer(playerId, cardData, isHoleCard = false) {
        const seat = this.getPlayerSeat(playerId);
        if (!seat) return;

        const card = this.createCard(cardData, this.dealerPosition.x, this.dealerPosition.y);
        
        // Enhanced card deal animation with sound
        this.soundManager.playCardDeal();
        this.gameEnhancer.animateCardDeal(
            card,
            seat.position.x + (seat.cards.length * 20),
            seat.position.y - 30,
            seat.cards.length * 150,
            () => {
                // Card deal complete callback
                if (!isHoleCard) {
                    this.gameEnhancer.addCardFlipEffect(card);
                }
                this.gameEnhancer.addFloatingText(seat.position.x, seat.position.y - 60, 'CARD DEALT', '#FFD700');
            }
        );
        
        seat.cards.push(card);
        return card;
    }

    dealCommunityCard(cardData, position) {
        const card = this.createCard(cardData, this.dealerPosition.x, this.dealerPosition.y);
        const targetX = 300 + (position * 60);
        const targetY = 300;
        
        // Enhanced community card animation
        this.soundManager.playCardDeal();
        this.gameEnhancer.animateCardDeal(card, targetX, targetY, position * 200, () => {
            this.gameEnhancer.addCardFlipEffect(card);
            this.gameEnhancer.createSparkleEffect(targetX, targetY);
        });
        
        this.communityCards.push(card);
        return card;
    }

    createCard(cardData, x, y) {
        const card = this.add.image(x, y, `card-${cardData.suit}-${cardData.value}`)
            .setScale(0.7)
            .setDepth(10);
        
        // Add card enhancement effects
        this.gameEnhancer.addCardShadow(card);
        
        return card;
    }

    // Enhanced pot animation
    animatePotWin(winnerId, amount) {
        const winnerSeat = this.getPlayerSeat(winnerId);
        if (!winnerSeat) return;

        // Create pot collection animation
        this.gameEnhancer.animatePotCollection(
            400, 200, // pot position
            winnerSeat.position.x, winnerSeat.position.y, // winner position
            amount,
            () => {
                // Pot collected callback
                this.soundManager.playChipCollection();
                this.gameEnhancer.addWinCelebration(winnerSeat.position.x, winnerSeat.position.y);
                this.gameEnhancer.addFloatingText(
                    winnerSeat.position.x, 
                    winnerSeat.position.y - 40, 
                    `+$${amount}`, 
                    '#00FF00', 
                    24
                );
            }
        );
    }

    // Enhanced betting animation
    animateBet(playerId, amount, betType = 'bet') {
        const seat = this.getPlayerSeat(playerId);
        if (!seat) return;

        // Animate chips from player to pot
        this.gameEnhancer.animateChipToPot(
            seat.position.x, seat.position.y,
            400, 250, // pot position
            amount,
            () => {
                this.soundManager.playChipBet();
                this.updatePotDisplay();
                
                // Show bet action text
                const actionText = this.getActionText(betType, amount);
                this.gameEnhancer.addFloatingText(
                    seat.position.x, 
                    seat.position.y + 40, 
                    actionText, 
                    '#FFD700'
                );
            }
        );
    }

    getActionText(betType, amount) {
        switch(betType) {
            case 'call': return 'CALL';
            case 'raise': return `RAISE $${amount}`;
            case 'bet': return `BET $${amount}`;
            case 'allin': return 'ALL-IN!';
            case 'fold': return 'FOLD';
            case 'check': return 'CHECK';
            default: return betType.toUpperCase();
        }
    }

    // Enhanced player action feedback
    showPlayerAction(playerId, action, amount = 0) {
        const seat = this.getPlayerSeat(playerId);
        if (!seat) return;

        // Clear previous action text
        if (seat.actionText) {
            seat.actionText.destroy();
        }

        const actionString = amount > 0 ? `${action.toUpperCase()} $${amount}` : action.toUpperCase();
        
        seat.actionText = this.add.text(seat.position.x, seat.position.y + 60, actionString, {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: this.getActionColor(action),
            fontStyle: 'bold',
            backgroundColor: '#000000',
            padding: { x: 8, y: 4 }
        }).setOrigin(0.5).setDepth(15);

        // Animate action text
        this.gameEnhancer.addBounceAnimation(seat.actionText);

        // Auto-hide after 3 seconds
        this.time.delayedCall(3000, () => {
            if (seat.actionText) {
                this.tweens.add({
                    targets: seat.actionText,
                    alpha: 0,
                    duration: 500,
                    onComplete: () => {
                        if (seat.actionText) {
                            seat.actionText.destroy();
                            seat.actionText = null;
                        }
                    }
                });
            }
        });
    }

    getActionColor(action) {
        const colors = {
            fold: '#FF4444',
            call: '#44AA44',
            check: '#44AA44',
            bet: '#4444FF',
            raise: '#4444FF',
            allin: '#FF8800'
        };
        return colors[action.toLowerCase()] || '#FFFFFF';
    }

    // Enhanced showdown animation
    showdownAnimation(results) {
        results.forEach((result, index) => {
            const seat = this.getPlayerSeat(result.playerId);
            if (!seat) return;

            this.time.delayedCall(index * 500, () => {
                // Reveal hole cards with flip animation
                seat.cards.forEach((card, cardIndex) => {
                    this.time.delayedCall(cardIndex * 200, () => {
                        this.gameEnhancer.addCardFlipEffect(card);
                        this.soundManager.playCardFlip();
                    });
                });

                // Show hand ranking
                if (result.handRank) {
                    this.gameEnhancer.addFloatingText(
                        seat.position.x,
                        seat.position.y - 80,
                        result.handRank.toUpperCase(),
                        '#FFD700',
                        18
                    );
                }

                // Winner celebration
                if (result.isWinner) {
                    this.time.delayedCall(1000, () => {
                        this.gameEnhancer.addWinCelebration(seat.position.x, seat.position.y);
                        this.animatePotWin(result.playerId, result.winAmount);
                    });
                }
            });
        });
    }

    // Utility methods
    getPlayerSeat(playerId) {
        return this.playerSeats.find(seat => seat.playerId === playerId);
    }

    updatePotDisplay() {
        const totalPot = this.gameState?.pot || 0;
        if (this.potText) {
            this.potText.setText(`POT: $${totalPot}`);
            this.gameEnhancer.addPulseAnimation(this.potText, 1.1, 200);
        }
    }

    // Enhanced cleanup
    clearTable() {
        // Clear community cards with animation
        this.communityCards.forEach((card, index) => {
            this.time.delayedCall(index * 100, () => {
                this.gameEnhancer.animateCardCollect(card, this.dealerPosition.x, this.dealerPosition.y);
            });
        });
        this.communityCards = [];

        // Clear player cards
        this.playerSeats.forEach(seat => {
            if (seat.cards) {
                seat.cards.forEach((card, index) => {
                    this.time.delayedCall(index * 50, () => {
                        this.gameEnhancer.animateCardCollect(card, this.dealerPosition.x, this.dealerPosition.y);
                    });
                });
                seat.cards = [];
            }
            
            // Clear action text
            if (seat.actionText) {
                seat.actionText.destroy();
                seat.actionText = null;
            }
        });
    }

    // Enhanced event handlers
    handleNewHand(handData) {
        this.soundManager.playNewHand();
        this.clearTable();
        
        // Reset pot display
        this.updatePotDisplay();
        
        // Show new hand animation
        this.gameEnhancer.addScreenFlash(0xFFD700, 0.2, 300);
        this.gameEnhancer.addFloatingText(400, 100, 'NEW HAND', '#FFD700', 24);
    }

    handlePlayerJoin(playerData) {
        this.soundManager.playPlayerJoin();
        const seat = this.playerSeats[playerData.seatIndex - 1];
        if (seat) {
            seat.playerId = playerData.id;
            seat.isEmpty = false;
            
            // Update seat visual
            this.updateSeatDisplay(seat, playerData);
            
            // Welcome animation
            this.gameEnhancer.addWelcomeEffect(seat.position.x, seat.position.y);
        }
    }

    handlePlayerLeave(playerId) {
        this.soundManager.playPlayerLeave();
        const seat = this.getPlayerSeat(playerId);
        if (seat) {
            seat.playerId = null;
            seat.isEmpty = true;
            
            // Clear seat display
            this.clearSeatDisplay(seat);
            
            // Departure effect
            this.gameEnhancer.addDepartureEffect(seat.position.x, seat.position.y);
        }
    }
}
