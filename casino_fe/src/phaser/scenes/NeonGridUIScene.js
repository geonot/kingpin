import Phaser from 'phaser';
import EventBus from '@/event-bus';
import { formatSatsToBtc } from '@utils/currencyFormatter'; // Import formatter

export default class NeonGridUIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'NeonGridUIScene' });

    // UI elements
    this.balanceText = null;
    this.winText = null;
    this.betSizeText = null;
    this.spinButton = null;
    this.turboButton = null;
    this.autoSpinButton = null; // If implementing auto-spin
    this.settingsButton = null;
    this.betPlusButton = null;
    this.betMinusButton = null;

    // State
    this.currentBetIndex = 0;
    this.betOptions = [10, 20, 50, 100, 200, 500]; // Default, loaded from config
    this.currentBetSats = 10;
    this.isSpinning = false; // Local state to disable buttons during spin
    this.soundEnabled = true;
    this.turboEnabled = false;
  }

  preload() {
    // Preload common UI assets if not done in PreloadScene
    // this.load.image('spin-button', '/assets/ui/spin_button.png'); // Example
    // this.load.image('settings-button', '/assets/ui/settings.png');
    // Assets specific to the slot theme (like button icons) should be loaded in PreloadScene
  }

  create() {
    console.log('NeonGridUIScene: Create');
    const gameConfig = this.registry.get('gameConfig');
    if (!gameConfig) {
        console.error("NeonGridUIScene: Game config not found!");
        return;
    }
     // Initialize state from registry
    this.soundEnabled = this.registry.get('soundEnabled') ?? true;
    this.turboEnabled = this.registry.get('turboEnabled') ?? false;


    // Get bet options from config or use default
    this.betOptions = gameConfig.settings?.betOptions || this.betOptions;
    this.currentBetSats = this.registry.get('initialBet') || this.betOptions[0] || 10;
    this.currentBetIndex = this.betOptions.indexOf(this.currentBetSats);
    if (this.currentBetIndex === -1) { // If initialBet not in options, default to first
        this.currentBetIndex = 0;
        this.currentBetSats = this.betOptions[0];
    }

    const initialBalance = this.registry.get('userBalance') ?? 0;

    // Create UI elements using config positions/styles if available
    this.createBalanceDisplay(initialBalance, gameConfig.ui?.balance);
    this.createWinDisplay(0, gameConfig.ui?.win);
    this.createBetDisplay(this.currentBetSats, gameConfig.ui?.betSize, gameConfig.ui?.betAdjust);
    this.createActionButtons(gameConfig.ui?.buttons);

    // --- Event Listeners ---
    // Listen for updates from GameScene or Vue app
    EventBus.$on('uiUpdate', (data) => {
        if (data.balance !== undefined) {
            this.updateBalance(data.balance);
        }
        if (data.winAmount !== undefined) {
            // Pass isBonusWin or isTotalWin if present in data
            const isTotalOrBonus = data.isBonusWin || data.isTotalWin || false;
            this.updateWin(data.winAmount, data.isScatter, data.ways, isTotalOrBonus);
        }
        if (data.balanceInsufficient !== undefined) {
            this.handleInsufficientBalance(data.balanceInsufficient);
        }
    });

    // Listen for line win updates from GameScene
    EventBus.$on('lineWinUpdate', (data) => {
        if (data.winAmount !== undefined) {
            // Updated to pass data.ways
            this.updateWin(data.winAmount, data.isScatter, data.ways);
        }
    });

    // Listen for UI idle state to re-enable spin button
    EventBus.$on('uiSetIdle', () => {
        if (this.isSpinning) {
            this.isSpinning = false;
            if (this.spinButton) {
                this.spinButton.setAlpha(1.0);
            }
        }
    });

     // Listen for spin start/end from GameScene to disable/enable buttons
     // This might be redundant if GameScene directly checks its own isSpinning state
     // EventBus.$on('spinStateChanged', (data) => {
     //   this.isSpinning = data.spinning;
     //   this.spinButton?.setInteractive(!this.isSpinning);
     //   // Disable other buttons during spin?
     // });

     // Listen for settings changes to update button states if needed (e.g., Turbo)
      EventBus.$on('turboSettingChanged', (isEnabled) => {
          this.turboEnabled = isEnabled;
          this.updateTurboButtonVisuals(); // Update visual state
      });
       EventBus.$on('soundSettingChanged', (isEnabled) => {
          this.soundEnabled = isEnabled;
          // Update sound button visuals if any in this scene
      });

      console.log('NeonGridUIScene: Ready.');
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
        this.spinButton = this.add.image(spinPos.x, spinPos.y, spinConfig.asset)
            .setDisplaySize(spinSize.width, spinSize.height)
            .setOrigin(0.5)
            .setInteractive({ useHandCursor: true });

        // Add text overlay on spin button if needed
        this.add.text(spinPos.x, spinPos.y, 'SPIN', {
             font: 'bold 20px Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 3
        }).setOrigin(0.5);

        this.spinButton.on('pointerdown', () => {
            const gameScene = this.scene.get('NeonGridGameScene');
            // Check both GameScene's state and local UI state
            if (!gameScene || gameScene.isSpinning || this.isSpinning) return;

            this.playSound('buttonClick');
            this.isSpinning = true; // Set local UI lock

            // Update visual appearance only
            this.spinButton?.setAlpha(0.6);

            // Get current balance from store via event bus
            EventBus.$emit('getBalanceForDeduction', this.currentBetSats);

            // Emit spin request with bet amount
            EventBus.$emit('spinRequest', { betAmount: this.currentBetSats }); // Changed from 'bet' to 'betAmount'
        });
         // Re-enable spin button when spin completes (via GameScene event or specific callback)
        // We'll use the 'uiUpdate' event for simplicity, assuming it implies spin end if win occurs/balance updates
         EventBus.$on('uiUpdate', () => {
             if (this.isSpinning) { // Only re-enable if it was spinning
                this.isSpinning = false;
                if (this.spinButton) {
                    // Update visual appearance only
                    this.spinButton.setAlpha(1.0);
                }
             }
         });
         // Also re-enable on spin error
         EventBus.$on('spinError', () => {
              if (this.isSpinning) {
                  this.isSpinning = false;
                  if (this.spinButton) {
                      // Update visual appearance only
                      this.spinButton.setAlpha(1.0);
                  }
              }
         });


        // --- Turbo Button ---
        const turboConfig = config?.turbo;
        if (turboConfig) {
            const turboPos = turboConfig.position || { x: 520, y: 475 };
            const turboSize = turboConfig.size || { width: 80, height: 40 };
            this.turboButton = this.add.image(turboPos.x, turboPos.y, turboConfig.asset)
                .setDisplaySize(turboSize.width, turboSize.height)
                .setOrigin(0.5)
                .setInteractive({ useHandCursor: true });

             this.add.text(turboPos.x, turboPos.y, 'TURBO', {
                 font: 'bold 14px Arial', color: '#FFFFFF'
             }).setOrigin(0.5);

            this.turboButton.on('pointerdown', () => {
                 this.playSound('buttonClick');
                const newState = !this.turboEnabled;
                EventBus.$emit('turboSettingChanged', newState); // Emit event for GameScene & Settings
            });
            this.updateTurboButtonVisuals(); // Set initial visual state
        }

        // --- Settings Button ---
        const settingsConfig = config?.settings;
         if (settingsConfig) {
            const settingsPos = settingsConfig.position || { x: 750, y: 50 };
            const settingsSize = settingsConfig.size || { width: 40, height: 40 };
            this.settingsButton = this.add.image(settingsPos.x, settingsPos.y, settingsConfig.asset)
                .setDisplaySize(settingsSize.width, settingsSize.height)
                .setOrigin(0.5)
                .setInteractive({ useHandCursor: true });

            this.settingsButton.on('pointerdown', () => {
                 this.playSound('buttonClick');
                 // Pause current scenes and launch settings modal
                 this.scene.pause('NeonGridGameScene');
                 this.scene.pause('UIScene'); // Pause this scene as well
                 this.scene.launch('SettingsModalScene', {
                    gameSceneKey: 'NeonGridGameScene',
                    uiSceneKey: 'NeonGridUIScene',
                     soundEnabled: this.soundEnabled,
                     turboEnabled: this.turboEnabled
                 });
            });
         }


        // --- Auto Spin Button (Placeholder) ---
        const autoSpinConfig = config?.autoSpin;
        if (autoSpinConfig) {
             const autoPos = autoSpinConfig.position || { x: 280, y: 475 };
             const autoSize = autoSpinConfig.size || { width: 80, height: 40 };
             this.autoSpinButton = this.add.image(autoPos.x, autoPos.y, autoSpinConfig.asset)
                 .setDisplaySize(autoSize.width, autoSize.height)
                 .setOrigin(0.5)
                 .setInteractive({ useHandCursor: true });

             this.add.text(autoPos.x, autoPos.y, 'AUTO', {
                 font: 'bold 14px Arial', color: '#FFFFFF'
             }).setOrigin(0.5);

             this.autoSpinButton.on('pointerdown', () => {
                  this.playSound('buttonClick');
                 console.log('Auto-spin clicked (Not Implemented)');
                 // TODO: Implement auto-spin logic
             });
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

  updateWin(winAmountSats, isScatter = false, ways = undefined, isTotalOrBonusWin = false) {
     try {
       if (this.winText && this.winText.active && this.scene.isActive()) {
          const formattedWin = formatSatsToBtc(winAmountSats, true); // Assuming true adds BTC suffix
          let displayText = '';

          if (winAmountSats > 0) {
              if (isTotalOrBonusWin) {
                  // GameScene might send isBonusWin specifically, or just a total that implies it.
                  // For now, a generic "Total Win" or "Bonus Win" if we refine data from GameScene.
                  // If data specifically says data.isBonusWin, we can use "Bonus Win: "
                  // Otherwise, for a general total win (which could be from bonus), "Total Win: " is safe.
                  displayText = `Total Win: ${formattedWin}`;
                  // If GameScene sends `isBonusWin: true` specifically for the final bonus payout,
                  // we could have: displayText = data.isBonusWin ? `Bonus Win: ${formattedWin}` : `Total Win: ${formattedWin}`;
              } else if (isScatter) {
                  displayText = `SCATTER: ${formattedWin}`;
              } else if (ways !== undefined && ways > 0) {
                  displayText = `${formattedWin} (${ways} WAYS)`;
              } else { // Standard payline win
                  displayText = formattedWin; // Individual line wins might not need "Line Win:" prefix here if GameScene manages that cycle
              }
              this.winText.setText(displayText);
              this.winText.setVisible(true);

              if (this.tweens && typeof this.tweens.add === 'function') {
                  this.tweens.killTweensOf(this.winText);
                  this.tweens.add({
                      targets: this.winText,
                      scale: { from: 1.2, to: 1 },
                      duration: 300,
                      ease: 'Back.easeOut'
                  });
              }
          } else {
              this.winText.setVisible(false);
              this.winText.setText('');
          }
       }
     } catch (error) {
       console.error('Error updating win text:', error);
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
        const gameScene = this.scene.get('NeonGridGameScene');
        gameScene?.playSound(key); // Delegate to GameScene's playSound method
    }

}
