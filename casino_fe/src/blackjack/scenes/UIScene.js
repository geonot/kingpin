import Phaser from 'phaser';
import EventBus from '@/event-bus';
import { formatSatsToBtc } from '@utils/currencyFormatter'; // Import formatter

export default class UIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'UIScene' });

    // UI elements
    this.balanceText = null;
    this.betText = null;
    this.winText = null;
    this.messageText = null;
    this.dealerTotalText = null;
    this.playerTotalText = null;
    this.dealButton = null;
    this.hitButton = null;
    this.standButton = null;
    this.doubleButton = null;
    this.splitButton = null;
    this.betPlusButton = null;
    this.betMinusButton = null;
    
    // Button text labels
    this.hitButtonText = null;
    this.standButtonText = null;
    this.doubleButtonText = null;
    this.splitButtonText = null;
    this.settingsButton = null;
    this.chipButtons = [];

    // State
    this.currentBetIndex = 0;
    this.betOptions = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]; // Default, loaded from config
    this.currentBetSats = 10;
    this.isPlaying = false; // Local state to disable buttons during play
    this.soundEnabled = true;
    this.playerTurnActive = false;
  }

  create() {
    console.log('UIScene: Create');
    const gameConfig = this.registry.get('gameConfig');
    if (!gameConfig) {
      console.error("UIScene: Game config not found!");
      return;
    }
    
    // Initialize state from registry
    this.soundEnabled = this.registry.get('soundEnabled') ?? true;

    // Get bet options from config or use default
    this.betOptions = gameConfig.settings?.betOptions || this.betOptions;
    this.currentBetSats = this.registry.get('initialBet') || this.betOptions[0] || 10;
    this.currentBetIndex = this.betOptions.indexOf(this.currentBetSats);
    if (this.currentBetIndex === -1) { // If initialBet not in options, default to first
      this.currentBetIndex = 0;
      this.currentBetSats = this.betOptions[0];
    }

    const initialBalance = this.registry.get('userBalance') ?? 10000; // Default balance for testing

    // Create UI elements using config positions/styles if available
    this.createBalanceDisplay(initialBalance, gameConfig.ui?.balance);
    this.createBetDisplay(this.currentBetSats, gameConfig.ui?.bet);
    this.createWinDisplay(0, gameConfig.ui?.win);
    this.createMessageDisplay();
    this.createChipButtons();
    this.createActionButtons(gameConfig.ui?.buttons);

    // --- Event Listeners ---
    // Listen for updates from GameScene or Vue app
    EventBus.$on('uiUpdate', (data) => {
      if (data.balance !== undefined) {
        this.updateBalance(data.balance);
      }
      if (data.balanceInsufficient !== undefined) {
        this.handleInsufficientBalance(data.balanceInsufficient);
      }
    });

    // Listen for hand updates from GameScene
    EventBus.$on('handUpdated', (data) => {
      this.updateHandDisplay(data);
    });

    // Listen for player turn events from GameScene
    EventBus.$on('playerTurn', (data) => {
      this.playerTurnActive = true;
      this.updateActionButtons(data);
    });

    // Listen for round end events from GameScene
    EventBus.$on('roundEnded', (data) => {
      this.handleRoundEnd(data);
    });

    // Listen for settings changes
    EventBus.$on('soundSettingChanged', (isEnabled) => {
      this.soundEnabled = isEnabled;
      // Update sound button visuals if any in this scene
    });
    
    // Listen for UI reset events
    EventBus.$on('resetUI', () => {
      // Clear message text
      if (this.messageText) {
        this.messageText.setText('');
        this.messageText.setVisible(false);
      }
      
      // Clear dealer and player total texts
      if (this.dealerTotalText) {
        this.dealerTotalText.setText('');
        this.dealerTotalText.setVisible(false);
      }
      
      // Don't hide player total if it has a value - just reset it when empty
      if (this.playerTotalText) {
        this.playerTotalText.setText('');
        this.playerTotalText.setVisible(false);
      }
      
      // Clear win text
      if (this.winText) {
        this.winBackground.setVisible(false);
        this.winLabel.setVisible(false);
        this.winText.setVisible(false);
      }
    });

    console.log('UIScene: Ready.');
  }

  // --- UI Element Creation ---

  createBalanceDisplay(initialBalance, config) {
    const pos = config?.position || { x: 150, y: 550 };
    const style = config?.style || { font: 'bold 24px Arial', color: '#ffffff', align: 'center' };
    const labelStyle = { font: '16px Arial', color: '#cccccc', align: 'center' };

    this.add.text(pos.x, pos.y - 20, 'Balance', labelStyle).setOrigin(0.5);
    this.balanceText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialBalance, true), style).setOrigin(0.5);
  }

  createBetDisplay(initialBet, config) {
    const pos = config?.position || { x: 650, y: 550 };
    const style = config?.style || { font: 'bold 24px Arial', color: '#ffffff', align: 'center' };
    const labelStyle = { font: '16px Arial', color: '#cccccc', align: 'center' };
    const adjustStyle = { font: 'bold 32px Arial', color: '#ffffff' };
    const minusPos = { x: pos.x - 60, y: pos.y + 5 };
    const plusPos = { x: pos.x + 60, y: pos.y + 5 };

    this.add.text(pos.x, pos.y - 20, 'Bet', labelStyle).setOrigin(0.5);
    this.betText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialBet), style).setOrigin(0.5);

    // Minus Button
    this.betMinusButton = this.add.text(minusPos.x, minusPos.y, '-', adjustStyle)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true })
      .on('pointerdown', () => this.adjustBet(-1));

    // Plus Button
    this.betPlusButton = this.add.text(plusPos.x, plusPos.y, '+', adjustStyle)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true })
      .on('pointerdown', () => this.adjustBet(1));

    this.updateBetButtonStates(); // Disable +/- if at min/max bet
  }

  createWinDisplay(initialWin, config) {
    const { width, height } = this.cameras.main;
    const pos = config?.position || { x: width / 2, y: height - 50 }; // Position at bottom center of screen
    const style = config?.style || {
      font: 'bold 28px Arial',
      color: '#FFD700',
      align: 'center',
      stroke: '#000000',
      strokeThickness: 3,
      shadow: { blur: 5, color: '#000000', fill: true }
    }; // Gold color with black outline for better visibility
    const labelStyle = {
      font: '18px Arial',
      color: '#ffffff',
      align: 'center',
      stroke: '#000000',
      strokeThickness: 2
    };

    // Create a background for better visibility
    this.winBackground = this.add.rectangle(pos.x, pos.y, 300, 80, 0x000000, 0.6)
      .setOrigin(0.5)
      .setVisible(false);
      
    this.winLabel = this.add.text(pos.x, pos.y - 20, 'WIN AMOUNT', labelStyle).setOrigin(0.5);
    this.winText = this.add.text(pos.x, pos.y + 10, formatSatsToBtc(initialWin, true), style).setOrigin(0.5);
    
    // Initially hide the win display
    this.winLabel.setVisible(false);
    this.winText.setVisible(false);
  }

  createMessageDisplay() {
    const { width, height } = this.cameras.main;
    const style = { font: 'bold 28px Arial', color: '#ffffff', align: 'center', backgroundColor: 'rgba(0,0,0,0.5)', padding: { x: 10, y: 5 } };
    
    // Create message text for general messages
    this.messageText = this.add.text(width / 2, height * 0.39, '', style)
      .setOrigin(0.5)
      .setDepth(100); // Set a high depth value to ensure it appears in front of cards
    this.messageText.setVisible(false); // Initially hidden
    
    // Create separate text objects for dealer and player totals
    const dealerTotalStyle = { 
      font: 'bold 24px Arial', 
      color: '#ffffff', 
      align: 'center', 
      backgroundColor: 'rgba(0,0,0,0.7)',
      padding: { x: 8, y: 4 }
    };
    
    const playerTotalStyle = {
      font: 'bold 24px Arial', // Even larger font size
      color: '#00ffff', // Cyan color for maximum contrast and visibility
      align: 'center',
      backgroundColor: 'rgba(0,0,0,0.7)', // Nearly opaque background

    };
    
    // Dealer total text - positioned above dealer cards
    this.dealerTotalText = this.add.text(width / 2, height * 0.25, '', dealerTotalStyle)
      .setOrigin(0.5)
      .setDepth(100); // High depth to appear in front of cards
    this.dealerTotalText.setVisible(false);
    
    // Player total text - positioned ABOVE the player's cards like the dealer total
    this.playerTotalText = this.add.text(width / 2, height * 0.85, '', playerTotalStyle)
      .setOrigin(0.5)
      .setDepth(100) // High depth to ensure it's always on top
    
    this.playerTotalText.setVisible(true);
  }

  createChipButtons() {
    const { width, height } = this.cameras.main;
    const chipValues = [10, 20, 50, 100, 500, 1000];
    const startX = width / 2 - ((chipValues.length - 1) * 60) / 2;
    const y = height * 0.85;
    
    chipValues.forEach((value, index) => {
      const x = startX + index * 60;
      const chip = this.add.image(x, y, `chip-${value}`)
        .setDisplaySize(50, 50)
        .setInteractive({ useHandCursor: true });
      
      chip.on('pointerdown', () => {
        this.playSound('chip-place');
        this.setBet(value);
      });
      
      this.chipButtons.push(chip);
    });
  }

  createActionButtons(config) {
    const { width, height } = this.cameras.main;
    const buttonY = height * 0.75;
    const buttonSpacing = 100;
    
    // Deal Button
    this.dealButton = this.add.image(width / 2, buttonY, 'bet-button')
      .setDisplaySize(120, 60)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true });
    
    this.add.text(width / 2, buttonY, 'DEAL', {
      font: 'bold 20px Arial', color: '#000000', stroke: '#ffffff', strokeThickness: 1
    }).setOrigin(0.5);
    
    this.dealButton.on('pointerdown', () => {
      if (this.isPlaying) return;
      
      this.playSound('button-click');
      this.isPlaying = true;
      
      // Update visual appearance
      this.dealButton.setAlpha(0.6);
      this.betPlusButton.setAlpha(0.5);
      this.betMinusButton.setAlpha(0.5);
      
      // Disable chip buttons
      this.chipButtons.forEach(chip => chip.setAlpha(0.5));
      
      // Clear any previous message text
      if (this.messageText) {
        this.messageText.setText('');
        this.messageText.setVisible(false);
      }
      
      // Clear any previous win display
      if (this.winText) {
        this.winText.setVisible(false);
      }
      
      // Emit deal request event
      EventBus.$emit('dealRequest', { bet: this.currentBetSats });
    });
    
    // Hit Button
    this.hitButton = this.add.image(width / 2 - buttonSpacing, buttonY, 'hit-button')
      .setDisplaySize(80, 40)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true })
      .setVisible(false);
    
    this.hitButtonText = this.add.text(width / 2 - buttonSpacing, buttonY, 'HIT', {
      font: 'bold 16px Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 1
    }).setOrigin(0.5).setVisible(false);
    
    this.hitButton.on('pointerdown', () => {
      if (!this.playerTurnActive) return;
      
      this.playSound('button-click');
      EventBus.$emit('actionRequest', { action: 'hit' });
      
      // Disable hit button immediately after clicking to prevent multiple hits
      this.hitButton.setAlpha(0.5);
      this.hitButton.disableInteractive();
      setTimeout(() => {
        this.hitButton.setAlpha(1);
        this.hitButton.setInteractive({ useHandCursor: true });
      }, 500); // Re-enable after 500ms to prevent accidental double-clicks
    });
    
    // Stand Button
    this.standButton = this.add.image(width / 2, buttonY, 'stand-button')
      .setDisplaySize(80, 40)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true })
      .setVisible(false);
    
    this.standButtonText = this.add.text(width / 2, buttonY, 'STAND', {
      font: 'bold 16px Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 1
    }).setOrigin(0.5).setVisible(false);
    
    this.standButton.on('pointerdown', () => {
      if (!this.playerTurnActive) return;
      
      this.playSound('button-click');
      EventBus.$emit('actionRequest', { action: 'stand' });
      
      // Immediately set playerTurnActive to false to prevent further actions
      this.playerTurnActive = false;
      
      // Disable all action buttons
      this.hitButton.setVisible(false);
      this.hitButtonText.setVisible(false);
      this.standButton.setVisible(false);
      this.standButtonText.setVisible(false);
      this.doubleButton.setVisible(false);
      this.doubleButtonText.setVisible(false);
      this.splitButton.setVisible(false);
      this.splitButtonText.setVisible(false);
    });
    
    // Double Button
    this.doubleButton = this.add.image(width / 2 + buttonSpacing, buttonY, 'double-button')
      .setDisplaySize(80, 40)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true })
      .setVisible(false);
    
    this.doubleButtonText = this.add.text(width / 2 + buttonSpacing, buttonY, 'DOUBLE', {
      font: 'bold 16px Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 1
    }).setOrigin(0.5).setVisible(false);
    
    this.doubleButton.on('pointerdown', () => {
      if (!this.playerTurnActive) return;
      
      this.playSound('button-click');
      EventBus.$emit('actionRequest', { action: 'double' });
    });
    
    // Split Button
    this.splitButton = this.add.image(width / 2 + buttonSpacing * 2, buttonY, 'split-button')
      .setDisplaySize(80, 40)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true })
      .setVisible(false);
    
    this.splitButtonText = this.add.text(width / 2 + buttonSpacing * 2, buttonY, 'SPLIT', {
      font: 'bold 16px Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 1
    }).setOrigin(0.5).setVisible(false);
    
    this.splitButton.on('pointerdown', () => {
      if (!this.playerTurnActive) return;
      
      this.playSound('button-click');
      EventBus.$emit('actionRequest', { action: 'split' });
    });
    
    // Settings Button
    const settingsPos = { x: width - 50, y: 50 };
    this.settingsButton = this.add.image(settingsPos.x, settingsPos.y, 'settings-button')
      .setDisplaySize(40, 40)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true });
    
    this.settingsButton.on('pointerdown', () => {
      this.playSound('button-click');
      // Implement settings modal if needed
    });
  }

  // --- UI Update Methods ---

  updateBalance(newBalanceSats) {
    if (this.balanceText) {
      this.balanceText.setText(formatSatsToBtc(newBalanceSats, true));
      this.handleInsufficientBalance(newBalanceSats < this.currentBetSats);
    }
  }

  setBet(betAmount) {
    if (this.isPlaying) return;
    
    this.currentBetSats = betAmount;
    this.updateBetSize(betAmount);
  }

  updateBetSize(newBetSats) {
    if (this.betText) {
      this.betText.setText(formatSatsToBtc(newBetSats));
      this.currentBetSats = newBetSats;
      // Optionally, update registry if other scenes need current bet
      this.registry.set('currentBet', newBetSats);
      this.updateBetButtonStates(); // Enable/disable +/- buttons
      // Check if new bet exceeds balance
      this.handleInsufficientBalance(this.registry.get('userBalance') < newBetSats);
    }
  }

  updateBetButtonStates() {
    if (this.betMinusButton) {
      const canDecrease = this.currentBetIndex > 0 && !this.isPlaying;
      // Update visual appearance only
      this.betMinusButton.setAlpha(canDecrease ? 1 : 0.5);
    }

    if (this.betPlusButton) {
      const canIncrease = this.currentBetIndex < this.betOptions.length - 1 && !this.isPlaying;
      // Update visual appearance only
      this.betPlusButton.setAlpha(canIncrease ? 1 : 0.5);
    }
  }

  updateHandDisplay(data) {
    // Check if data has the required properties
    if (!data) {
      console.warn('UIScene: updateHandDisplay called with no data');
      return;
    }
    
    // Check if player_hands exists and is an array
    if (!data.player_hands || !Array.isArray(data.player_hands)) {
      console.warn('UIScene: updateHandDisplay called with invalid player_hands data', data);
      return;
    }
    
    // Check if current_hand_index is valid
    const currentHandIndex = data.current_hand_index ?? 0;
    if (currentHandIndex < 0 || currentHandIndex >= data.player_hands.length) {
      console.warn(`UIScene: Invalid current_hand_index ${currentHandIndex} for player_hands of length ${data.player_hands.length}`);
      return;
    }
    
    // Get the current player hand and dealer hand
    const playerHand = data.player_hands[currentHandIndex];
    const dealerHand = data.dealer_hand;
    
    if (!playerHand || !dealerHand) {
      console.warn('UIScene: Missing playerHand or dealerHand data', { playerHand, dealerHand });
      return;
    }
    
    // Update dealer total
    this.dealerTotalText.setText(`Dealer: ${dealerHand.total}`);
    this.dealerTotalText.setVisible(true);
    
    // Update player total with a more prominent label
    this.playerTotalText.setText(`YOUR TOTAL: ${playerHand.total}`);
    this.playerTotalText.setVisible(true);
    
    this.tweens.killTweensOf(this.playerTotalText); // Stop any existing tweens
    
    // Add a border glow effect
    this.playerTotalText.setShadow(0, 0, '#ff0000', 8, true, true);
    
    // Reset shadow after animation
    this.time.delayedCall(2000, () => {
      this.playerTotalText.setShadow(3, 3, '#000000', 8, false, true);
    });
    
    // Hide the general message text if it was showing
    this.messageText.setVisible(false);
  }

  updateActionButtons(data) {
    // Only update hand display if data has the required properties
    if (data && data.player_hands && Array.isArray(data.player_hands) && data.dealer_hand) {
      this.updateHandDisplay(data);
    } else {
      console.warn('UIScene: updateActionButtons called with invalid data for updateHandDisplay', data);
    }
    
    // Show/hide action buttons based on available actions
    this.dealButton.setVisible(false);
    
    // Hide chip buttons during play
    this.chipButtons.forEach(chip => chip.setVisible(false));
    
    // Update hit button visibility - only allow hit if canHit is true and player hasn't stood
    const canHit = data && data.canHit;
    this.hitButton.setVisible(canHit);
    if (this.hitButtonText) {
      this.hitButtonText.setVisible(canHit);
    }
    
    // Update stand button visibility
    const canStand = data && data.canStand;
    this.standButton.setVisible(canStand);
    if (this.standButtonText) {
      this.standButtonText.setVisible(canStand);
    }
    
    // Update double button visibility
    const canDouble = data && data.canDouble;
    this.doubleButton.setVisible(canDouble);
    if (this.doubleButtonText) {
      this.doubleButtonText.setVisible(canDouble);
    }
    
    // Update split button visibility
    const canSplit = data && data.canSplit;
    this.splitButton.setVisible(canSplit);
    if (this.splitButtonText) {
      this.splitButtonText.setVisible(canSplit);
    }
  }

  handleRoundEnd(data) {
    this.playerTurnActive = false;
    this.isPlaying = false;
    
    // Hide action buttons and their text labels
    this.hitButton.setVisible(false);
    if (this.hitButtonText) this.hitButtonText.setVisible(false);
    
    this.standButton.setVisible(false);
    if (this.standButtonText) this.standButtonText.setVisible(false);
    
    this.doubleButton.setVisible(false);
    if (this.doubleButtonText) this.doubleButtonText.setVisible(false);
    
    this.splitButton.setVisible(false);
    if (this.splitButtonText) this.splitButtonText.setVisible(false);
    
    // Show deal button and chip buttons
    this.dealButton.setVisible(true);
    this.dealButton.setAlpha(1.0);
    this.chipButtons.forEach(chip => chip.setVisible(true).setAlpha(1.0));
    
    // Enable bet adjustment
    this.updateBetButtonStates();
    
    // Display result message
    let resultMessage = '';
    switch (data.result) {
      case 'blackjack':
        resultMessage = 'BLACKJACK!';
        break;
      case 'win':
        resultMessage = 'YOU WIN!';
        break;
      case 'lose':
        resultMessage = 'DEALER WINS';
        break;
      case 'push':
        resultMessage = 'PUSH';
        break;
    }
    
    // Keep the dealer and player total texts visible
    if (this.playerTotalText) {
      this.playerTotalText.setVisible(true);
    }
    
    // Show the result message
    this.messageText.setText(resultMessage);
    this.messageText.setVisible(true);
    
    // Display win amount if any
    if (data.winAmount > 0) {
      this.winText.setText(formatSatsToBtc(data.winAmount, true));
      this.winBackground.setVisible(true);
      this.winLabel.setVisible(true);
      this.winText.setVisible(true);
      
      // Animate win text
      // this.tweens.add({
      //   targets: this.winText,
      //   scale: { from: 1, to: 1.2 },
      //   duration: 300,
      //   yoyo: true,
      //   repeat: 3,
      //   ease: 'Sine.easeInOut'
      // });
      
      // Add a glow effect
      //this.winText.setShadow(0, 0, '#ffff00', 8, true, true);
      
      // Reset shadow after animation
      this.time.delayedCall(2000, () => {
        this.winText.setShadow(2, 2, '#000000', 5, false, true);
      });
    } else {
      this.winBackground.setVisible(false);
      this.winLabel.setVisible(false);
      this.winText.setVisible(false);
    }
  }

  handleInsufficientBalance(isInsufficient) {
    // Disable deal button if balance is too low for the current bet
    if (this.dealButton) {
      const canDeal = !isInsufficient && !this.isPlaying;
      
      // Just update the visual appearance
      this.dealButton.setAlpha(canDeal ? 1.0 : 0.5);
    }
  }

  // --- Actions ---

  adjustBet(direction) { // direction is +1 or -1
    if (this.isPlaying) return; // Can't adjust bet during play
    
    this.playSound('button-click');
    const newIndex = this.currentBetIndex + direction;

    if (newIndex >= 0 && newIndex < this.betOptions.length) {
      this.currentBetIndex = newIndex;
      const newBet = this.betOptions[this.currentBetIndex];
      this.updateBetSize(newBet);
    }
  }

  playSound(key) {
    // Use the GameScene's sound manager to ensure consistency with settings
    const gameScene = this.scene.get('GameScene');
    gameScene?.playSound(key); // Delegate to GameScene's playSound method
  }
}