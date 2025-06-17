import Phaser from 'phaser';
import GameEnhancer from '../utils/GameEnhancer';
import CasinoGameIntegrator from '../utils/CasinoGameIntegrator';
import SoundManager from '../utils/SoundManager';

export default class PokerUIScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PokerUIScene', active: false });
        
        // Enhancement systems
        this.gameEnhancer = null;
        this.gameIntegrator = null;
        this.soundManager = null;
        
        // UI state
        this.eventBus = null;
        this.gameState = null;
        this.currentPlayer = null;
        
        // UI elements
        this.actionButtons = {};
        this.betSlider = null;
        this.betAmountText = null;
        this.playerInfoPanel = null;
        this.potDisplay = null;
        this.chipSelection = [];
        
        // Current bet amount
        this.currentBetAmount = 0;
        this.minBet = 10;
        this.maxBet = 1000;
        
        // Player actions available
        this.availableActions = [];
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameState = this.registry.get('gameState');
        this.currentPlayer = this.registry.get('currentPlayer');
    }

    create() {
        console.log('PokerUIScene: create()');
        
        // Initialize enhancement systems
        this.initializeEnhancements();
        
        this.setupUI();
        this.setupEventListeners();
        
        if (this.gameState) {
            this.updateUI(this.gameState);
        }
        
        // Apply poker UI enhancements
        this.gameIntegrator.enhancePokerUI(this);
        
        console.log('PokerUIScene: Ready');
    }

    initializeEnhancements() {
        this.gameEnhancer = new GameEnhancer(this);
        this.gameIntegrator = new CasinoGameIntegrator(this);
        this.soundManager = new SoundManager(this);
        
        console.log('PokerUIScene: Enhancement systems initialized');
    }

    setupUI() {
        const centerX = 400;
        const centerY = 300;
        
        // Action buttons panel
        this.createActionButtons();
        
        // Betting controls
        this.createBettingControls();
        
        // Player info panel
        this.createPlayerInfoPanel();
        
        // Chip selection
        this.createChipSelection();
        
        // Game info display
        this.createGameInfoDisplay();
    }

    createActionButtons() {
        const buttonY = 500;
        const buttonSpacing = 120;
        const startX = 200;
        
        const actions = [
            { key: 'fold', text: 'Fold', color: 0xFF4444 },
            { key: 'check', text: 'Check', color: 0x44AA44 },
            { key: 'call', text: 'Call', color: 0x4444FF },
            { key: 'bet', text: 'Bet', color: 0xFFAA44 },
            { key: 'raise', text: 'Raise', color: 0xAA44FF },
            { key: 'allIn', text: 'All-In', color: 0xFF44AA }
        ];
        
        actions.forEach((action, index) => {
            const buttonX = startX + (index * buttonSpacing);
            
            // Button background
            const button = this.add.rectangle(buttonX, buttonY, 100, 40, action.color, 0.8)
                .setStrokeStyle(2, 0xFFFFFF)
                .setInteractive()
                .setVisible(false);
            
            // Button text
            const buttonText = this.add.text(buttonX, buttonY, action.text, {
                fontSize: '14px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            // Button functionality
            button.on('pointerdown', () => this.handleAction(action.key));
            button.on('pointerover', () => {
                button.setFillStyle(action.color, 1.0);
                this.playSound('hover');
            });
            button.on('pointerout', () => {
                button.setFillStyle(action.color, 0.8);
            });
            
            this.actionButtons[action.key] = {
                button: button,
                text: buttonText,
                originalColor: action.color
            };
        });
    }

    createBettingControls() {
        const centerX = 400;
        const controlY = 450;
        
        // Bet amount display
        this.betAmountText = this.add.text(centerX, controlY - 30, 'Bet: $0', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold',
            backgroundColor: '#000000',
            padding: { x: 10, y: 5 }
        }).setOrigin(0.5);
        
        // Bet slider background
        const sliderBg = this.add.rectangle(centerX, controlY, 200, 20, 0x333333)
            .setStrokeStyle(2, 0x666666);
        
        // Bet slider handle
        this.betSlider = this.add.circle(centerX - 100, controlY, 12, 0xFFD700)
            .setStrokeStyle(2, 0x000000)
            .setInteractive({ draggable: true });
        
        // Slider functionality
        this.betSlider.on('drag', (pointer, dragX) => {
            const sliderLeft = centerX - 100;
            const sliderRight = centerX + 100;
            const clampedX = Phaser.Math.Clamp(dragX, sliderLeft, sliderRight);
            
            this.betSlider.x = clampedX;
            
            // Calculate bet amount
            const percentage = (clampedX - sliderLeft) / (sliderRight - sliderLeft);
            this.currentBetAmount = Math.round(this.minBet + (percentage * (this.maxBet - this.minBet)));
            this.updateBetDisplay();
        });
        
        // Quick bet buttons
        const quickBets = [10, 25, 50, 100, 250];
        quickBets.forEach((amount, index) => {
            const buttonX = centerX - 100 + (index * 50);
            const quickBetBtn = this.add.rectangle(buttonX, controlY + 40, 40, 25, 0x444444)
                .setStrokeStyle(1, 0x888888)
                .setInteractive();
            
            this.add.text(buttonX, controlY + 40, `$${amount}`, {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: '#FFFFFF'
            }).setOrigin(0.5);
            
            quickBetBtn.on('pointerdown', () => {
                this.setCurrentBet(amount);
            });
        });
    }

    createPlayerInfoPanel() {
        const panelX = 50;
        const panelY = 50;
        
        // Panel background
        const panel = this.add.rectangle(panelX, panelY, 180, 120, 0x000000, 0.8)
            .setStrokeStyle(2, 0xFFD700)
            .setOrigin(0, 0);
        
        // Player info text
        this.playerInfoPanel = this.add.text(panelX + 10, panelY + 10, '', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            wordWrap: { width: 160 }
        });
    }

    createChipSelection() {
        const chipValues = [1, 5, 25, 100, 500];
        const chipColors = [0xFFFFFF, 0xFF4444, 0x44AA44, 0x4444FF, 0x000000];
        
        chipValues.forEach((value, index) => {
            const chipX = 700 + (index * 50);
            const chipY = 450;
            
            // Chip circle
            const chip = this.add.circle(chipX, chipY, 20, chipColors[index])
                .setStrokeStyle(3, 0xFFD700)
                .setInteractive();
            
            // Chip value
            this.add.text(chipX, chipY, `$${value}`, {
                fontSize: '10px',
                fontFamily: 'Arial',
                fill: value === 500 ? '#FFFFFF' : '#000000',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            // Chip functionality
            chip.on('pointerdown', () => {
                this.addChipToBet(value);
                this.playSound('chipPlace');
            });
            
            chip.on('pointerover', () => {
                chip.setScale(1.1);
            });
            
            chip.on('pointerout', () => {
                chip.setScale(1.0);
            });
            
            this.chipSelection.push({ chip: chip, value: value });
        });
    }

    createGameInfoDisplay() {
        // Game phase display
        this.gamePhaseText = this.add.text(400, 50, '', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Timer display
        this.timerText = this.add.text(400, 75, '', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF'
        }).setOrigin(0.5);
    }

    setupEventListeners() {
        if (this.eventBus) {
            this.eventBus.on('pokerGameStateUpdate', this.updateUI, this);
            this.eventBus.on('pokerPlayerTurn', this.handlePlayerTurn, this);
            this.eventBus.on('pokerActionsAvailable', this.updateAvailableActions, this);
            this.eventBus.on('pokerBettingPhase', this.handleBettingPhase, this);
            this.eventBus.on('pokerGamePhaseChange', this.updateGamePhase, this);
        }
    }

    updateUI(gameState) {
        this.gameState = gameState;
        
        this.updatePlayerInfo();
        this.updateGamePhase(gameState.game_phase);
        this.updateAvailableActions(gameState.available_actions || []);
        this.updateBetDisplay();
    }

    updatePlayerInfo() {
        if (this.currentPlayer && this.playerInfoPanel) {
            const playerText = `Player: ${this.currentPlayer.username}\nStack: $${this.currentPlayer.stack_sats}\nPosition: ${this.currentPlayer.position || 'Unknown'}`;
            this.playerInfoPanel.setText(playerText);
        }
    }

    updateGamePhase(phase) {
        const phaseNames = {
            'pre_flop': 'Pre-Flop',
            'flop': 'Flop',
            'turn': 'Turn',
            'river': 'River',
            'showdown': 'Showdown'
        };
        
        const displayPhase = phaseNames[phase] || phase;
        this.gamePhaseText.setText(displayPhase);
    }

    updateAvailableActions(actions) {
        this.availableActions = actions;
        
        // Hide all action buttons
        Object.values(this.actionButtons).forEach(btn => {
            btn.button.setVisible(false);
        });
        
        // Show available action buttons
        actions.forEach(action => {
            if (this.actionButtons[action]) {
                this.actionButtons[action].button.setVisible(true);
            }
        });
        
        // Update button states based on current bet
        this.updateButtonStates();
    }

    updateButtonStates() {
        if (!this.gameState) return;
        
        const callAmount = this.gameState.current_bet - (this.currentPlayer?.current_bet || 0);
        
        // Update call button text
        if (this.actionButtons.call && callAmount > 0) {
            this.actionButtons.call.text.setText(`Call $${callAmount}`);
        }
        
        // Update bet/raise button text
        if (this.actionButtons.bet) {
            this.actionButtons.bet.text.setText(`Bet $${this.currentBetAmount}`);
        }
        
        if (this.actionButtons.raise) {
            this.actionButtons.raise.text.setText(`Raise $${this.currentBetAmount}`);
        }
    }

    handlePlayerTurn(data) {
        // Highlight that it's player's turn
        this.showTurnIndicator(true);
        
        // Start turn timer if applicable
        if (data.time_limit) {
            this.startTurnTimer(data.time_limit);
        }
    }

    handleBettingPhase(data) {
        // Update betting controls based on phase
        this.minBet = data.min_bet || 10;
        this.maxBet = Math.min(data.max_bet || 1000, this.currentPlayer?.stack_sats || 1000);
        
        // Reset bet amount if it's outside new limits
        if (this.currentBetAmount < this.minBet) {
            this.setCurrentBet(this.minBet);
        } else if (this.currentBetAmount > this.maxBet) {
            this.setCurrentBet(this.maxBet);
        }
    }

    handleAction(actionType) {
        if (!this.availableActions.includes(actionType)) {
            console.warn(`Action ${actionType} not available`);
            return;
        }
        
        const actionData = {
            action: actionType,
            amount: (actionType === 'bet' || actionType === 'raise') ? this.currentBetAmount : undefined
        };
        
        // Send action to game
        if (this.eventBus) {
            this.eventBus.emit('pokerPlayerAction', actionData);
        }
        
        // Hide turn indicator
        this.showTurnIndicator(false);
        
        // Play action sound
        this.playActionSound(actionType);
    }

    setCurrentBet(amount) {
        this.currentBetAmount = Phaser.Math.Clamp(amount, this.minBet, this.maxBet);
        
        // Update slider position
        const percentage = (this.currentBetAmount - this.minBet) / (this.maxBet - this.minBet);
        this.betSlider.x = 300 + (percentage * 200);
        
        this.updateBetDisplay();
    }

    addChipToBet(chipValue) {
        this.setCurrentBet(this.currentBetAmount + chipValue);
    }

    updateBetDisplay() {
        this.betAmountText.setText(`Bet: $${this.currentBetAmount}`);
        this.updateButtonStates();
    }

    showTurnIndicator(show) {
        if (show) {
            // Create pulsing border or highlight
            if (!this.turnIndicator) {
                this.turnIndicator = this.add.rectangle(400, 300, 780, 580, 0x00FF00, 0)
                    .setStrokeStyle(4, 0x00FF00, 0.8)
                    .setDepth(100);
            }
            
            this.turnIndicator.setVisible(true);
            
            // Pulsing animation
            this.tweens.add({
                targets: this.turnIndicator,
                alpha: 0.3,
                duration: 500,
                yoyo: true,
                repeat: -1
            });
        } else {
            if (this.turnIndicator) {
                this.tweens.killTweensOf(this.turnIndicator);
                this.turnIndicator.setVisible(false);
            }
        }
    }

    startTurnTimer(timeLimit) {
        if (this.turnTimer) {
            this.turnTimer.remove();
        }
        
        let timeLeft = timeLimit;
        this.timerText.setText(`Time: ${timeLeft}s`);
        
        this.turnTimer = this.time.addEvent({
            delay: 1000,
            callback: () => {
                timeLeft--;
                this.timerText.setText(`Time: ${timeLeft}s`);
                
                if (timeLeft <= 0) {
                    // Auto-fold when time runs out
                    this.handleAction('fold');
                }
            },
            repeat: timeLimit - 1
        });
    }

    playSound(soundKey) {
        try {
            const sound = this.sound.get(soundKey);
            if (sound) {
                sound.play({ volume: 0.3 });
            }
        } catch (e) {
            console.warn(`Could not play sound: ${soundKey}`, e);
        }
    }

    playActionSound(actionType) {
        const soundMap = {
            'fold': 'cardFlip',
            'check': 'chipClick',
            'call': 'chipPlace',
            'bet': 'chipPlace',
            'raise': 'chipPlace',
            'allIn': 'chipStack'
        };
        
        const soundKey = soundMap[actionType] || 'chipClick';
        this.playSound(soundKey);
    }

    shutdown() {
        if (this.eventBus) {
            this.eventBus.off('pokerGameStateUpdate', this.updateUI, this);
            this.eventBus.off('pokerPlayerTurn', this.handlePlayerTurn, this);
            this.eventBus.off('pokerActionsAvailable', this.updateAvailableActions, this);
            this.eventBus.off('pokerBettingPhase', this.handleBettingPhase, this);
            this.eventBus.off('pokerGamePhaseChange', this.updateGamePhase, this);
        }
        
        if (this.turnTimer) {
            this.turnTimer.remove();
        }
        
        if (this.turnIndicator) {
            this.tweens.killTweensOf(this.turnIndicator);
        }
    }

    setupEnhancedActionButtons() {
        const buttonConfigs = [
            { key: 'fold', text: 'FOLD', color: 0xff4444, x: 200, y: 550 },
            { key: 'check', text: 'CHECK', color: 0x44aa44, x: 330, y: 550 },
            { key: 'call', text: 'CALL', color: 0x44aa44, x: 330, y: 550 },
            { key: 'bet', text: 'BET', color: 0x4444ff, x: 460, y: 550 },
            { key: 'raise', text: 'RAISE', color: 0x4444ff, x: 460, y: 550 },
            { key: 'allin', text: 'ALL-IN', color: 0xff8800, x: 590, y: 550 }
        ];

        buttonConfigs.forEach(config => {
            const button = this.createEnhancedButton(
                config.x, config.y,
                config.text,
                config.color,
                () => this.handleActionButton(config.key)
            );
            
            this.actionButtons[config.key] = button;
            button.setVisible(false); // Initially hidden
        });
    }

    createEnhancedButton(x, y, text, color, callback) {
        const container = this.add.container(x, y);
        
        // Button background
        const bg = this.add.rectangle(0, 0, 120, 40, color)
            .setStrokeStyle(2, 0xffffff);
        
        // Button text
        const buttonText = this.add.text(0, 0, text, {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#ffffff',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        container.add([bg, buttonText]);
        container.setSize(120, 40);
        container.setInteractive({ useHandCursor: true });
        
        // Enhanced button interactions
        container.on('pointerover', () => {
            this.gameEnhancer.addButtonHoverEffect(container);
            this.soundManager.playButtonHover();
        });
        
        container.on('pointerout', () => {
            this.gameEnhancer.removeButtonHoverEffect(container);
        });
        
        container.on('pointerdown', () => {
            this.gameEnhancer.addButtonClickEffect(container);
            this.soundManager.playButtonClick();
            callback();
        });
        
        return container;
    }

    setupEnhancedBetSlider() {
        const sliderX = 400;
        const sliderY = 500;
        
        // Slider background
        const sliderBg = this.add.rectangle(sliderX, sliderY, 200, 10, 0x333333)
            .setStrokeStyle(1, 0x666666);
        
        // Slider thumb
        const thumb = this.add.circle(sliderX - 100, sliderY, 12, 0xFFD700)
            .setStrokeStyle(2, 0x000000)
            .setInteractive({ draggable: true });
        
        // Bet amount display
        this.betAmountText = this.add.text(sliderX, sliderY - 30, '$0', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Enhanced slider interactions
        thumb.on('drag', (pointer, dragX) => {
            const minX = sliderX - 100;
            const maxX = sliderX + 100;
            const clampedX = Phaser.Math.Clamp(dragX, minX, maxX);
            
            thumb.x = clampedX;
            
            // Calculate bet amount
            const percentage = (clampedX - minX) / (maxX - minX);
            this.currentBetAmount = Math.round(this.minBet + (this.maxBet - this.minBet) * percentage);
            
            // Update display with enhancement
            this.betAmountText.setText(`$${this.currentBetAmount}`);
            this.gameEnhancer.addPulseAnimation(this.betAmountText, 1.1, 100);
            
            // Play slider sound
            this.soundManager.playSliderMove();
        });
        
        this.betSlider = { background: sliderBg, thumb: thumb };
    }

    setupEnhancedChipSelection() {
        const chipValues = [1, 5, 25, 100, 500, 1000];
        const startX = 50;
        const startY = 450;
        
        chipValues.forEach((value, index) => {
            const chipX = startX + (index * 60);
            const chip = this.createEnhancedChip(chipX, startY, value);
            this.chipSelection.push(chip);
        });
    }

    createEnhancedChip(x, y, value) {
        const container = this.add.container(x, y);
        
        // Chip colors based on value
        const colors = {
            1: 0xffffff,     // White
            5: 0xff4444,     // Red  
            25: 0x44aa44,    // Green
            100: 0x000000,   // Black
            500: 0x800080,   // Purple
            1000: 0xffd700   // Gold
        };
        
        const chipColor = colors[value] || 0x888888;
        
        // Chip background
        const chip = this.add.circle(0, 0, 25, chipColor)
            .setStrokeStyle(3, 0xffffff);
        
        // Chip value text
        const chipText = this.add.text(0, 0, `$${value}`, {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: value === 1000 ? '#000000' : '#ffffff',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        container.add([chip, chipText]);
        container.setSize(50, 50);
        container.setInteractive({ useHandCursor: true });
        container.setData('chipValue', value);
        
        // Enhanced chip interactions
        container.on('pointerover', () => {
            this.gameEnhancer.addChipHoverEffect(container);
            this.soundManager.playChipHover();
        });
        
        container.on('pointerout', () => {
            this.gameEnhancer.removeChipHoverEffect(container);
        });
        
        container.on('pointerdown', () => {
            this.selectChip(value);
            this.gameEnhancer.addChipClickEffect(container);
            this.soundManager.playChipClick();
        });
        
        return container;
    }

    selectChip(value) {
        // Update selected chip value
        this.selectedChipValue = value;
        
        // Update bet slider to selected chip value
        this.updateBetSliderToChip(value);
        
        // Visual feedback for selected chip
        this.chipSelection.forEach(chip => {
            const chipValue = chip.getData('chipValue');
            if (chipValue === value) {
                this.gameEnhancer.addGlowEffect(chip, 0xFFD700, 0.8);
            } else {
                this.gameEnhancer.removeGlowEffect(chip);
            }
        });
    }

    updateBetSliderToChip(chipValue) {
        if (!this.betSlider) return;
        
        const percentage = Math.min(chipValue / this.maxBet, 1);
        const sliderWidth = 200;
        const newX = 400 - 100 + (sliderWidth * percentage);
        
        // Animate thumb to new position
        this.tweens.add({
            targets: this.betSlider.thumb,
            x: newX,
            duration: 300,
            ease: 'Power2'
        });
        
        this.currentBetAmount = chipValue;
        this.betAmountText.setText(`$${chipValue}`);
        this.gameEnhancer.addPulseAnimation(this.betAmountText, 1.2, 200);
    }

    setupEnhancedPlayerInfo() {
        // Player info panel
        this.playerInfoPanel = this.add.container(50, 50);
        
        const panel = this.add.rectangle(0, 0, 200, 100, 0x2a2a2a, 0.9)
            .setStrokeStyle(2, 0x666666);
        
        const nameText = this.add.text(-90, -30, 'Player Name', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#ffffff',
            fontStyle: 'bold'
        });
        
        const balanceText = this.add.text(-90, -10, 'Balance: $1000', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#44aa44'
        });
        
        const stackText = this.add.text(-90, 10, 'Stack: $500', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFD700'
        });
        
        this.playerInfoPanel.add([panel, nameText, balanceText, stackText]);
        this.playerInfoPanel.setDepth(20);
    }

    setupEnhancedPotDisplay() {
        this.potDisplay = this.add.container(400, 50);
        
        const potBg = this.add.rectangle(0, 0, 150, 60, 0x2a5a2a, 0.9)
            .setStrokeStyle(2, 0xFFD700);
        
        const potLabel = this.add.text(0, -15, 'POT', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.potAmountText = this.add.text(0, 10, '$0', {
            fontSize: '20px',
            fontFamily: 'Arial',
            fill: '#ffffff',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.potDisplay.add([potBg, potLabel, this.potAmountText]);
        this.potDisplay.setDepth(20);
    }

    handleActionButton(action) {
        // Enhanced action handling with feedback
        switch(action) {
            case 'fold':
                this.performFold();
                break;
            case 'check':
                this.performCheck();
                break;
            case 'call':
                this.performCall();
                break;
            case 'bet':
                this.performBet();
                break;
            case 'raise':
                this.performRaise();
                break;
            case 'allin':
                this.performAllIn();
                break;
        }
    }

    performFold() {
        this.gameEnhancer.addScreenFlash(0xff4444, 0.3, 200);
        this.gameEnhancer.addFloatingText(400, 300, 'FOLD', '#ff4444', 24);
        this.eventBus?.emit('pokerAction', { action: 'fold' });
        this.hideActionButtons();
    }

    performCheck() {
        this.gameEnhancer.addFloatingText(400, 300, 'CHECK', '#44aa44', 24);
        this.eventBus?.emit('pokerAction', { action: 'check' });
        this.hideActionButtons();
    }

    performCall() {
        this.gameEnhancer.addFloatingText(400, 300, 'CALL', '#44aa44', 24);
        this.eventBus?.emit('pokerAction', { action: 'call' });
        this.hideActionButtons();
    }

    performBet() {
        if (this.currentBetAmount > 0) {
            this.gameEnhancer.addFloatingText(400, 300, `BET $${this.currentBetAmount}`, '#4444ff', 24);
            this.eventBus?.emit('pokerAction', { action: 'bet', amount: this.currentBetAmount });
            this.hideActionButtons();
        }
    }

    performRaise() {
        if (this.currentBetAmount > 0) {
            this.gameEnhancer.addFloatingText(400, 300, `RAISE $${this.currentBetAmount}`, '#4444ff', 24);
            this.eventBus?.emit('pokerAction', { action: 'raise', amount: this.currentBetAmount });
            this.hideActionButtons();
        }
    }

    performAllIn() {
        this.gameEnhancer.addScreenFlash(0xff8800, 0.5, 500);
        this.gameEnhancer.addFloatingText(400, 300, 'ALL-IN!', '#ff8800', 32);
        this.gameEnhancer.createFireworkEffect(400, 300);
        this.eventBus?.emit('pokerAction', { action: 'allin' });
        this.hideActionButtons();
    }

    showActionButtons(availableActions) {
        this.availableActions = availableActions;
        
        // Hide all buttons first
        Object.values(this.actionButtons).forEach(button => button.setVisible(false));
        
        // Show available actions with stagger animation
        availableActions.forEach((action, index) => {
            if (this.actionButtons[action]) {
                this.time.delayedCall(index * 100, () => {
                    this.actionButtons[action].setVisible(true);
                    this.gameEnhancer.addBounceAnimation(this.actionButtons[action]);
                });
            }
        });
    }

    hideActionButtons() {
        Object.values(this.actionButtons).forEach((button, index) => {
            this.time.delayedCall(index * 50, () => {
                this.tweens.add({
                    targets: button,
                    alpha: 0,
                    scaleX: 0.8,
                    scaleY: 0.8,
                    duration: 200,
                    onComplete: () => {
                        button.setVisible(false);
                        button.setAlpha(1);
                        button.setScale(1);
                    }
                });
            });
        });
    }

    updatePotAmount(amount) {
        if (this.potAmountText) {
            this.potAmountText.setText(`$${amount}`);
            this.gameEnhancer.addPulseAnimation(this.potAmountText, 1.2, 300);
            
            // Add coin effect for pot increase
            if (amount > 0) {
                this.gameEnhancer.createCoinEffect(400, 50);
            }
        }
    }

    updatePlayerBalance(balance) {
        // Update player info panel with new balance
        if (this.playerInfoPanel) {
            const balanceText = this.playerInfoPanel.list[2]; // Third element
            balanceText.setText(`Balance: $${balance}`);
            this.gameEnhancer.addPulseAnimation(balanceText, 1.1, 200);
        }
    }

    showWinAnimation(amount) {
        this.gameEnhancer.addScreenFlash(0x00ff00, 0.4, 600);
        this.gameEnhancer.addFloatingText(400, 200, `YOU WIN $${amount}!`, '#00ff00', 36);
        this.gameEnhancer.createFireworkEffect(400, 300);
        this.soundManager.playWin();
    }

    showLoseAnimation() {
        this.gameEnhancer.addScreenFlash(0xff4444, 0.3, 400);
        this.gameEnhancer.addFloatingText(400, 200, 'BETTER LUCK NEXT TIME', '#ff4444', 24);
        this.soundManager.playLose();
    }
}
