import Phaser from 'phaser';
import EventBus from '@/event-bus';
import { formatSatsToBtc } from '@utils/currencyFormatter'; // Import formatter

export default class UIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'UIScene' });

    // UI elements
    this.balanceText = null;
    this.winText = null;
    this.betSizeText = null;
    this.spinButton = null;
    this.turboButton = null;
    // this.autoSpinButton = null; // If implementing auto-spin
    this.settingsButton = null;
    this.betPlusButton = null;
    this.betMinusButton = null;

    // State
    this.currentBetIndex = 0;
    this.betOptions = [1000000, 2000000, 5000000, 10000000]; // Default Satoshis, loaded from config
    this.currentBetSats = 1000000; // Default Satoshis
    this.isSpinning = false;
    this.soundEnabled = true; // Will be updated from registry
    this.turboEnabled = false; // Will be updated from registry
    this.eventBus = null;
  }

  // No preload needed here, assets are loaded in PreloadScene

  create() {
    console.log('UIScene: Create');
    this.gameConfig = this.registry.get('gameConfig');
    this.eventBus = this.registry.get('eventBus'); // Get EventBus from registry

    if (!this.gameConfig || !this.eventBus) {
        console.error("UIScene: Missing game configuration or EventBus from registry!");
        // Fallback or stop scene
        if (!this.eventBus) this.eventBus = EventBus; // Fallback to global import if not in registry
        if (!this.gameConfig) return;
    }

    this.soundEnabled = this.registry.get('soundEnabled') ?? true;
    this.turboEnabled = this.registry.get('turboEnabled') ?? false;

    this.betOptions = this.gameConfig.settings?.betOptions || this.betOptions;
    // Initial bet can be passed from Vue or use first option
    const initialBetFromRegistry = this.registry.get('initialBet');
    this.currentBetSats = initialBetFromRegistry !== undefined ? initialBetFromRegistry : (this.betOptions[0] || 1000000);

    this.currentBetIndex = this.betOptions.indexOf(this.currentBetSats);
    if (this.currentBetIndex === -1) {
        this.currentBetIndex = 0;
        this.currentBetSats = this.betOptions[0];
        console.warn(`Initial bet ${initialBetFromRegistry} not in options, defaulting to ${this.currentBetSats}`);
    }
    // Emit initial bet to Vue, so Vue is aware of default/initial Phaser bet
    this.eventBus.emit('uiBetChanged', { newBetAmountSats: this.currentBetSats });


    const initialBalance = this.registry.get('userBalance') ?? 0;

    this.createBalanceDisplay(initialBalance, this.gameConfig.ui?.balance);
    this.createWinDisplay(0, this.gameConfig.ui?.win);
    this.createBetDisplay(this.currentBetSats, this.gameConfig.ui?.betSize, this.gameConfig.ui?.betAdjust);
    this.createActionButtons(this.gameConfig.ui?.buttons);

    // --- Event Listeners from Vue or GameScene ---
    this.eventBus.on('vueBalanceUpdated', (data) => {
        if (data.balance !== undefined) this.updateBalance(data.balance);
    });
    // GameScene's displayWinningLines will emit 'lineWinUpdate' to update this.winText
    this.eventBus.on('lineWinUpdate', (data) => {
        if (data.winAmount !== undefined) this.updateWin(data.winAmount, data.isScatter);
    });
    this.eventBus.on('phaserBalanceInsufficient', () => {
        this.handleInsufficientBalance(true);
    });
    this.eventBus.on('vueSpinInitiated', () => {
        this.isSpinning = true;
        this.spinButton?.setAlpha(0.5).disableInteractive();
        this.betPlusButton?.disableInteractive().setAlpha(0.5);
        this.betMinusButton?.disableInteractive().setAlpha(0.5);
    });
    this.eventBus.on('vueSpinConcluded', () => { // Or listen to 'visualSpinComplete' from GameScene
        this.isSpinning = false;
        this.spinButton?.setAlpha(1.0).setInteractive();
        this.updateBetButtonStates(); // Re-enable bet buttons based on currentBetIndex
        // Balance check will re-enable/disable spin if needed via vueBalanceUpdated
    });
    this.eventBus.on('updateSettingsInPhaser', (settings) => {
        if (settings.soundEnabled !== undefined) {
            this.soundEnabled = settings.soundEnabled;
        }
        if (settings.turboEnabled !== undefined) {
            this.turboEnabled = settings.turboEnabled;
            this.updateTurboButtonVisuals();
        }
    });

    // Initial UI setup based on state
    this.updateTurboButtonVisuals();
    this.handleInsufficientBalance(initialBalance < this.currentBetSats);


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

  createWinDisplay(initialWin, config) {
     const pos = config?.position || { x: 400, y: 550 };
     const style = config?.style || { font: 'bold 24px Arial', color: '#FFD700', align: 'center' }; // Gold color for win
     const labelStyle = { font: '16px Arial', color: '#cccccc', align: 'center' };

     this.add.text(pos.x, pos.y - 20, 'Win', labelStyle).setOrigin(0.5);
     this.winText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialWin, true), style).setOrigin(0.5);
     this.winText.setVisible(false); // Initially hidden, only show when there's a win
  }

   createBetDisplay(initialBet, sizeConfig, adjustConfig) {
        const pos = sizeConfig?.position || { x: 650, y: 550 };
        const style = sizeConfig?.style || { font: 'bold 24px Arial', color: '#ffffff', align: 'center' };
        const labelStyle = { font: '16px Arial', color: '#cccccc', align: 'center' };
        const adjustStyle = adjustConfig?.minus?.style || { font: 'bold 32px Arial', color: '#ffffff' };
        const minusPos = adjustConfig?.minus?.position || { x: pos.x - 60, y: pos.y + 5};
        const plusPos = adjustConfig?.plus?.position || { x: pos.x + 60, y: pos.y + 5 };

        this.add.text(pos.x, pos.y - 20, 'Bet', labelStyle).setOrigin(0.5);
        this.betSizeText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialBet), style).setOrigin(0.5);

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

    createActionButtons(config) {
        // --- Spin Button ---
        const spinConfig = config?.spin;
        const spinPos = spinConfig?.position || { x: 400, y: 475 };
        const spinSize = spinConfig?.size || { width: 120, height: 60 };
        this.spinButton = this.add.image(spinPos.x, spinPos.y, spinConfig?.name || 'spin-button')
            .setDisplaySize(spinSize.width, spinSize.height)
            .setOrigin(0.5)
            .setInteractive({ useHandCursor: true });

        // Add text overlay on spin button if needed
        this.add.text(spinPos.x, spinPos.y, 'SPIN', {
             font: 'bold 20px Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 3
        }).setOrigin(0.5);

        this.spinButton.on('pointerdown', () => {
            const gameScene = this.scene.get('GameScene');
            // Check both GameScene's state and local UI state
            if (!gameScene || gameScene.isSpinning || this.isSpinning) return;

            this.playSound('buttonClick');
            this.isSpinning = true; // Set local UI lock
            
            // Spin button should not directly deduct balance or call API.
            // It emits an event to Slot.vue, which then calls the Vuex action.
            this.playSound('buttonClick');
            this.eventBus.emit('uiSpinButtonClicked', { betAmount: this.currentBetSats });
        });

        // --- Turbo Button ---
        const turboConfig = config?.turbo; // Expects { name: "turboButtonTextureKey", position, size }
        if (turboConfig?.name) { // Check if name (texture key) is provided
            const turboPos = turboConfig.position || { x: 520, y: 475 }; // Example default
            const turboSize = turboConfig.size || { width: 80, height: 40 };
            this.turboButton = this.add.image(turboPos.x, turboPos.y, turboConfig.name)
                .setDisplaySize(turboSize.width, turboSize.height)
                .setOrigin(0.5)
                .setInteractive({ useHandCursor: true });

            // Optional: Add text over turbo button if not part of the image
             this.add.text(turboPos.x, turboPos.y, 'TURBO', { font: 'bold 14px Arial', color: '#FFFFFF' }).setOrigin(0.5);


            this.turboButton.on('pointerdown', () => {
                this.playSound('buttonClick');
                const newTurboState = !this.turboEnabled;
                // this.turboEnabled = newTurboState; // Local state updated by event listener
                // this.updateTurboButtonVisuals();
                this.eventBus.emit('uiTurboSettingChanged', { turboEnabled: newTurboState });
            });
            this.updateTurboButtonVisuals();
        } else {
            console.warn("UIScene: Turbo button configuration or texture key missing in gameConfig.ui.buttons.turbo");
        }

        // --- Settings Button ---
        const settingsConfig = config?.settingsButton; // Expects { name: "settingsButtonTextureKey", position, size }
         if (settingsConfig?.name) {
            const settingsPos = settingsConfig.position || { x: 750, y: 50 }; // Example default
            const settingsSize = settingsConfig.size || { width: 40, height: 40 };
            this.settingsButton = this.add.image(settingsPos.x, settingsPos.y, settingsConfig.name)
                .setDisplaySize(settingsSize.width, settingsSize.height)
                .setOrigin(0.5)
                .setInteractive({ useHandCursor: true });

            this.settingsButton.on('pointerdown', () => {
                this.playSound('buttonClick');
                this.eventBus.emit('uiSettingsButtonClicked'); // Inform Vue
                this.scene.pause('GameScene');
                this.scene.pause('UIScene');
                this.scene.launch('SettingsModalScene', {
                    // Pass current states, which are kept in sync by updateSettingsInPhaser listener
                    soundEnabled: this.soundEnabled,
                    turboEnabled: this.turboEnabled
                });
            });
         } else {
            console.warn("UIScene: Settings button configuration or texture key missing in gameConfig.ui.buttons.settingsButton");
         }
    }

  // --- UI Update Methods ---

  updateBalance(newBalanceSats) {
    try {
      if (this.balanceText && this.balanceText.active && this.scene.isActive()) {
        // Make sure the text object exists, is active, and the scene is active
        const formattedBalance = formatSatsToBtc(newBalanceSats, true); // Add 'BTC' suffix
        this.balanceText.setText(formattedBalance);
        
        // Only check for insufficient balance if we have a valid bet amount
        if (typeof this.currentBetSats === 'number') {
          this.handleInsufficientBalance(newBalanceSats < this.currentBetSats);
        }
      }
    } catch (error) {
      console.error('Error updating balance text:', error);
      // Don't throw the error, just log it to prevent game crashes
    }
  }

  updateWin(winAmountSats, isScatter = false) {
     try {
       if (this.winText && this.winText.active && this.scene.isActive()) {
          const formattedWin = formatSatsToBtc(winAmountSats, true);
          
          // Add prefix for scatter wins if needed
          const winPrefix = isScatter ? 'SCATTER: ' : '';
          this.winText.setText(`${winPrefix}${formattedWin}`);
          
          // Only show win text if there's an actual win
          if (winAmountSats > 0) {
              this.winText.setVisible(true);
              
              // Reset any existing tweens
              if (this.tweens) {
                  this.tweens.killTweensOf(this.winText);
              }
              
              // Simple scale animation on win text
              if (this.tweens && typeof this.tweens.add === 'function') {
                  this.tweens.add({
                      targets: this.winText,
                      scale: { from: 1.2, to: 1 },
                      duration: 300,
                      ease: 'Back.easeOut'
                  });
              }
          } else {
              // Hide win text when there's no win
              this.winText.setVisible(false);
          }
       }
     } catch (error) {
       console.error('Error updating win text:', error);
       // Don't throw the error, just log it to prevent game crashes
     }
  }

  updateBetSize(newBetSats) {
     if (this.betSizeText) {
        this.betSizeText.setText(formatSatsToBtc(newBetSats));
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
            const canDecrease = this.currentBetIndex > 0;
            // Update visual appearance only
            this.betMinusButton.setAlpha(canDecrease ? 1 : 0.5);
        }

        if (this.betPlusButton) {
            const canIncrease = this.currentBetIndex < this.betOptions.length - 1;
            // Update visual appearance only
            this.betPlusButton.setAlpha(canIncrease ? 1 : 0.5);
        }
    }

    updateTurboButtonVisuals() {
        if (this.turboButton) {
            // Example: change tint or alpha based on state
            this.turboButton.setTint(this.turboEnabled ? 0xaaaaff : 0xffffff); // Blueish tint when ON
            this.turboButton.setAlpha(this.turboEnabled ? 1.0 : 0.8);
        }
    }

    handleInsufficientBalance(isInsufficient) {
        try {
            // Disable spin button if balance is too low for the current bet
            if (this.spinButton && this.spinButton.active && this.scene.isActive()) {
                const canSpin = !isInsufficient && !this.isSpinning;
                
                // Just update the visual appearance
                this.spinButton.setAlpha(canSpin ? 1.0 : 0.5);
                
                // Optionally show a message or change button appearance further
                if (!canSpin) {
                    console.log('Spin button disabled: ' + (isInsufficient ? 'Insufficient balance' : 'Already spinning'));
                }
            }
        } catch (error) {
            console.error('Error handling insufficient balance:', error);
            // Don't throw the error, just log it to prevent game crashes
        }
    }


  // --- Actions ---

  adjustBet(direction) { // direction is +1 or -1
    this.playSound('buttonClick');
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

