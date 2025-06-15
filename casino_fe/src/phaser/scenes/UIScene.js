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
    this.autoSpinButton = null; // If implementing auto-spin
    this.settingsButton = null;
    this.betPlusButton = null;
    this.betMinusButton = null;

    // State
    this.currentBetIndex = 0;
    this.betOptions = [10, 20, 50, 100, 200, 500]; // Default, loaded from config
    this.defaultButtonStates = {
        hover: { alpha: 0.8, tint: 0xf0f0f0, scale: 1.05 },
        pressed: { alpha: 0.6, tint: 0xd0d0d0, scale: 0.95 },
        disabled: { alpha: 0.5, tint: 0xaaaaaa, scale: 1.0 },
        active: { alpha: 1.0, tint: 0xaaaaff, scale: 1.0 } // For toggle buttons like Turbo
    };
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
    console.log('UIScene: Create');
    const gameConfig = this.registry.get('gameConfig');
    if (!gameConfig) {
        console.error("UIScene: Game config not found!");
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
            this.updateBalance(data.balance); // updateBalance will call updateSpinButtonVisuals
        }
        if (data.winAmount !== undefined) {
            const isTotalOrBonus = data.isBonusWin || data.isTotalWin || false;
            this.updateWin(data.winAmount, data.isScatter, data.ways, isTotalOrBonus);
        }
        // If a spin cycle completes, GameScene might emit uiUpdate with spinComplete:true
        // This ensures isSpinning is reset and visuals updated even if balance/win didn't change but spin ended.
        if (this.isSpinning && data.spinComplete === true) {
            this.isSpinning = false;
            this.updateSpinButtonVisuals();
        }
        // data.balanceInsufficient is handled by updateSpinButtonVisuals called via updateBalance
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
        this.isSpinning = false;
        this.updateSpinButtonVisuals();
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
          this.turboEnabled = isEnabled; // Keep local state in sync
          // this.registry.set('turboEnabled', isEnabled); // Ensure registry is also up to date - already done by createConfigurableButton's action for turbo
          this.updateTurboButtonVisuals();
      });
       EventBus.$on('soundSettingChanged', (isEnabled) => {
          this.soundEnabled = isEnabled;
          // Update sound button visuals if any in this scene
      });

      console.log('UIScene: Ready.');
  }

  // --- UI Element Creation ---

  createBalanceDisplay(initialBalance, config) {
    const pos = config?.position || { x: 150, y: 550 };
    // Default style with Phaser 3 text properties
    const defaultStyle = { fontStyle: 'bold', fontSize: '24px', fontFamily: 'Arial', color: '#ffffff', align: 'center', stroke: '#000000', strokeThickness: 0 };
    const defaultLabelStyle = { fontSize: '16px', fontFamily: 'Arial', color: '#cccccc', align: 'center', stroke: '#000000', strokeThickness: 0 };

    const style = { ...defaultStyle, ...(config?.style || {}) };
    const labelStyle = { ...defaultLabelStyle, ...(config?.labelStyle || {}) };
    const labelText = config?.labelText || 'Balance';

    this.add.text(pos.x, pos.y - 20, labelText, labelStyle).setOrigin(0.5);
    this.balanceText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialBalance, true), style).setOrigin(0.5);
  }

  createWinDisplay(initialWin, config) {
     const pos = config?.position || { x: 400, y: 550 };
     const defaultStyle = { fontStyle: 'bold', fontSize: '24px', fontFamily: 'Arial', color: '#FFD700', align: 'center', stroke: '#000000', strokeThickness: 0 };
     const defaultLabelStyle = { fontSize: '16px', fontFamily: 'Arial', color: '#cccccc', align: 'center', stroke: '#000000', strokeThickness: 0 };

     const style = { ...defaultStyle, ...(config?.style || {}) };
     const labelStyle = { ...defaultLabelStyle, ...(config?.labelStyle || {}) };
     const labelText = config?.labelText || 'Win';

     this.add.text(pos.x, pos.y - 20, labelText, labelStyle).setOrigin(0.5);
     this.winText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialWin, true), style).setOrigin(0.5);
     this.winText.setVisible(false); // Initially hidden, only show when there's a win
  }

   createBetDisplay(initialBet, sizeConfig, adjustConfig) {
        const pos = sizeConfig?.position || { x: 650, y: 550 };
        const defaultStyle = { fontStyle: 'bold', fontSize: '24px', fontFamily: 'Arial', color: '#ffffff', align: 'center', stroke: '#000000', strokeThickness: 0 };
        const defaultLabelStyle = { fontSize: '16px', fontFamily: 'Arial', color: '#cccccc', align: 'center', stroke: '#000000', strokeThickness: 0 };

        const style = { ...defaultStyle, ...(sizeConfig?.style || {}) };
        const labelStyle = { ...defaultLabelStyle, ...(sizeConfig?.labelStyle || {}) };
        const labelText = sizeConfig?.labelText || 'Bet';

        const defaultAdjustStyle = { fontStyle: 'bold', fontSize: '32px', fontFamily: 'Arial', color: '#ffffff', stroke: '#000000', strokeThickness: 0 };
        // Overall style for adjust buttons, can be overridden by specific minus/plus styles
        const baseAdjustStyle = { ...defaultAdjustStyle, ...(adjustConfig?.style || {}) };
        const minusStyle = { ...baseAdjustStyle, ...(adjustConfig?.minus?.style || {}) };
        const plusStyle = { ...baseAdjustStyle, ...(adjustConfig?.plus?.style || {}) };

        const minusPos = adjustConfig?.minus?.position || { x: pos.x - 60, y: pos.y + 5};
        const plusPos = adjustConfig?.plus?.position || { x: pos.x + 60, y: pos.y + 5 };
        const minusText = adjustConfig?.minus?.labelText || '-';
        const plusText = adjustConfig?.plus?.labelText || '+';

        this.add.text(pos.x, pos.y - 20, labelText, labelStyle).setOrigin(0.5);
        this.betSizeText = this.add.text(pos.x, pos.y + 5, formatSatsToBtc(initialBet), style).setOrigin(0.5);

        this.betMinusButton = this.add.text(minusPos.x, minusPos.y, minusText, minusStyle)
            .setOrigin(0.5)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.adjustBet(-1));

        this.betPlusButton = this.add.text(plusPos.x, plusPos.y, plusText, plusStyle)
            .setOrigin(0.5)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.adjustBet(1));

        this.updateBetButtonStates();
    }

    // Generic function to create a button with states and text
    createConfigurableButton(scene, config, buttonNameKey, defaultIconKey, onClickAction) {
        const buttonConfig = config?.[buttonNameKey] || {}; // e.g., config.spin or config.turbo
        const pos = buttonConfig.position || { x: scene.cameras.main.width / 2, y: scene.cameras.main.height / 2 }; // Default position if not specified
        const size = buttonConfig.size || { width: 100, height: 50 }; // Default size

        const iconNormal = buttonConfig.icon_normal || defaultIconKey;
        const iconHover = buttonConfig.icon_hover;
        const iconPressed = buttonConfig.icon_pressed;
        const iconDisabled = buttonConfig.icon_disabled;
        const iconActive = buttonConfig.icon_active; // For toggle buttons like Turbo

        // Merge default states with specific button states from config
        const stateStyles = {
            hover: { ...this.defaultButtonStates.hover, ...(buttonConfig.states?.hover || {}) },
            pressed: { ...this.defaultButtonStates.pressed, ...(buttonConfig.states?.pressed || {}) },
            disabled: { ...this.defaultButtonStates.disabled, ...(buttonConfig.states?.disabled || {}) },
            active: { ...this.defaultButtonStates.active, ...(buttonConfig.states?.active || {}) },
        };

        const button = scene.add.image(pos.x, pos.y, iconNormal)
            .setDisplaySize(size.width, size.height)
            .setOrigin(0.5)
            .setInteractive({ useHandCursor: true });

        // Store all relevant data on the button itself for easy access in event handlers and update methods
        button.setData('config', buttonConfig); // Full config for this button
        button.setData('stateStyles', stateStyles);
        button.setData('icons', { normal: iconNormal, hover: iconHover, pressed: iconPressed, disabled: iconDisabled, active: iconActive });
        button.setData('isPressed', false); // Track if pointer is currently down on this button
        button.setData('isDisabled', false); // Track disabled state
        button.setData('isActive', false); // Track active state for toggle buttons

        // Text Overlay
        const labelText = buttonConfig.labelText || ''; // Get text from config, or default to empty
        if (labelText) {
            const defaultLabelStyle = { fontSize: '16px', fontFamily: 'Arial', color: '#FFFFFF', stroke: '#000000', strokeThickness: 2, align: 'center' };
            const labelStyle = { ...defaultLabelStyle, ...(buttonConfig.labelStyle || {}) };
            const textGameObject = scene.add.text(pos.x, pos.y, labelText, labelStyle).setOrigin(0.5);
            button.setData('label', textGameObject); // Store the text object to manage its state (e.g., visibility)
        }

        button.on('pointerover', () => {
            if (button.getData('isDisabled') || button.getData('isPressed')) return;
            const icons = button.getData('icons');
            const styles = button.getData('stateStyles');
            if (icons.hover) button.setTexture(icons.hover);
            else { // Fallback to style changes
                if (styles.hover.alpha !== undefined) button.setAlpha(styles.hover.alpha);
                if (styles.hover.tint !== undefined) button.setTint(styles.hover.tint); else button.clearTint();
                if (styles.hover.scale !== undefined) button.setScale(styles.hover.scale); else button.setScale(1.0);
            }
        });

        button.on('pointerout', () => {
            if (button.getData('isDisabled') || button.getData('isPressed')) return;
            const icons = button.getData('icons');
            const styles = button.getData('stateStyles');
            const isActive = button.getData('isActive');
            
            const currentIcon = isActive && icons.active ? icons.active : icons.normal;
            button.setTexture(currentIcon); // Revert to normal or active icon
            
            if (isActive) { // If active (e.g. Turbo ON)
                 button.setAlpha(styles.active.alpha !== undefined ? styles.active.alpha : 1.0);
                 if (styles.active.tint !== undefined) button.setTint(styles.active.tint); else button.clearTint();
                 button.setScale(styles.active.scale !== undefined ? styles.active.scale : 1.0);
            } else { // Normal state after hover
                 button.setAlpha(1.0);
                 button.clearTint();
                 button.setScale(1.0);
            }
        });

        button.on('pointerdown', () => {
            if (button.getData('isDisabled')) return;
            button.setData('isPressed', true);
            const icons = button.getData('icons');
            const styles = button.getData('stateStyles');
            if (icons.pressed) button.setTexture(icons.pressed);
            else {
                if (styles.pressed.alpha !== undefined) button.setAlpha(styles.pressed.alpha);
                if (styles.pressed.tint !== undefined) button.setTint(styles.pressed.tint); else button.clearTint();
                if (styles.pressed.scale !== undefined) button.setScale(styles.pressed.scale); else button.setScale(1.0);
            }
            scene.playSound('buttonClick'); // Play sound consistently
            if (onClickAction) onClickAction(button); // Pass button to action if needed
        });

        button.on('pointerup', () => {
            const wasPressed = button.getData('isPressed');
            button.setData('isPressed', false);

            if (!wasPressed) return; // Only proceed if it was actually pressed

            // If button is now disabled (e.g. spin button after click)
            // This state will be visually updated by a dedicated updateVisuals function (e.g., updateSpinButtonVisuals)
            // So, here we just ensure it doesn't revert to hover if it became disabled.
            if (button.getData('isDisabled')) {
                 // Visual update for disabled state is handled by updateXButtonVisuals methods
                return;
            }

            // If pointer is still over the button, revert to hover state
            if (button.input.hitArea.contains(scene.input.activePointer.x, scene.input.activePointer.y)) {
                button.emit('pointerover');
            } else { // Pointer moved out while pressed, revert to normal/active base state
                const icons = button.getData('icons');
                const isActive = button.getData('isActive');
                const styles = button.getData('stateStyles');
                const currentIcon = isActive && icons.active ? icons.active : icons.normal;
                button.setTexture(currentIcon);
                if(isActive) {
                    if (styles.active.alpha !== undefined) button.setAlpha(styles.active.alpha); else button.setAlpha(1.0);
                    if (styles.active.tint !== undefined) button.setTint(styles.active.tint); else button.clearTint();
                    if (styles.active.scale !== undefined) button.setScale(styles.active.scale); else button.setScale(1.0);
                } else {
                     button.setAlpha(1.0); button.clearTint(); button.setScale(1.0);
                }
            }
        });
        return button;
    }

    createActionButtons(config) { // config is gameConfig.ui.buttons from registry
        const buttonsRootConfig = this.registry.get('gameConfig')?.ui?.buttons || {};

        this.spinButton = this.createConfigurableButton(this, buttonsRootConfig, 'spin', 'spin-button-default',
            () => { // onClickAction for Spin
                const gameScene = this.scene.get('GameScene');
                // Check local isSpinning, GameScene state, and button's own disabled data state
                if (!gameScene || gameScene.isSpinning || this.isSpinning || this.spinButton.getData('isDisabled')) {
                    return;
                }
                this.isSpinning = true; // Local UI lock
                // Visuals are updated by pointerdown, then by updateSpinButtonVisuals called by events
                EventBus.$emit('getBalanceForDeduction', this.currentBetSats);
                EventBus.$emit('spinRequest', { betAmount: this.currentBetSats });
            }
        );
        // this.updateSpinButtonVisuals(); // Initial state set after event listeners are established

        if (buttonsRootConfig.turbo) { // Check if turbo button is configured
            this.turboButton = this.createConfigurableButton(this, buttonsRootConfig, 'turbo', 'turbo-button-default',
                (button) => { // onClickAction for Turbo
                    // The actual toggling of this.turboEnabled and calling updateTurboButtonVisuals
                    // is handled by the 'turboSettingChanged' event listener in create()
                    this.registry.set('turboEnabled', !this.registry.get('turboEnabled'));
                }
            );
            // this.updateTurboButtonVisuals(); // Initial state set by turboSettingChanged listener
        }

         if (buttonsRootConfig.settings) { // Check if settings button is configured
            this.settingsButton = this.createConfigurableButton(this, buttonsRootConfig, 'settings', 'settings-button-default',
                () => { // onClickAction for Settings
                     this.scene.pause('GameScene');
                     this.scene.pause('UIScene');
                     this.scene.launch('SettingsModalScene', {
                         soundEnabled: this.registry.get('soundEnabled'), // Get fresh values from registry
                         turboEnabled: this.registry.get('turboEnabled')
                     });
                }
            );
         }

        if (buttonsRootConfig.autoSpin) { // Check if autoSpin button is configured
             this.autoSpinButton = this.createConfigurableButton(this, buttonsRootConfig, 'autoSpin', 'auto-button-default',
                () => { // onClickAction for AutoSpin
                     console.log('Auto-spin clicked (Not Implemented)');
                     // TODO: Implement auto-spin logic and visual states for autoSpinButton
                }
            );
            // this.updateAutoSpinButtonVisuals(); // TODO: if auto-spin has states
        }
        // Ensure initial visual states are set after all buttons are created and event listeners might be set up
        this.updateSpinButtonVisuals();
        if (this.turboButton) this.updateTurboButtonVisuals();
    }

  // --- UI Update Methods ---

  updateBalance(newBalanceSats) {
    try {
      if (this.balanceText && this.balanceText.active && this.scene.isActive()) {
        const formattedBalance = formatSatsToBtc(newBalanceSats, true);
        this.balanceText.setText(formattedBalance);
        // The call to handleInsufficientBalance is removed as this logic
        // is now part of updateSpinButtonVisuals, which is called below.
        if (typeof this.currentBetSats === 'number') {
          this.updateSpinButtonVisuals();
        }
      }
    } catch (error) {
      console.error('Error updating balance text:', error);
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

    // The following methods were added in the previous step and are assumed to be correct.
    // updateBetButtonStates() { ... }
    // updateTurboButtonVisuals() { ... }
    // updateSpinButtonVisuals() { ... }

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

