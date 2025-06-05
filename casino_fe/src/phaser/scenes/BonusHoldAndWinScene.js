import Phaser from 'phaser';
import EventBus from '@/event-bus'; // For communication if needed

export default class BonusHoldAndWinScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BonusHoldAndWinScene' });

    // Game state properties
    this.gridConfig = {
        cols: 5,
        rows: 3,
        startX: 0,
        startY: 0,
        width: 0,
        height: 0,
        symbolSize: { width: 100, height: 100 } // Default, will be from gameConfig
    };
    this.reelContainers = []; // Array of containers for each reel's symbols
    this.symbolMap = {}; // To store active coin symbols: 'col,row' -> coinSprite
    this.heldCoins = {}; // To store data of held coins: 'col,row' -> {value: X, sprite: coinSprite}

    this.respinsRemaining = 0;
    this.initialRespins = 3; // Will be from gameConfig
    this.totalBonusWin = 0;
    this.baseBet = 0; // To calculate actual coin values

    // UI Text elements
    this.respinsText = null;
    this.totalWinText = null;
    this.infoText = null; // For messages like "Good Luck!", "No New Coins!"
    this.spinButton = null;

    this.gameConfig = null; // To store the main game config
    this.bonusConfig = null; // To store the holdAndWinBonus part of the config
    this.slotId = null; // To construct asset keys
    this.initialCoinsData = null; // To store initial coins passed from GameScene
  }

  init(data) {
    console.log('BonusHoldAndWinScene: init()', data);
    this.gameConfig = data.gameConfig;
    this.bonusConfig = this.gameConfig.holdAndWinBonus;
    this.slotId = this.gameConfig.game.short_name; // e.g., "hack" from slot1/gameConfig.json
    this.baseBet = data.currentBet || 1; // Get current bet from GameScene
    if (data.initialCoins) {
      this.initialCoinsData = data.initialCoins;
    }

    if (!this.bonusConfig) {
        console.error("BonusHoldAndWinScene: holdAndWinBonus configuration not found!");
        // Potentially emit an error event or transition back
        this.scene.stop();
        // Optionally, resume the main game scene if it was paused
        // this.scene.resume('GameScene');
        // this.scene.resume('UIScene');
        return;
    }

    this.initialRespins = this.bonusConfig.initialRespins || 3;
    this.gridConfig.rows = this.bonusConfig.bonusReelLayout?.rows || 3;
    this.gridConfig.cols = this.bonusConfig.bonusReelLayout?.columns || 5;
    this.gridConfig.symbolSize = this.gameConfig.reel?.symbolSize || { width: 100, height: 100 };
  }

  preload() {
    console.log('BonusHoldAndWinScene: preload()');
    // Assets like the coin symbol and bonus background should ideally be loaded
    // in PreloadScene.js based on the gameConfig.
    // If there are assets *only* for this bonus scene and not declared in gameConfig,
    // they could be loaded here.

    // Example: Load coin symbol if not already available globally
    // This assumes coinSymbolId refers to an existing symbol definition in gameConfig.symbols
    const coinSymbolDef = this.gameConfig.game.symbols.find(s => s.id === this.bonusConfig.coinSymbolId);
    if (coinSymbolDef && coinSymbolDef.icon) {
        // The key construction needs to match how PreloadScene loads symbols,
        // e.g., `symbol-${coinSymbolDef.id}` or a slot-specific prefix.
        // For slot1 (hack), symbols are like `hack_sprite_0`.
        // If PreloadScene used `symbol-${id}`, then that's fine.
        // Let's assume PreloadScene handles symbol loading.
        // We just need to ensure the coin image is loaded.
        // If PreloadScene uses `slotId_assetName` (e.g. `hack_coin`), then:
        // const coinAssetKey = `${this.slotId}_${coinSymbolDef.icon.split('/').pop().replace(/\..+$/, '')}`;
        // this.load.image(coinAssetKey, `public/slots/${this.slotId}/${coinSymbolDef.icon.split('/').pop()}`);
        // console.log(`Attempting to load coin image with key: ${coinAssetKey}`);
    }

    // Load bonus background if specified and not loaded by PreloadScene
    if (this.bonusConfig.bonusBackgroundAsset) {
        this.load.image('bonus_background_specific', `public/slots/${this.slotId}/${this.bonusConfig.bonusBackgroundAsset.split('/').pop()}`);
    }
  }

  create() {
    console.log('BonusHoldAndWinScene: create()');
    this.respinsRemaining = this.initialRespins;
    this.totalBonusWin = 0;
    this.heldCoins = {};

    this.createBackground();
    this.calculateGridDimensions();
    this.createReelGrid(); // Placeholder for visual grid/slots
    this.createMask();
    this.createUI(); // Respins display, win display, spin button

    if (this.initialCoinsData && this.initialCoinsData.length > 0) {
      this.placeInitialCoins();
    }

    console.log('BonusHoldAndWinScene: Ready.');
    if (this.getEmptySlots().length === 0) {
        this.infoText.setText('Grid Full! Calculating winnings...');
        this.time.delayedCall(1500, this.endBonus, [], this);
    } else if (this.initialCoinsData && this.initialCoinsData.length > 0) {
        this.infoText.setText('Initial coins placed! Spin to win more!');
         // Automatically reset respins if initial coins are placed, as per common H&W logic
        this.respinsRemaining = this.bonusConfig.resetRespinsValue || 3;
        this.updateUIText();
    }
    else {
        this.infoText.setText('Spin to start the bonus!');
    }
  }

  update(time, delta) {
    // console.log('BonusHoldAndWinScene: update()');
    // Game loop logic, if any needed per frame
  }

  calculateGridDimensions() {
    const gameWidth = this.cameras.main.width;
    // const gameHeight = this.cameras.main.height; // Not used directly for grid start

    const { cols, rows, symbolSize } = this.gridConfig;
    const reelSpacing = this.gameConfig.reel?.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel?.symbolSpacing || 0;

    this.gridConfig.width = cols * symbolSize.width + (cols - 1) * reelSpacing;
    this.gridConfig.height = rows * symbolSize.height + (rows - 1) * symbolSpacing;

    // Center the grid, or use position from config if available
    this.gridConfig.startX = (gameWidth - this.gridConfig.width) / 2;
    this.gridConfig.startY = (this.gameConfig.reel?.position?.y || 100) + 50; // A bit lower for bonus
  }

  createBackground() {
    const { width, height } = this.cameras.main;
    let bg;
    if (this.bonusConfig.bonusBackgroundAsset && this.textures.exists('bonus_background_specific')) {
        bg = this.add.image(width / 2, height / 2, 'bonus_background_specific');
    } else if (this.textures.exists('background')) { // Fallback to main game background
        bg = this.add.image(width / 2, height / 2, 'background');
    } else { // Fallback to color
        this.cameras.main.setBackgroundColor('#000033'); // Dark blue
        return;
    }
    const scaleX = width / bg.width;
    const scaleY = height / bg.height;
    bg.setScale(Math.max(scaleX, scaleY)).setScrollFactor(0);
    bg.setDepth(-1);
  }

  createReelGrid() {
    this.reelContainers = [];
    this.symbolMap = {}; // Clear any previous map

    const { cols, rows, startX, startY, symbolSize } = this.gridConfig;
    const reelSpacing = this.gameConfig.reel?.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel?.symbolSpacing || 0;

    for (let c = 0; c < cols; c++) {
      const reelX = startX + c * (symbolSize.width + reelSpacing);
      const reelContainer = this.add.container(reelX, startY);
      this.reelContainers.push(reelContainer);

      for (let r = 0; r < rows; r++) {
        // Add placeholder graphics for empty slots
        const slotY = r * (symbolSize.height + symbolSpacing) + symbolSize.height / 2;
        const placeholder = this.add.graphics()
            .fillStyle(0x000000, 0.3)
            .fillRect(0, slotY - symbolSize.height / 2, symbolSize.width, symbolSize.height)
            .lineStyle(1, 0xffffff, 0.5)
            .strokeRect(0, slotY - symbolSize.height / 2, symbolSize.width, symbolSize.height);
        reelContainer.add(placeholder);
      }
    }
    console.log('Reel grid placeholders created.');
  }

  createMask() {
    const { startX, startY, width, height } = this.gridConfig;
    const maskShape = this.make.graphics();
    maskShape.fillStyle(0xffffff);
    maskShape.fillRect(startX, startY, width, height);
    const mask = maskShape.createGeometryMask();
    mask.invertAlpha = false;
    this.reelContainers.forEach(container => {
      container.setMask(mask);
    });
  }

  createUI() {
    const screenCenterX = this.cameras.main.width / 2;
    const topPanelY = 50;
    const bottomPanelY = this.cameras.main.height - 70;

    // Respins Remaining
    this.respinsText = this.add.text(screenCenterX - 150, topPanelY, `Respins: ${this.respinsRemaining}`, {
      font: 'bold 28px Arial', fill: '#FFD700', stroke: '#000000', strokeThickness: 4
    }).setOrigin(0.5);

    // Total Bonus Win
    this.totalWinText = this.add.text(screenCenterX + 150, topPanelY, `Win: ${this.totalBonusWin}`, {
      font: 'bold 28px Arial', fill: '#FFD700', stroke: '#000000', strokeThickness: 4
    }).setOrigin(0.5);

    // Info Text
    this.infoText = this.add.text(screenCenterX, this.gridConfig.startY + this.gridConfig.height + 40, '', {
      font: '24px Arial', fill: '#FFFFFF', stroke: '#000000', strokeThickness: 3, align: 'center'
    }).setOrigin(0.5);


    // Spin Button for Bonus Round
    this.spinButton = this.add.text(screenCenterX, bottomPanelY, 'SPIN', {
      font: 'bold 32px Arial', fill: '#4CAF50', backgroundColor: '#222222', padding: { x: 20, y: 10 },
      stroke: '#000000', strokeThickness: 2
    })
    .setOrigin(0.5)
    .setInteractive({ useHandCursor: true });

    this.spinButton.on('pointerdown', () => {
      if (this.respinsRemaining > 0) {
        this.handleSpin();
      }
    });

    // Initial update of UI text
    this.updateUIText();
  }

  updateUIText() {
    this.respinsText?.setText(`Respins: ${this.respinsRemaining}`);
    this.totalWinText?.setText(`Win: ${ (this.totalBonusWin * this.baseBet).toFixed(2) }`); // Display actual win value, formatted
  }

  placeInitialCoins() {
    if (!this.initialCoinsData) return;
    console.log('Placing initial coins:', this.initialCoinsData);
    this.initialCoinsData.forEach(coinData => {
      // Value from initialCoinsData could be a direct value or a multiplier
      // For consistency, let's assume it's a multiplier like other coins,
      // or adjust if it's meant to be a pre-calculated value.
      this.addCoinToGrid(coinData.col, coinData.row, coinData.value, true);
    });
  }

  addCoinToGrid(col, row, value, isInitialCoin = false) {
    if (this.heldCoins[`${col},${row}`]) {
      console.warn(`Attempted to add coin at already occupied slot: ${col},${row}`);
      return false; // Slot already occupied
    }

    const coinSymbolDef = this.gameConfig.game.symbols.find(s => s.id === this.bonusConfig.coinSymbolId);
    if (!coinSymbolDef) {
        console.error("Coin symbol definition not found! Cannot add coin to grid.");
        return false;
    }

    const iconFileName = coinSymbolDef.icon.split('/').pop().replace(/\..+$/, '');
    const textureKey = `${this.slotId}_${iconFileName}`; // e.g. "hack_coin"

    let coinSprite;
    const positionX = this.gridConfig.symbolSize.width / 2;
    const positionY = row * (this.gridConfig.symbolSize.height + (this.gameConfig.reel?.symbolSpacing || 0)) + this.gridConfig.symbolSize.height / 2;

    if (!this.textures.exists(textureKey)) {
        console.warn(`Texture key ${textureKey} not found for coin. Using fallback graphics.`);
        coinSprite = this.add.graphics()
            .fillStyle(0xFFD700, 1)
            .fillCircle(0, 0, this.gridConfig.symbolSize.width / 2 * 0.8); // Centered at 0,0 for container
        // coinSprite is a Graphics object, setDisplaySize not applicable. Scale it if needed.
        coinSprite.setScale(0.9); // Example scale
        this.heldCoins[`${col},${row}`] = { value: value, sprite: coinSprite, isGraphics: true };
    } else {
        coinSprite = this.add.image(0, 0, textureKey); // Centered at 0,0 for container
        coinSprite.setDisplaySize(this.gridConfig.symbolSize.width * 0.9, this.gridConfig.symbolSize.height * 0.9);
        this.heldCoins[`${col},${row}`] = { value: value, sprite: coinSprite };
    }

    coinSprite.setPosition(positionX, positionY);
    this.reelContainers[col].add(coinSprite);


    const valueText = this.add.text(
        positionX,
        positionY,
        `${value * this.baseBet}`,
        { font: 'bold 20px Arial', fill: '#000000', align: 'center' }
    ).setOrigin(0.5);
    this.reelContainers[col].add(valueText);
    this.heldCoins[`${col},${row}`].valueText = valueText;

    this.totalBonusWin += value;

    if (!isInitialCoin) {
        // Simple scale-in animation for newly landed coins
        coinSprite.setScale(0);
        valueText.setScale(0);
        this.tweens.add({
            targets: [coinSprite, valueText],
            scale: coinSprite.isGraphics ? 0.9 : 1, // Target scale for graphics vs image
            ease: 'Back.easeOut',
            duration: 300,
        });
    }

    console.log(`Added coin at ${col},${row} with value multiplier: ${value}. Initial: ${isInitialCoin}`);
    return true;
  }

  handleSpin() {
    console.log('BonusHoldAndWinScene: handleSpin() called');
    if (this.respinsRemaining <= 0 || this.checkIfGridFull()) {
        this.infoText.setText(this.checkIfGridFull() ? 'Grid Full!' : 'No respins left!');
        if (this.checkIfGridFull()) {
            this.time.delayedCall(1500, this.endBonus, [], this);
        }
        return;
    }

    this.respinsRemaining--;
    this.spinButton?.disableInteractive().setAlpha(0.5);
    this.infoText.setText('Spinning...');
    this.updateUIText();

    this.time.delayedCall(1000, () => {
      const newCoinsLandedThisSpin = this.attemptPlaceNewCoinsDuringSpin();

      if (newCoinsLandedThisSpin) {
        this.respinsRemaining = this.bonusConfig.resetRespinsValue || 3;
        this.infoText.setText('Coins Landed! Respins Reset!');
        // Play sound: EventBus.$emit('playSound', 'bonusCoinLand');
      } else {
        this.infoText.setText('No new coins.');
        // Play sound: EventBus.$emit('playSound', 'bonusNoNewCoin');
      }

      this.updateUIText();

      if (this.checkIfGridFull()) {
        this.infoText.setText('Grid Full! Calculating winnings...');
        this.time.delayedCall(1500, this.endBonus, [], this);
      } else if (this.respinsRemaining <= 0) {
        this.infoText.setText('No respins left! Calculating winnings...');
        this.time.delayedCall(1500, this.endBonus, [], this);
      } else {
        this.spinButton?.setInteractive(true).setAlpha(1.0);
      }
    });
  }

  attemptPlaceNewCoinsDuringSpin() {
    let landedAtLeastOneCoin = false;
    const emptySlots = this.getEmptySlots();
    if (emptySlots.length === 0) return false;

    const coinAppearanceChance = this.bonusConfig.coinAppearanceChancePerSlot || 0.15; // Default 15% chance per empty slot

    emptySlots.forEach(slot => {
      if (Math.random() < coinAppearanceChance) {
        let coinValue = 1; // Default value multiplier
        if (this.bonusConfig.coinValueSource === 'fixed' && typeof this.bonusConfig.fixedCoinValue !== 'undefined') {
            coinValue = this.bonusConfig.fixedCoinValue;
        } else if (this.bonusConfig.coinValueSource === 'randomRange' && this.bonusConfig.coinValueRange) {
            coinValue = Phaser.Math.Between(this.bonusConfig.coinValueRange[0], this.bonusConfig.coinValueRange[1]);
        }

        if (this.addCoinToGrid(slot.col, slot.row, coinValue, false)) {
            landedAtLeastOneCoin = true;
        }
      }
    });

    return landedAtLeastOneCoin;
  }

  getEmptySlots() {
    const emptySlots = [];
    for (let r = 0; r < this.gridConfig.rows; r++) {
      for (let c = 0; c < this.gridConfig.cols; c++) {
        if (!this.heldCoins[`${c},${r}`]) {
          emptySlots.push({ col: c, row: r });
        }
      }
    }
    return emptySlots;
  }

  checkIfGridFull() {
    return this.getEmptySlots().length === 0;
  }

  endBonus() {
    console.log('BonusHoldAndWinScene: endBonus() called');
    this.spinButton?.disableInteractive().setAlpha(0.5);
    const finalWinAmount = this.totalBonusWin * this.baseBet;
    this.infoText.setText(`Bonus Over! Final Win: ${finalWinAmount}`);
    console.log(`Bonus game ended. Total win multiplier: ${this.totalBonusWin}, Actual win: ${finalWinAmount}`);

    // Emit an event with the bonus result
    EventBus.$emit('bonusGameComplete', { winAmount: finalWinAmount, bonusConfig: this.bonusConfig });

    // Transition back to GameScene after a delay
    this.time.delayedCall(3000, () => {
      this.scene.stop('BonusHoldAndWinScene');
      // GameScene should be listening and resume itself and UIScene
    });
  }
}
