import Phaser from 'phaser';
// EventBus is now retrieved from registry in create()
// import EventBus from '@/event-bus';
import { formatSatsToBtc } from '@utils/currencyFormatter';

export default class UIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'UIScene' });

    // UI elements
    this.balanceText = null;
    this.betText = null;
    this.winText = null; // For displaying round win amount
    this.messageText = null; // For messages like "Bust!", "Blackjack!"

    this.dealButton = null;
    this.hitButton = null;
    this.standButton = null;
    this.doubleButton = null;
    this.splitButton = null;
    this.rebetButton = null; // For re-betting same amount
    this.newRoundButton = null; // For starting new round with potentially different bet

    this.betAdjustContainer = null; // Container for chip buttons or +/-
    this.chipButtons = []; // Array to hold chip GameObjects

    // State
    this.currentBetSats = 0;
    this.activeHandIndex = 0; // To know which hand actions apply to (for splits)
    this.isPlaying = false; // True when a round is in progress

    // From registry
    this.eventBus = null;
    this.tableAPIData = null;
    this.gameDefinition = null;
    this.soundEnabled = true;
  }

  create() {
    console.log('UIScene: create()');
    this.eventBus = this.registry.get('eventBus');
    this.tableAPIData = this.registry.get('tableAPIData');
    this.gameDefinition = this.registry.get('gameDefinition');
    this.soundEnabled = this.registry.get('soundEnabled') ?? true;

    if (!this.eventBus || !this.tableAPIData || !this.gameDefinition) {
      console.error("UIScene: Critical data not found in registry! Aborting.");
      return;
    }

    this.currentBetSats = this.tableAPIData.min_bet || this.gameDefinition.settings.betOptions[0] || 10;

    const initialBalance = this.registry.get('userBalance') || 0;

    this.createBalanceDisplay(initialBalance);
    this.createBetDisplayAndControls(this.currentBetSats);
    this.createWinDisplay();
    this.createMessageDisplay();
    this.createActionButtons();

    // Event Listeners
    this.eventBus.on('updateButtonStates', this.handleUpdateButtonStates, this);
    this.eventBus.on('roundEndedUI', this.handleRoundEndedUI, this);
    this.eventBus.on('userBalanceUpdate', this.updateBalanceDisplay, this);
    this.eventBus.on('initialDeal', this.handleInitialDealUI, this);
    this.eventBus.on('dealFailed', this.handleDealFailed, this);
    this.eventBus.on('actionFailed', this.handleActionFailed, this);


    this.setInitialUIState();
    console.log('UIScene: Ready.');
  }

  setInitialUIState() {
    this.isPlaying = false;
    this.dealButton.setVisible(true).setActive(true);
    this.rebetButton.setVisible(false).setActive(false);
    this.newRoundButton.setVisible(false).setActive(false);

    this.hitButton.setVisible(false).setActive(false);
    this.standButton.setVisible(false).setActive(false);
    this.doubleButton.setVisible(false).setActive(false);
    this.splitButton.setVisible(false).setActive(false);
    
    this.betAdjustContainer.setVisible(true);
    this.winText.setVisible(false);
    this.messageText.setText('').setVisible(false);
    this.updateBetButtonStates();
  }

  // --- UI Element Creation ---
  createBalanceDisplay(initialBalance) {
    const config = this.gameDefinition.ui.balance;
    this.balanceText = this.add.text(config.x, config.y, `Balance: ${formatSatsToBtc(initialBalance, true)}`, config.style)
      .setOrigin(config.origin?.x || 0.5, config.origin?.y || 0.5);
  }

  createBetDisplayAndControls(initialBet) {
    const config = this.gameDefinition.ui.bet;
    this.betText = this.add.text(config.x, config.y, `Bet: ${formatSatsToBtc(initialBet)}`, config.style)
      .setOrigin(config.origin?.x || 0.5, config.origin?.y || 0.5);

    this.betAdjustContainer = this.add.container(config.controlsX || config.x, config.controlsY || (config.y + 50));

    const chipValues = this.gameDefinition.settings.chipValues || [10, 25, 100, 500];
    const chipSpacing = (this.gameDefinition.ui.chips.spacing || 60);
    const totalChipWidth = (chipValues.length -1) * chipSpacing;
    let currentChipX = -totalChipWidth / 2;

    chipValues.forEach(value => {
      const chipButton = this.add.image(currentChipX, 0, `chip-${value}`)
        .setDisplaySize(this.gameDefinition.ui.chips.width || 50, this.gameDefinition.ui.chips.height || 50)
        .setInteractive({ useHandCursor: true })
        .on('pointerdown', () => {
          if (!this.isPlaying) {
            this.playSound('snd-chip-place');
            this.setBet(value);
          }
        });
      this.chipButtons.push(chipButton);
      this.betAdjustContainer.add(chipButton);
      currentChipX += chipSpacing;
    });
  }

  createWinDisplay() {
    const config = this.gameDefinition.ui.win;
    this.winText = this.add.text(config.x, config.y, '', config.style)
      .setOrigin(config.origin?.x || 0.5, config.origin?.y || 0.5)
      .setVisible(false);
  }

  createMessageDisplay() {
    const config = this.gameDefinition.ui.messageText;
    this.messageText = this.add.text(config.x, config.y, '', config.style)
      .setOrigin(config.origin?.x || 0.5, config.origin?.y || 0.5)
      .setDepth(100)
      .setVisible(false);
  }

  createActionButtons() {
    const positions = this.gameDefinition.ui.buttonPositions;
    const styles = this.gameDefinition.ui.buttons;

    this.dealButton = this.createButton('Deal', positions.deal, styles.deal, () => {
      if(this.registry.get('userBalance') < this.currentBetSats){
        this.messageText.setText("Not enough balance for current bet!").setVisible(true).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
        this.playSound('snd-lose');
        return;
      }
      this.eventBus.emit('blackjackDealRequest', { betAmount: this.currentBetSats });
      this.playSound('snd-button-click');
    });

    this.hitButton = this.createButton('Hit', positions.hit, styles.action, () => {
      this.eventBus.emit('blackjackActionRequest', { action: 'hit', hand_index: this.activeHandIndex });
      this.playSound('snd-button-click');
    });

    this.standButton = this.createButton('Stand', positions.stand, styles.action, () => {
      this.eventBus.emit('blackjackActionRequest', { action: 'stand', hand_index: this.activeHandIndex });
      this.playSound('snd-button-click');
    });

    this.doubleButton = this.createButton('Double', positions.double, styles.action, () => {
      this.eventBus.emit('blackjackActionRequest', { action: 'double', hand_index: this.activeHandIndex });
      this.playSound('snd-button-click');
    });

    this.splitButton = this.createButton('Split', positions.split, styles.action, () => {
      this.eventBus.emit('blackjackActionRequest', { action: 'split', hand_index: this.activeHandIndex });
      this.playSound('snd-button-click');
    });
    
    this.rebetButton = this.createButton('Rebet', positions.rebet || positions.deal, styles.deal, () => {
        if(this.registry.get('userBalance') < this.currentBetSats){
            this.messageText.setText("Not enough balance for last bet! Adjust bet.").setVisible(true).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
            this.playSound('snd-lose');
            return;
        }
        this.eventBus.emit('blackjackDealRequest', { betAmount: this.currentBetSats });
        this.playSound('snd-button-click');
    }).setVisible(false);

    this.newRoundButton = this.createButton('New Round', positions.newRound || {x: positions.deal.x + 150, y: positions.deal.y }, styles.deal, () => {
        this.setBet(this.tableAPIData.min_bet);
        if(this.registry.get('userBalance') < this.currentBetSats){
            this.messageText.setText("Not enough balance for minimum bet!").setVisible(true).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
            this.playSound('snd-lose');
            return;
        }
        this.eventBus.emit('blackjackDealRequest', { betAmount: this.currentBetSats });
        this.playSound('snd-button-click');
    }).setVisible(false);
  }

  createButton(text, pos, styleConfig, callback) {
    const button = this.add.image(pos.x, pos.y, styleConfig.texture)
      .setOrigin(styleConfig.origin?.x || 0.5, styleConfig.origin?.y || 0.5)
      .setInteractive({ useHandCursor: true })
      .on('pointerdown', callback);
    
    if (styleConfig.textStyle && text) {
        const label = this.add.text(pos.x + (styleConfig.textOffset?.x || 0), pos.y + (styleConfig.textOffset?.y || 0), text, styleConfig.textStyle)
            .setOrigin(styleConfig.textOrigin?.x || 0.5, styleConfig.textOrigin?.y || 0.5);
        button.setData('label', label);
    }
    return button;
  }

  // --- Event Handlers ---
  handleInitialDealUI(handData) {
    this.isPlaying = true;
    this.activeHandIndex = handData.active_hand_index;
    
    this.dealButton.setVisible(false).setActive(false);
    this.rebetButton.setVisible(false).setActive(false);
    this.newRoundButton.setVisible(false).setActive(false);
    this.betAdjustContainer.setVisible(false);
    
    this.winText.setVisible(false);
    this.messageText.setText('').setVisible(false);
    
    this.updateActionButtonsVisibility(handData);
  }

  handleUpdateButtonStates(data) {
    this.activeHandIndex = data.active_hand_index;
    if (this.isPlaying && data.status !== 'completed') {
        this.updateActionButtonsVisibility(data);
    }
  }

  updateActionButtonsVisibility(data) {
    // Ensure data and player_hands exist and active_hand_index is valid
    if (!data || !data.player_hands || !data.player_hands[data.active_hand_index]) {
        // All action buttons hidden if data is incomplete
        this.hitButton.setVisible(false).setActive(false);
        this.standButton.setVisible(false).setActive(false);
        this.doubleButton.setVisible(false).setActive(false);
        this.splitButton.setVisible(false).setActive(false);
        return;
    }
    const currentPlayersHand = data.player_hands[data.active_hand_index];
    const canPerformAction = !currentPlayersHand.is_standing && !currentPlayersHand.is_busted;

    this.hitButton.setVisible(data.canHit && canPerformAction).setActive(data.canHit && canPerformAction);
    this.standButton.setVisible(data.canStand && canPerformAction).setActive(data.canStand && canPerformAction);
    this.doubleButton.setVisible(data.canDouble && canPerformAction).setActive(data.canDouble && canPerformAction);
    this.splitButton.setVisible(data.canSplit && canPerformAction).setActive(data.canSplit && canPerformAction);

    this.hitButton.getData('label')?.setVisible(this.hitButton.visible);
    this.standButton.getData('label')?.setVisible(this.standButton.visible);
    this.doubleButton.getData('label')?.setVisible(this.doubleButton.visible);
    this.splitButton.getData('label')?.setVisible(this.splitButton.visible);
  }

  handleRoundEndedUI(outcomeData) {
    this.isPlaying = false;
    this.activeHandIndex = -1;

    this.hitButton.setVisible(false).setActive(false);
    this.standButton.setVisible(false).setActive(false);
    this.doubleButton.setVisible(false).setActive(false);
    this.splitButton.setVisible(false).setActive(false);
    this.hitButton.getData('label')?.setVisible(false);
    this.standButton.getData('label')?.setVisible(false);
    this.doubleButton.getData('label')?.setVisible(false);
    this.splitButton.getData('label')?.setVisible(false);

    this.dealButton.setVisible(false).setActive(false); // Keep Deal hidden
    this.rebetButton.setVisible(true).setActive(true);
    this.newRoundButton.setVisible(true).setActive(true);
    
    this.betAdjustContainer.setVisible(true);

    if (outcomeData.win_amount > 0) {
      this.winText.setText(`WIN: ${formatSatsToBtc(outcomeData.win_amount)}`).setVisible(true);
    } else {
      this.winText.setVisible(false);
    }
    // GameScene is responsible for per-hand messages. UIScene can show overall.
    // Example: this.messageText.setText("Round Over!").setVisible(true);

    this.updateBalanceDisplay(this.registry.get('userBalance'));
    this.updateBetButtonStates();
  }

  handleDealFailed(error) {
    this.isPlaying = false;
    this.messageText.setText(error.status_message || 'Deal failed.').setVisible(true).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
    this.setInitialUIState();
  }

  handleActionFailed(error) {
    this.messageText.setText(error.status_message || 'Action failed.').setVisible(true).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
    // Buttons state might need refresh based on GameScene's next 'updateButtonStates'
  }

  updateBalanceDisplay(newBalance) {
    this.balanceText.setText(`Balance: ${formatSatsToBtc(newBalance, true)}`);
    this.registry.set('userBalance', newBalance);
    this.updateBetButtonStates();
  }

  updateBetButtonStates() {
    const currentBalance = this.registry.get('userBalance') || 0;
    const canAffordCurrentBet = currentBalance >= this.currentBetSats;

    const dealActive = canAffordCurrentBet && !this.isPlaying;
    this.dealButton.setAlpha(dealActive ? 1 : 0.5).setActive(dealActive);
    this.rebetButton.setAlpha(canAffordCurrentBet && !this.isPlaying ? 1 : 0.5).setActive(canAffordCurrentBet && !this.isPlaying);
    
    const minBet = this.tableAPIData.min_bet || this.gameDefinition.settings.betOptions[0] || 10;
    const newRoundActive = currentBalance >= minBet && !this.isPlaying;
    this.newRoundButton.setAlpha(newRoundActive ? 1 : 0.5).setActive(newRoundActive);

    this.chipButtons.forEach(chip => {
        chip.setAlpha(this.isPlaying ? 0.5 : 1.0);
        if (this.isPlaying) chip.disableInteractive();
        else chip.setInteractive({useHandCursor: true});
    });
  }

  setBet(amount) {
    if (this.isPlaying) return;
    this.currentBetSats = Math.max(this.tableAPIData.min_bet, Math.min(amount, this.tableAPIData.max_bet));
    this.betText.setText(`Bet: ${formatSatsToBtc(this.currentBetSats)}`);
    this.updateBetButtonStates();
  }

  playSound(key) {
    if (this.soundEnabled && key && this.sound.get(key)) {
      this.sound.play(key);
    } else if (this.soundEnabled && key) {
        console.warn(`UIScene: Sound key "${key}" not found.`);
    }
  }

  shutdown() {
    console.log('UIScene: shutdown');
    if (this.eventBus) {
      this.eventBus.off('updateButtonStates', this.handleUpdateButtonStates, this);
      this.eventBus.off('roundEndedUI', this.handleRoundEndedUI, this);
      this.eventBus.off('userBalanceUpdate', this.updateBalanceDisplay, this);
      this.eventBus.off('initialDeal', this.handleInitialDealUI, this);
      this.eventBus.off('dealFailed', this.handleDealFailed, this);
      this.eventBus.off('actionFailed', this.handleActionFailed, this);
    }
  }
}
