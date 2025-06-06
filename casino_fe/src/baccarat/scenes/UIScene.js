import Phaser from 'phaser';

export default class UIScene extends Phaser.Scene {
    constructor() {
        super({ key: 'UIScene', active: false });
        this.eventBus = null;
        this.gameConfig = null;
        // Betting state
        this.currentBet = { player: 0, banker: 0, tie: 0, total: 0 };
        this.selectedChipValue = 100; // Default chip
        // TODO: BACKEND INTEGRATION: Fetch initial user balance from the backend via API call.
        // The event bus or a direct call from Vue component should provide this.
        // Example: this.eventBus.on('initialBalanceSet', balance => { this.userBalance = balance; this.balanceText.setText(`Balance: $${this.userBalance}`); });
        // this.registry.get('eventBus').emit('requestInitialBalance'); // If Vue needs to trigger fetch
        this.userBalance = 1000; // Placeholder initial balance
        this.lastBet = null; // For re-bet functionality
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameConfig = this.registry.get('gameDefinition');
    }

    /**
     * UIScene Event Emitters:
     * - dealButtonPressed: { bets: this.currentBet } - When the deal button is pressed.
     * - roundConcluded (indirectly via handleHandResult timer): Signals UI is ready for next round.
     *
     * UIScene Event Listeners:
     * - roundConcluded (from GameScene): To re-enable betting controls.
     * - outOfCards (from GameScene): To display message and potentially disable controls.
     * - handResult (from GameScene): { playerHand, bankerHand, playerScore, bankerScore, winner } - To display results.
     * - roundInProgress (from GameScene): To disable betting controls.
     */
    create() {
        const { width, height } = this.cameras.main;

        // Bet Amount Texts (created here, updated in placeBet)
        const betTextStyle = { fontSize: '20px', fill: '#fff', backgroundColor: 'rgba(0,0,0,0.5)', padding: { x: 5, y: 2 } };
        this.playerBetAmountText = this.add.text(width * 0.25, height * 0.55, '', betTextStyle).setOrigin(0.5);
        this.bankerBetAmountText = this.add.text(width * 0.5, height * 0.55, '', betTextStyle).setOrigin(0.5);
        this.tieBetAmountText = this.add.text(width * 0.75, height * 0.55, '', betTextStyle).setOrigin(0.5);


        // Betting spots (Player, Banker, Tie) - make them interactive
        const playerBetSpot = this.add.rectangle(width * 0.25, height * 0.65, 150, 100, 0x00ff00, 0.3).setInteractive();
        playerBetSpot.on('pointerover', () => playerBetSpot.setFillStyle(0x00ff00, 0.5));
        playerBetSpot.on('pointerout', () => playerBetSpot.setFillStyle(0x00ff00, 0.3));
        playerBetSpot.on('pointerdown', () => this.placeBet('player'));
        this.playerBetSpot = playerBetSpot;

        const bankerBetSpot = this.add.rectangle(width * 0.5, height * 0.65, 150, 100, 0xff0000, 0.3).setInteractive();
        bankerBetSpot.on('pointerover', () => bankerBetSpot.setFillStyle(0xff0000, 0.5));
        bankerBetSpot.on('pointerout', () => bankerBetSpot.setFillStyle(0xff0000, 0.3));
        bankerBetSpot.on('pointerdown', () => this.placeBet('banker'));
        this.bankerBetSpot = bankerBetSpot;

        const tieBetSpot = this.add.rectangle(width * 0.75, height * 0.65, 150, 100, 0xaaaa00, 0.3).setInteractive();
        tieBetSpot.on('pointerover', () => tieBetSpot.setFillStyle(0xaaaa00, 0.5));
        tieBetSpot.on('pointerout', () => tieBetSpot.setFillStyle(0xaaaa00, 0.3));
        tieBetSpot.on('pointerdown', () => this.placeBet('tie'));
        this.tieBetSpot = tieBetSpot;


        // Chip selection buttons
        const chipValues = [5, 25, 100, 500];
        const chipStartX = width * 0.3;
        const chipSpacing = 80;
        this.chipButtons = chipValues.map((value, index) => {
            const chipButton = this.add.text(chipStartX + (index * chipSpacing), height * 0.85, `$${value}`, {
                fontSize: '24px',
                fill: '#fff',
                backgroundColor: '#555',
                padding: { x: 10, y: 5 }
            }).setInteractive();

            chipButton.on('pointerdown', () => {
                this.selectedChipValue = value;
                console.log(`Selected chip: ${value}`);
                this.chipButtons.forEach(btn => {
                    const isSelected = btn.text === `$${value}`;
                    btn.setBackgroundColor(isSelected ? '#888' : '#555');
                    btn.setScale(isSelected ? 1.1 : 1.0);
                    btn.setTint(isSelected ? 0xffff00 : 0xffffff);
                });
            });
            if (value === this.selectedChipValue) {
                chipButton.setBackgroundColor('#888');
                chipButton.setScale(1.1);
                chipButton.setTint(0xffff00);
            }
            return chipButton;
        });

        // Action Buttons
        this.dealButton = this.add.text(width * 0.3, height * 0.95, 'Deal', { fontSize: '28px', fill: '#0f0', backgroundColor: '#333', padding: { x:15, y:10 }}).setInteractive();
        this.dealButton.on('pointerdown', () => {
            if (this.dealButton.input.enabled && this.currentBet.total > 0) {
                this.lastBet = { ...this.currentBet }; // Store for re-bet

                // TODO: BACKEND INTEGRATION: Instead of client-side 'dealButtonPressed',
                // this should send the 'this.currentBet' object to the backend API to initiate a new game round.
                // Example:
                // sendBetToBackend(this.currentBet).then(response => {
                //   // Backend will likely respond with initial hand dealing or confirmation.
                //   // GameScene will then receive results via a separate WebSocket message or API poll.
                //   // If using WebSocket, GameScene would listen for messages from the backend.
                // }).catch(error => {
                //   console.error("Error placing bet:", error);
                //   this.messageText.setText("Error placing bet. Try again.");
                //   this.toggleBettingControls(true); // Re-enable controls if bet fails
                // });
                // For now, client-side event 'dealButtonPressed' will trigger GameScene's local dealing.
                console.log('UIScene: Emitting dealButtonPressed with bets:', this.currentBet);
                this.eventBus.emit('dealButtonPressed', { bets: this.currentBet });
                // UI will be updated by 'roundInProgress' event from GameScene
            } else if (this.dealButton.input.enabled) {
                this.messageText.setText("Please place a bet first!");
            }
        });

        this.clearButton = this.add.text(width * 0.5, height * 0.95, 'Clear Bet', { fontSize: '28px', fill: '#f00', backgroundColor: '#333', padding: { x:15, y:10 }}).setInteractive();
        this.clearButton.on('pointerdown', () => {
            if (!this.clearButton.input.enabled) return;
            console.log('Clear Bet button clicked');
            this.currentBet = { player: 0, banker: 0, tie: 0, total: 0 };
            this.currentBetText.setText('Current Bet: $0');
            this.playerBetAmountText.setText('');
            this.bankerBetAmountText.setText('');
            this.tieBetAmountText.setText('');
            this.messageText.setText('Place your bets!');
            this.updateDealButtonState(); // Deal button should be disabled if bet is cleared
        });

        this.rebetButton = this.add.text(width * 0.7, height * 0.95, 'Re-Bet', { fontSize: '28px', fill: '#00f', backgroundColor: '#333', padding: { x:15, y:10 }}).setInteractive();
        this.rebetButton.on('pointerdown', () => {
            if (!this.rebetButton.input.enabled) return;
            console.log('Re-Bet button clicked');
            if (this.lastBet && this.lastBet.total > 0) {
                // TODO: BACKEND INTEGRATION: Check against actual user balance from backend if re-bet is possible.
                if (this.userBalance >= this.lastBet.total) {
                    this.currentBet = { ...this.lastBet };
                    this.currentBetText.setText('Current Bet: $' + this.currentBet.total);
                    this.playerBetAmountText.setText(this.currentBet.player > 0 ? `$${this.currentBet.player}` : '');
                    this.bankerBetAmountText.setText(this.currentBet.banker > 0 ? `$${this.currentBet.banker}` : '');
                    this.tieBetAmountText.setText(this.currentBet.tie > 0 ? `$${this.currentBet.tie}` : '');
                    this.messageText.setText('Bets placed. Press Deal.');
                    this.updateDealButtonState();
                    // Play chip sound (placeholder)
                    try { this.sound.play('chip_sound'); } catch(e) { console.warn('chip_sound not loaded');}
                } else {
                    this.messageText.setText('Insufficient balance for re-bet.');
                }
            } else {
                this.messageText.setText('No last bet to re-bet.');
            }
        });

        // Text Displays
        this.balanceText = this.add.text(20, 20, `Balance: $${this.userBalance}`, { fontSize: '24px', fill: '#fff' });
        this.currentBetText = this.add.text(20, 50, `Current Bet: $${this.currentBet.total}`, { fontSize: '24px', fill: '#fff' });
        this.lastWinText = this.add.text(width - 200, 20, 'Last Win: $0', { fontSize: '24px', fill: '#fff' });
        this.messageText = this.add.text(width / 2, height * 0.9, 'Place your bets!', { fontSize: '24px', fill: '#ff0' }).setOrigin(0.5);

        // Example of listening to an event from GameScene to re-enable betting
        this.eventBus.on('roundConcluded', () => {
            this.toggleBettingControls(true);
            this.messageText.setText('Place your bets for the next round!');
        }, this);

        this.eventBus.on('outOfCards', () => {
            this.messageText.setText('No more cards in deck. Please restart.');
            this.toggleBettingControls(false); // Disable all controls
        }, this);

        this.eventBus.on('handResult', this.handleHandResult, this);

        this.eventBus.on('roundInProgress', () => {
            this.toggleBettingControls(false);
            this.messageText.setText("Round in progress...");
        }, this);


        // Listen for updates from GameScene or Vue (e.g., balance update)
        // this.eventBus.on('updateBalance', (newBalance) => {
        //     this.userBalance = newBalance;
        //     this.balanceText.setText(`Balance: $${this.userBalance}`);
        // }, this);
    }

    placeBet(area) {
        // Prevent betting if a round is in progress and cards are shown, etc.
        // This state needs to be managed, e.g., by disabling bet spots/chips.
        // For now, assume betting is allowed.

        if (this.selectedChipValue <= 0) {
            this.messageText.setText('Select a chip value first!');
            return;
        }

        // TODO: BACKEND INTEGRATION: Check against actual user balance from backend.
        if (this.userBalance < this.currentBet.total + this.selectedChipValue) {
            this.messageText.setText('Insufficient balance.');
            return;
        }

        this.currentBet[area] += this.selectedChipValue;
        this.currentBet.total = this.currentBet.player + this.currentBet.banker + this.currentBet.tie;
        this.currentBetText.setText('Current Bet: $' + this.currentBet.total);
        this.updateDealButtonState();

        // Update visual bet amount on the specific spot
        switch (area) {
            case 'player':
                this.playerBetAmountText.setText(`$${this.currentBet.player}`);
                break;
            case 'banker':
                this.bankerBetAmountText.setText(`$${this.currentBet.banker}`);
                break;
            case 'tie':
                this.tieBetAmountText.setText(`$${this.currentBet.tie}`);
                break;
        }

        // Play chip sound
        try { this.sound.play('chip_sound'); } catch(e) { console.warn('chip_sound not loaded');}

        this.messageText.setText('Bet placed. Press Deal or add more.');
    }

    handleHandResult(data) {
        console.log("UIScene: Hand result received", data);
        this.messageText.setText(`Player: ${data.playerScore} - Banker: ${data.bankerScore}\n${data.winner} Wins!`);

        // TODO: BACKEND INTEGRATION: The backend should be the source of truth for the user's balance
        // and winnings. After a hand result, the backend should send the updated balance and amount won/lost.
        // This client-side calculation should be removed or reconciled with backend data.
        // Example: this.eventBus.on('balanceUpdatedByBackend', (updateData) => {
        //    this.userBalance = updateData.newBalance;
        //    this.lastWinText.setText(`Last Win: $${updateData.lastWinAmount}`);
        //    this.balanceText.setText(`Balance: $${this.userBalance.toFixed(0)}`);
        //    if (updateData.lastWinAmount > 0) try { this.sound.play('win_sound'); } catch(e){}
        //    else try { this.sound.play('lose_sound'); } catch(e){}
        // });

        let winAmountCalculation = 0; // This is the total returned to player (stake + profit)
        if (data.winner === 'Player' && this.currentBet.player > 0) {
            winAmountCalculation = this.currentBet.player * 2; // Standard 1:1 payout
        } else if (data.winner === 'Banker' && this.currentBet.banker > 0) {
            // Banker wins typically pay 0.95:1 on the profit, stake is returned.
            // So, profit = this.currentBet.banker * 0.95. Returned = this.currentBet.banker + profit.
            // For simplicity (as per previous steps), using 1:1 for now:
            winAmountCalculation = this.currentBet.banker * 2;
        } else if (data.winner === 'Tie' && this.currentBet.tie > 0) {
            winAmountCalculation = this.currentBet.tie * 9; // Standard 8:1 payout (win 8x, get stake back)
        }

        const amountRisked = this.currentBet.total;
        const profitOrLoss = winAmountCalculation - amountRisked;

        this.userBalance += profitOrLoss; // Update balance based on client calculation
        this.balanceText.setText(`Balance: $${this.userBalance.toFixed(0)}`);

        if (profitOrLoss > 0) {
            this.lastWinText.setText(`Last Win: $${profitOrLoss.toFixed(0)}`);
            try { this.sound.play('win_sound'); } catch (e) { console.warn("win_sound not loaded or playable", e); }
        } else if (profitOrLoss < 0) {
            this.lastWinText.setText('Last Win: $0'); // Or display loss if desired
            try { this.sound.play('lose_sound'); } catch (e) { console.warn("lose_sound not loaded or playable", e); }
        } else {
            this.lastWinText.setText('Last Win: $0'); // Push or no bet on winning outcome
        }

        // The delayed call for messageText update is now handled by the 'roundConcluded' event listener
    }

    toggleBettingControls(enabled) {
        const alpha = enabled ? 1 : 0.5;

        // Bet Spots
        this.playerBetSpot.input.enabled = enabled;
        this.playerBetSpot.setAlpha(alpha);
        this.bankerBetSpot.input.enabled = enabled;
        this.bankerBetSpot.setAlpha(alpha);
        this.tieBetSpot.input.enabled = enabled;
        this.tieBetSpot.setAlpha(alpha);

        // Chip Buttons
        this.chipButtons.forEach(button => {
            button.input.enabled = enabled;
            button.setAlpha(alpha);
        });

        // Action Buttons - specific logic
        this.clearButton.input.enabled = enabled;
        this.clearButton.setAlpha(alpha);
        this.rebetButton.input.enabled = enabled;
        this.rebetButton.setAlpha(alpha);

        this.updateDealButtonState(); // Deal button state depends on currentBet and general enabled state
    }

    updateDealButtonState() {
        const generalControlsEnabled = this.playerBetSpot.input.enabled; // Check one of the general controls
        if (generalControlsEnabled && this.currentBet.total > 0) {
            this.dealButton.input.enabled = true;
            this.dealButton.setAlpha(1);
        } else {
            this.dealButton.input.enabled = false;
            this.dealButton.setAlpha(0.5);
        }
    }

    update() {
        // TODO: UI updates if any
    }
}
