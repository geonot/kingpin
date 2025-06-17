import Phaser from 'phaser';
import { formatSatsToBtc } from '@utils/currencyFormatter';

export default class UIScene extends Phaser.Scene {
    constructor() {
        super({ key: 'UIScene', active: false });
        this.eventBus = null;
        this.gameConfig = null;
        this.tableAPIData = null;
        
        // UI Elements
        this.balanceText = null;
        this.totalBetText = null;
        this.winText = null;
        this.messageText = null;
        
        // Betting spots
        this.playerBetSpot = null;
        this.bankerBetSpot = null;
        this.tieBetSpot = null;
        
        // Bet displays
        this.playerBetText = null;
        this.bankerBetText = null;
        this.tieBetText = null;
        
        // Buttons
        this.dealButton = null;
        this.clearBetsButton = null;
        this.rebetButton = null;
        
        // Chip buttons
        this.chipButtons = [];
        this.selectedChipValue = 100;
        
        // Betting state
        this.currentBets = {
            player: 0,
            banker: 0,
            tie: 0
        };
        
        this.isHandInProgress = false;
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameConfig = this.registry.get('gameDefinition');
        this.tableAPIData = this.registry.get('tableData');
    }

    create() {
        console.log('Baccarat UIScene: create()');
        
        if (!this.eventBus || !this.gameConfig) {
            console.error('Baccarat UIScene: Critical data missing');
            return;
        }

        this.setupUI();
        this.setupEventListeners();
        this.updateUIState();
        
        console.log('Baccarat UIScene: Ready');
    }

    setupUI() {
        const centerX = this.cameras.main.centerX;
        const width = this.cameras.main.width;
        const height = this.cameras.main.height;
        
        // Balance display
        this.balanceText = this.add.text(20, 20, '', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        });
        
        // Total bet display
        this.totalBetText = this.add.text(20, 50, '', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFD700'
        });
        
        // Win display
        this.winText = this.add.text(centerX, 50, '', {
            fontSize: '20px',
            fontFamily: 'Arial',
            fill: '#00FF00',
            fontStyle: 'bold'
        }).setOrigin(0.5).setVisible(false);
        
        // Message display
        this.messageText = this.add.text(centerX, height - 100, '', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FF4444',
            fontStyle: 'bold'
        }).setOrigin(0.5).setVisible(false);
        
        this.setupBettingSpots();
        this.setupChipButtons();
        this.setupActionButtons();
    }

    setupBettingSpots() {
        const centerX = this.cameras.main.centerX;
        const centerY = this.cameras.main.centerY;
        
        // Player betting spot
        this.playerBetSpot = this.add.rectangle(centerX - 200, centerY + 250, 120, 60, 0x4169E1, 0.7)
            .setStrokeStyle(3, 0xFFD700)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.placeBet('player'));
            
        this.add.text(centerX - 200, centerY + 250, 'PLAYER', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.playerBetText = this.add.text(centerX - 200, centerY + 280, '', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFD700'
        }).setOrigin(0.5);
        
        // Banker betting spot
        this.bankerBetSpot = this.add.rectangle(centerX, centerY + 250, 120, 60, 0xDC143C, 0.7)
            .setStrokeStyle(3, 0xFFD700)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.placeBet('banker'));
            
        this.add.text(centerX, centerY + 250, 'BANKER', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.bankerBetText = this.add.text(centerX, centerY + 280, '', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFD700'
        }).setOrigin(0.5);
        
        // Tie betting spot
        this.tieBetSpot = this.add.rectangle(centerX + 200, centerY + 250, 120, 60, 0x32CD32, 0.7)
            .setStrokeStyle(3, 0xFFD700)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.placeBet('tie'));
            
        this.add.text(centerX + 200, centerY + 250, 'TIE', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.tieBetText = this.add.text(centerX + 200, centerY + 280, '', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFD700'
        }).setOrigin(0.5);
    }

    setupChipButtons() {
        const chipValues = [25, 100, 500, 1000];
        const startX = 50;
        const startY = this.cameras.main.height - 150;
        
        chipValues.forEach((value, index) => {
            const chip = this.add.circle(startX + (index * 80), startY, 25, this.getChipColor(value))
                .setStrokeStyle(3, 0x000000)
                .setInteractive({ useHandCursor: true })
                .on('pointerdown', () => this.selectChip(value));
                
            this.add.text(startX + (index * 80), startY, value.toString(), {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            this.chipButtons.push(chip);
        });
        
        // Highlight default chip
        this.updateChipSelection();
    }

    setupActionButtons() {
        const centerX = this.cameras.main.centerX;
        const buttonY = this.cameras.main.height - 50;
        
        // Deal button
        this.dealButton = this.add.rectangle(centerX - 100, buttonY, 120, 40, 0x228B22)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.dealHand());
            
        this.add.text(centerX - 100, buttonY, 'DEAL', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Clear bets button
        this.clearBetsButton = this.add.rectangle(centerX + 100, buttonY, 120, 40, 0xB22222)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.clearBets());
            
        this.add.text(centerX + 100, buttonY, 'CLEAR', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Rebet button (initially hidden)
        this.rebetButton = this.add.rectangle(centerX, buttonY, 120, 40, 0x4169E1)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.rebet())
            .setVisible(false);
            
        this.add.text(centerX, buttonY, 'REBET', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5).setVisible(false);
    }

    setupEventListeners() {
        this.eventBus.on('baccaratHandResult', this.handleHandResult, this);
        this.eventBus.on('userBalanceUpdate', this.updateBalance, this);
    }

    placeBet(area) {
        if (this.isHandInProgress) return;
        
        const maxBet = this.getMaxBetForArea(area);
        const newBet = Math.min(this.currentBets[area] + this.selectedChipValue, maxBet);
        
        if (newBet <= maxBet && this.canAffordBet(newBet - this.currentBets[area])) {
            this.currentBets[area] = newBet;
            this.updateBetDisplays();
            this.playChipSound();
        } else {
            this.showMessage('Insufficient balance or max bet reached!');
        }
    }

    selectChip(value) {
        this.selectedChipValue = value;
        this.updateChipSelection();
        this.playChipSound();
    }

    clearBets() {
        if (this.isHandInProgress) return;
        
        this.currentBets = { player: 0, banker: 0, tie: 0 };
        this.updateBetDisplays();
        this.hideMessage();
    }

    dealHand() {
        const totalBet = this.getTotalBet();
        if (totalBet === 0) {
            this.showMessage('Place a bet first!');
            return;
        }
        
        if (!this.canAffordBet(totalBet)) {
            this.showMessage('Insufficient balance!');
            return;
        }
        
        this.isHandInProgress = true;
        this.hideMessage();
        this.hideWinText();
        
        // Emit bet to Vue component
        this.eventBus.emit('baccaratBetRequested', {
            playerBet: this.currentBets.player,
            bankerBet: this.currentBets.banker,
            tieBet: this.currentBets.tie
        });
        
        this.updateUIState();
    }

    rebet() {
        // Reuse last bet amounts and deal
        this.dealHand();
    }

    handleHandResult(data) {
        this.isHandInProgress = false;
        
        if (data.success && data.hand) {
            const winAmount = data.hand.total_win_amount || 0;
            if (winAmount > 0) {
                this.showWinText(winAmount);
            }
        }
        
        this.updateUIState();
    }

    updateBalance(newBalance) {
        this.registry.set('userBalance', newBalance);
        this.updateUIState();
    }

    updateUIState() {
        const balance = this.registry.get('userBalance') || 0;
        this.balanceText.setText(`Balance: ${formatSatsToBtc(balance, true)}`);
        
        const totalBet = this.getTotalBet();
        this.totalBetText.setText(`Total Bet: ${formatSatsToBtc(totalBet)}`);
        
        // Update button states
        const canDeal = !this.isHandInProgress && totalBet > 0 && this.canAffordBet(totalBet);
        this.dealButton.setAlpha(canDeal ? 1 : 0.5);
        
        const canClear = !this.isHandInProgress && totalBet > 0;
        this.clearBetsButton.setAlpha(canClear ? 1 : 0.5);
        
        // Update betting spot interactivity
        [this.playerBetSpot, this.bankerBetSpot, this.tieBetSpot].forEach(spot => {
            spot.setAlpha(this.isHandInProgress ? 0.5 : 1);
        });
    }

    updateBetDisplays() {
        this.playerBetText.setText(this.currentBets.player > 0 ? formatSatsToBtc(this.currentBets.player) : '');
        this.bankerBetText.setText(this.currentBets.banker > 0 ? formatSatsToBtc(this.currentBets.banker) : '');
        this.tieBetText.setText(this.currentBets.tie > 0 ? formatSatsToBtc(this.currentBets.tie) : '');
        this.updateUIState();
    }

    updateChipSelection() {
        this.chipButtons.forEach((chip, index) => {
            const chipValues = [25, 100, 500, 1000];
            const isSelected = chipValues[index] === this.selectedChipValue;
            chip.setStrokeStyle(3, isSelected ? 0xFFD700 : 0x000000);
        });
    }

    showWinText(amount) {
        this.winText.setText(`WIN: ${formatSatsToBtc(amount)}`)
            .setVisible(true)
            .setAlpha(0);
            
        this.tweens.add({
            targets: this.winText,
            alpha: 1,
            scale: { from: 0.5, to: 1.2 },
            duration: 500,
            yoyo: true,
            repeat: 2
        });
    }

    hideWinText() {
        this.winText.setVisible(false);
    }

    showMessage(text) {
        this.messageText.setText(text).setVisible(true);
        this.time.delayedCall(3000, () => this.hideMessage());
    }

    hideMessage() {
        this.messageText.setVisible(false);
    }

    getTotalBet() {
        return this.currentBets.player + this.currentBets.banker + this.currentBets.tie;
    }

    canAffordBet(amount) {
        const balance = this.registry.get('userBalance') || 0;
        return balance >= amount;
    }

    getMaxBetForArea(area) {
        if (!this.tableAPIData) return 10000;
        
        switch (area) {
            case 'player':
            case 'banker':
                return this.tableAPIData.max_bet || 10000;
            case 'tie':
                return this.tableAPIData.max_tie_bet || this.tableAPIData.max_bet || 10000;
            default:
                return 10000;
        }
    }

    getChipColor(value) {
        const colors = {
            25: 0x008000,    // Green
            100: 0x000080,   // Navy
            500: 0x800080,   // Purple  
            1000: 0x8B0000   // Dark Red
        };
        return colors[value] || 0x808080;
    }

    playChipSound() {
        if (this.sound.get('chipPlace')) {
            this.sound.play('chipPlace', { volume: 0.3 });
        }
    }

    shutdown() {
        if (this.eventBus) {
            this.eventBus.off('baccaratHandResult', this.handleHandResult, this);
            this.eventBus.off('userBalanceUpdate', this.updateBalance, this);
        }
    }
}
    }
}
