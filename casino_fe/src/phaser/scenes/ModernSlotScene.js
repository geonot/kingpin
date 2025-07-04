import Phaser from 'phaser';
import EventBus from '@/event-bus';
import { formatSatsToBtc } from '@utils/currencyFormatter'; // For win display formatting

// Constants for animations and timings
const REEL_SPIN_DURATION_BASE = 800; // Base duration for a reel spin (ms)
const REEL_SPIN_DURATION_TURBO = 200;
const REEL_START_DELAY = 150; // Stagger delay between starting each reel (ms)
const REEL_STOP_DELAY = 250; // Additional delay between stopping each reel (ms)
const SYMBOL_WIN_ANIM_DURATION = 300; // Duration for symbol scale/pulse animation (Increased from 250)
const PAYLINE_SHOW_DURATION = 5000; // How long each winning payline is shown (ms) - INCREASED FOR DEBUGGING
const TOTAL_WIN_DISPLAY_DURATION = 3000; // How long the total win amount is shown prominently
const CASCADE_POP_DURATION = 200; // Duration for symbol pop animation in cascades
const BIG_WIN_THRESHOLD_MULTIPLIER = 20;
const MEGA_WIN_THRESHOLD_MULTIPLIER = 50;
const BIG_WIN_DISPLAY_DURATION = 2500;
const WIN_COUNTUP_DURATION = 1000;


export default class ModernSlotScene extends Phaser.Scene {
  constructor() {
    super({ key: 'ModernSlotScene' });

    // Game state properties
    this.isSpinning = false;
    this.isProcessingBigWin = false;
    this.isMultiwayGame = false; // A.2
    this.currentPanesPerReel = []; // A.2
    this.targetPanesPerReel = []; // A.2
    this.reels = []; // Array of Phaser Groups, one for each reel column
    this.reelContainers = []; // Array of containers holding each reel's symbols
    this.symbolMap = {}; // Map to easily access symbols at [col, row] -> symbol object
    this.paylineGraphics = null; // Graphics object for drawing paylines
    this.winEmitter = null; // Particle emitter for wins
    this.currentWinDisplay = null; // Text object for showing individual line wins or total win
    this.bigWinTextDisplay = null; // Text object for Big Win messages
    this.activeWinTweens = []; // Store tweens related to winning symbols/lines
    this.paylineTimer = null; // Timer event for cycling through paylines

    // Settings synced from registry/events
    this.turboSpinEnabled = false;
    this.soundEnabled = true;

    // Config loaded from registry
    this.gameConfig = null;
    this.slotId = null;
    this.symbolSize = { width: 100, height: 100 }; // Default, loaded from config
    this.dynamicSymbolSize = { width: 100, height: 100 }; // For responsive layout
    this.safeArea = { x: 0, y: 0, width: 0, height: 0 }; // For responsive layout
    // A.2 Initialize gridConfig with more comprehensive defaults
    this.gridConfig = {
        cols: 5,
        rows: 3, // Base rows, will be overridden for multiway initial max height
        startX: 0,
        startY: 0,
        width: 0,
        height: 0,
        initialRowsPerReel: [],
        maxRowsForSymbolMap: 3, // Max possible rows any reel can show + buffers
        currentActualMaxRows: 3 // Current max rows based on targetPanesPerReel or initial
    };

    // Cascade feature properties
    this.isCascadingSlot = false;
    this.cascadeWinMultipliers = [];
    this.currentCascadeMultiplierLevel = 0; // From backend response
  }

  // No preload here - assets are loaded in PreloadScene

  calculateResponsiveLayout(screenWidth, screenHeight, configRows, configCols) {
    // Define Safe Area
    const reservedTopSpace = screenHeight * 0.05; // e.g., for potential top UI elements or just margin
    const reservedBottomSpace = screenHeight * 0.20; // for main UI controls
    const reservedHorizontalSpace = screenWidth * 0.10; // total, so 5% each side
    this.safeArea.x = (screenWidth * 0.05);
    this.safeArea.y = reservedTopSpace;
    this.safeArea.width = screenWidth - reservedHorizontalSpace;
    this.safeArea.height = screenHeight - reservedTopSpace - reservedBottomSpace;

    // Get Spacing from Config (or default)
    const reelSpacing = this.gameConfig.game.reel.reelSpacing || 5;
    const symbolSpacing = this.gameConfig.game.reel.symbolSpacing || 5;

    // Calculate Max Symbol Dimensions
    const maxSymbolWidth = (this.safeArea.width - (configCols - 1) * reelSpacing) / configCols;
    const maxSymbolHeight = (this.safeArea.height - (configRows - 1) * symbolSpacing) / configRows;

    // Determine Final Symbol Size (maintaining 1:1 aspect ratio for now)
    let calculatedSize = Math.min(maxSymbolWidth, maxSymbolHeight);
    calculatedSize = Math.max(calculatedSize, 30); // Add a minimum symbol size (e.g., 30px)
    this.dynamicSymbolSize = { width: calculatedSize, height: calculatedSize };

    // Update gridConfig
    this.gridConfig.rows = configRows;
    this.gridConfig.cols = configCols;
    this.gridConfig.width = configCols * this.dynamicSymbolSize.width + (configCols - 1) * reelSpacing;
    this.gridConfig.height = configRows * this.dynamicSymbolSize.height + (configRows - 1) * symbolSpacing;
    this.gridConfig.startX = this.safeArea.x + (this.safeArea.width - this.gridConfig.width) / 2; // Center grid in safe area
    this.gridConfig.startY = this.safeArea.y + (this.safeArea.height - this.gridConfig.height) / 2; // Center grid in safe area

    this.gridConfig.initialRowsPerReel = Array(configCols).fill(configRows);
    this.gridConfig.maxRowsForSymbolMap = configRows;
    this.gridConfig.currentActualMaxRows = configRows;
  }

  create() {
    console.log('ModernSlotScene: Create');

    const slotApiData = this.registry.get('slotApiData');
    const slotGameJsonConfig = this.registry.get('slotGameJsonConfig');

    this.gameConfig = slotGameJsonConfig;
    this.slotId = slotApiData?.id;
    this.turboSpinEnabled = this.registry.get('turboEnabled');
    this.soundEnabled = this.registry.get('soundEnabled');
    this.sound.mute = !this.soundEnabled;

    if (!this.gameConfig || !this.slotId) {
        console.error("ModernSlotScene: Missing game configuration or Slot ID!");
        EventBus.$emit('phaserError', 'Game initialization failed: Missing configuration.');
        return;
    }

    this.isCascadingSlot = this.gameConfig.game?.is_cascading || false;
    this.cascadeWinMultipliers = this.gameConfig.game?.win_multipliers || [];

    this.isMultiwayGame = (this.gameConfig.type === 'multiway');
    const { rows: configRows, columns: configCols } = this.gameConfig.game.layout;

    this.calculateResponsiveLayout(this.cameras.main.width, this.cameras.main.height, configRows, configCols);
    this.currentPanesPerReel = [...this.gridConfig.initialRowsPerReel]; // Initialize after gridConfig is set

    // this.symbolSize can be kept as a config default if needed, but dynamicSymbolSize is used for rendering.
    // The old way of calculating startX, startY, totalGridWidth, totalGridHeight is removed.

    this.createBackground();
    this.createReels(); // Creates reel containers and initial symbols
    this.createMask(); // Masks symbols outside the visible grid area
    this.createBorders(); // Adds visual borders around reels/grid
    this.createParticles(); // Creates particle emitter for win effects
    this.createPaylineGraphics(); // Graphics object for drawing lines
    this.createWinDisplay(); // Text object for showing win amounts
    this.createBigWinDisplay(); // Text object for Big Win messages

    // --- Event Listeners ---
    // Listen for settings changes from SettingsModalScene or Vue
    EventBus.$on('turboSettingChanged', (isEnabled) => {
      this.turboSpinEnabled = isEnabled;
      console.log('ModernSlotScene: Turbo spin set to', this.turboSpinEnabled);
    });
     EventBus.$on('soundSettingChanged', (isEnabled) => {
      this.soundEnabled = isEnabled;
      this.sound.mute = !this.soundEnabled;
      console.log('ModernSlotScene: Sound set to', this.soundEnabled ? 'ON' : 'OFF');
    });

    console.log('ModernSlotScene: Ready.');
    // Notify Vue that Phaser is ready (if needed)
    // EventBus.$emit('phaserReady');

    EventBus.$on('bonusGameComplete', (data) => this.handleBonusComplete(data));
    EventBus.$on('vueSpinResult', (responseData) => this.handleSpinResult(responseData)); // Listen for spin results from Vue
  }

  shutdown() {
    console.log('ModernSlotScene: shutdown');
    EventBus.$off('turboSettingChanged');
    EventBus.$off('soundSettingChanged');
    EventBus.$off('bonusGameComplete');
    EventBus.$off('vueSpinResult'); // Unregister listener

    this.reels.forEach(reelSymbols => {
        reelSymbols.forEach(symbol => {
            this.tweens.killTweensOf(symbol); // Kill any active tweens on symbols
            symbol.destroy(); // Destroy symbols
        });
    });
    this.reels = [];
    this.reelContainers.forEach(container => container.destroy()); // Destroy containers
    this.reelContainers = [];
    this.symbolMap = {};

    this.paylineGraphics?.destroy();
    this.winEmitter?.destroy(); // Destroy particle emitter
    this.currentWinDisplay?.destroy();

    if (this.paylineTimer) this.paylineTimer.remove();

    // It's good practice to also nullify references if the scene might be restarted
    this.gameConfig = null;
    this.slotId = null;
  }

  // Adding destroy method to call shutdown for completeness, standard Phaser practice
  destroy() {
    this.shutdown();
    super.destroy();
  }

  createBackground() {
    const { width, height } = this.cameras.main;
    const bg = this.add.image(width / 2, height / 2, 'background');

    // Enhanced background scaling for Classic 3x3
    const bgConfig = this.gameConfig.game.background;
    if (bgConfig && bgConfig.scale) {
      bg.setScale(bgConfig.scale.x, bgConfig.scale.y);
    } else if (bgConfig && bgConfig.position) {
      // Position-based centering
      bg.setPosition(bgConfig.position.x, bgConfig.position.y);
      // Smart scaling to fill viewport while maintaining aspect ratio
      const scaleX = width / bg.width;
      const scaleY = height / bg.height;
      bg.setScale(Math.max(scaleX, scaleY));
    } else {
      // Default: scale to cover viewport
      const scaleX = width / bg.width;
      const scaleY = height / bg.height;
      bg.setScale(Math.max(scaleX, scaleY));
    }

    bg.setScrollFactor(0).setDepth(-1);
  }

 createReels() {
    this.reels = [];
    this.reelContainers = [];
    this.symbolMap = {};

    const { cols, startX, startY } = this.gridConfig; // Use gridConfig.cols
    const { dynamicSymbolSize } = this; // Use dynamicSymbolSize
    const reelSpacing = this.gameConfig.game.reel.reelSpacing || 5; // Use same default as in responsiveCalc
    const symbolSpacing = this.gameConfig.game.reel.symbolSpacing || 5; // Use same default

    // B.1: Number of symbols per reel: max possible rows + buffer
    const symbolsToCreatePerReel = this.gridConfig.maxRowsForSymbolMap + 4; // Increased buffer to prevent gaps

    for (let c = 0; c < cols; c++) {
      const reelX = startX + c * (symbolSize.width + reelSpacing);
      const reelContainer = this.add.container(reelX, startY);
      this.reelContainers.push(reelContainer);

      const currentReelSymbols = [];

      for (let i = 0; i < symbolsToCreatePerReel; i++) {
        const randomSymbolConfig = this.getRandomSymbolConfig();
        const symbolKey = `symbol-${randomSymbolConfig.id}`; // Use the correct key format from PreloadScene
        const symbolY = i * (dynamicSymbolSize.height + symbolSpacing);

        // Fix: Set origin first, then setDisplaySize to avoid scaling artifacts
        const symbol = this.add.image(dynamicSymbolSize.width / 2, symbolY + dynamicSymbolSize.height / 2, symbolKey)
          .setOrigin(0.5)
          .setDisplaySize(dynamicSymbolSize.width, dynamicSymbolSize.height);

        reelContainer.add(symbol);
        currentReelSymbols.push(symbol);

        // B.2: Set visibility and map initially visible symbols
        const isVisibleInitially = i < this.currentPanesPerReel[c];
        symbol.setVisible(isVisibleInitially);
        if (isVisibleInitially) {
           this.symbolMap[`${c},${i}`] = symbol;
           symbol.setData('gridPosition', { col: c, row: i });
        }
      }
      this.reels.push(currentReelSymbols);
    }
  }

  getRandomSymbolConfig() {
    // Helper to get a random symbol config for initial reel population
    const symbols = this.gameConfig.game.symbols;
    return symbols[Phaser.Math.Between(0, symbols.length - 1)];
  }

  createMask() {
    // Mask height should be based on the maximum possible visible area for multiway
    // or the standard grid height for normal slots.
    // this.gridConfig.rows now represents the max initial height for multiway.
    const { rows, cols, startX, startY } = this.gridConfig; // These are now from calculateResponsiveLayout
    const { dynamicSymbolSize } = this; // Use dynamicSymbolSize
    const reelSpacing = this.gameConfig.game.reel.reelSpacing || 5;
    const symbolSpacing = this.gameConfig.game.reel.symbolSpacing || 5;

    const maskWidth = cols * dynamicSymbolSize.width + (cols - 1) * reelSpacing;
    // For multiway, the mask height should accommodate the maximum possible symbols on any reel,
    // but visually it's often tied to the initial display or a fixed max.
    // For now, use this.gridConfig.rows which is set to max(initialPanes) for multiway.
    const maskHeight = this.gridConfig.rows * dynamicSymbolSize.height + (this.gridConfig.rows - 1) * symbolSpacing;

    const maskShape = this.make.graphics();
    maskShape.fillStyle(0xffffff);
    // Mask position is relative to the game canvas origin (0,0)
    maskShape.fillRect(startX, startY, maskWidth, maskHeight);

    const mask = maskShape.createGeometryMask();
    mask.invertAlpha = false; // Show only what's inside the mask rectangle

    // Apply mask to each reel container
    this.reelContainers.forEach(container => {
      container.setMask(mask);
    });
  }

  createBorders() {
    const { rows, cols, startX, startY, width, height } = this.gridConfig; // These are now from calculateResponsiveLayout
    const { dynamicSymbolSize } = this; // Use dynamicSymbolSize
    const reelSpacing = this.gameConfig.game.reel.reelSpacing || 5;
    const symbolSpacing = this.gameConfig.game.reel.symbolSpacing || 5;

    const borderGraphics = this.add.graphics().setDepth(10); // Ensure borders are on top

    const outerLineWidth = 3;
    const innerLineWidth = 1;
    const outerColor = 0xd4af37; // Gold
    const innerColor = 0xaaaaaa; // Light Gray/Silver
    const alpha = 0.8;

    // Outer border
    borderGraphics.lineStyle(outerLineWidth, outerColor, alpha);
    borderGraphics.strokeRect(startX - outerLineWidth / 2, startY - outerLineWidth / 2, width + outerLineWidth, height + outerLineWidth);

    // Inner vertical lines (between columns)
    borderGraphics.lineStyle(innerLineWidth, innerColor, alpha);
    for (let c = 1; c < cols; c++) {
      const x = startX + c * (dynamicSymbolSize.width + reelSpacing) - reelSpacing / 2;
      borderGraphics.lineBetween(x, startY, x, startY + height);
    }

    // Inner horizontal lines (between rows)
    for (let r = 1; r < rows; r++) {
      const y = startY + r * (dynamicSymbolSize.height + symbolSpacing) - symbolSpacing / 2;
      borderGraphics.lineBetween(startX, y, startX + width, y);
    }
  }

  createParticles() {
     this.winEmitter = this.add.particles(0, 0, 'win-particle', {
            speed: { min: 100, max: 300 },
            angle: { min: 220, max: 320 }, // Emit downwards-ish arc
            scale: { start: 0.8, end: 0 },
            lifespan: 800,
            quantity: 10, // Emit 10 particles per burst
            frequency: -1, // Emit only on demand (burst)
            gravityY: 400,
            blendMode: 'ADD' // Bright additive blending
        }).setDepth(15); // Ensure particles are visible
  }

  createPaylineGraphics() {
      this.paylineGraphics = this.add.graphics().setDepth(12); // Above symbols, below UI potentially
  }

  createWinDisplay() {
       this.currentWinDisplay = this.add.text(
            this.cameras.main.width / 2,
            this.gridConfig.startY + this.gridConfig.height + 30, // Position below the reels
            '', // Initially empty
            {
                font: 'bold 28px Arial',
                fill: '#FFD700', // Gold color
                stroke: '#000000',
                strokeThickness: 4,
                align: 'center'
            }
        ).setOrigin(0.5).setDepth(20); // Above most elements
        this.currentWinDisplay.setVisible(false); // Hide initially
  }

 // --- Spin Logic ---

  handleSpinResult(responseData) {
      console.log('ModernSlotScene received spin result from Vuex:', responseData);
      this.lastSpinResponse = responseData; // Store the full response

      // Extract data needed for animations and display
      // Backend sends initial grid as 'result' (not 'spin_result')
      const initialGrid = responseData.result;
      this.currentCascadeMultiplierLevel = responseData.current_multiplier_level || 0;

      let transposedTargetGrid;

      if (this.isMultiwayGame) {
          // Assuming multiway structure within result if applicable, or adjust as needed
          // For now, let's assume 'initialGrid' is already correctly structured or needs similar processing
          // This part might need specific adaptation if multiway slots also become cascading with varying panes
          console.warn("Multiway cascading visuals might need specific handling for pane changes during cascades - not yet fully implemented.")
          // Fallback to standard grid processing for now if structure is {result: [[r,c]]}
          this.targetPanesPerReel = Array(this.gridConfig.cols).fill(this.gridConfig.rows); // Default for now
          const formattedGrid = this.formatSpinResult(initialGrid);
          transposedTargetGrid = this.transposeMatrix(formattedGrid);
      } else {
          this.targetPanesPerReel = Array(this.gridConfig.cols).fill(this.gridConfig.rows);
          const formattedGrid = this.formatSpinResult(initialGrid);
          transposedTargetGrid = this.transposeMatrix(formattedGrid);
      }

      // Reset multiplier display in UI at the start of a new spin animation sequence
      EventBus.$emit('uiUpdateMultiplier', { level: 0, multipliersConfig: this.cascadeWinMultipliers });
      this.startReelSpinAnimation(transposedTargetGrid);
  }

  startReelSpinAnimation(transposedTargetGrid) {
      if (this.isSpinning) return;
      this.isSpinning = true;
      this.clearWinAnimations();

      // Additional reset: Ensure ALL symbols start with proper scale and size
      this.reels.forEach((reelSymbols) => {
          reelSymbols.forEach((symbol) => {
              if (symbol && symbol.active) {
                  // Kill any lingering tweens
                  this.tweens.killTweensOf(symbol);
                  // Reset to normal state
                  symbol.setScale(1);
                  symbol.setDepth(2);
                  symbol.setAlpha(1);
                  symbol.setOrigin(0.5);
                  // Ensure proper display size
                  symbol.setDisplaySize(this.dynamicSymbolSize.width, this.dynamicSymbolSize.height);
              }
          });
      });

      EventBus.$emit('lineWinUpdate', { winAmount: 0, isScatter: false, ways: undefined });
      // Reset UI multiplier display via UIScene at the beginning of a new spin
      EventBus.$emit('uiUpdateMultiplier', { level: 0, multipliersConfig: this.cascadeWinMultipliers });
      this.playSound(`${this.slotId}_spin_sound`); // Use slot-specific sound key

      const spinDuration = this.turboSpinEnabled ? REEL_SPIN_DURATION_TURBO : REEL_SPIN_DURATION_BASE;
      const numReels = this.gridConfig.cols;
      let completedReels = 0;

      this.reels.forEach((reelSymbols, reelIndex) => {
          this.time.delayedCall(reelIndex * REEL_START_DELAY, () => {
              this.spinReel(reelIndex, reelSymbols, spinDuration, transposedTargetGrid[reelIndex], () => {
                  completedReels++;
                  this.playSound(`${this.slotId}_reel_stop_sound`); // Use slot-specific sound key
                  if (completedReels === numReels) {
                      this.onAllReelsStopped();
                  }
              });
          });
      });
  }

  spinReel(reelIndex, reelSymbols, baseDuration, targetSymbolIdsForThisReel, onCompleteCallback) { // D
    const { startY } = this.gridConfig; // rows is now dynamic for multiway
    const { dynamicSymbolSize } = this; // Use dynamicSymbolSize
    const symbolSpacing = this.gameConfig.game.reel.symbolSpacing || 5;
    const symbolHeightWithSpacing = dynamicSymbolSize.height + symbolSpacing;
    const reelContainer = this.reelContainers[reelIndex];

    // totalReelHeight for wrapping based on max possible symbols
    const totalReelHeight = reelSymbols.length * symbolHeightWithSpacing;
    // visibleHeight based on *current* number of panes for this reel for stop positioning
    const targetVisibleHeightThisReel = (this.targetPanesPerReel[reelIndex] || this.gridConfig.rows) * symbolHeightWithSpacing;

    const wraps = 3;
    const wrapDistance = wraps * totalReelHeight;
    // Fix: More progressive timing - increase gap between reels
    const spinDuration = baseDuration + (reelIndex * 200); // Increased from 120ms to 200ms
    const spinDistance = wrapDistance + targetVisibleHeightThisReel;

    // Pre-populate symbols above the visible area to prevent gaps
    reelSymbols.forEach((symbol, i) => {
        if (i >= this.gridConfig.maxRowsForSymbolMap) {
            // Position extra symbols above the visible area
            symbol.y = (i - reelSymbols.length) * symbolHeightWithSpacing + dynamicSymbolSize.height / 2;
            const randomSymbolConfig = this.getRandomSymbolConfig();
            symbol.setTexture(`symbol-${randomSymbolConfig.id}`);
            symbol.setVisible(true);
            // Fix: Ensure symbols are properly sized during spin
            symbol.setOrigin(0.5).setDisplaySize(dynamicSymbolSize.width, dynamicSymbolSize.height);
        }
    });

    this.tweens.add({
        targets: reelContainer,
        y: `+=${spinDistance}`,
        duration: spinDuration,
        ease: 'Back.easeOut', // Changed from Cubic.easeOut
        easeParams: [1.5], // Parameter for Back.easeOut
        onUpdate: () => {
            reelSymbols.forEach((symbol) => {
                const symbolWorldY = reelContainer.y + symbol.y;
                // More aggressive wrapping threshold to prevent gaps
                if (symbolWorldY > startY + targetVisibleHeightThisReel + symbolHeightWithSpacing * 2) {
                    symbol.y -= totalReelHeight;
                    const randomSymbolConfig = this.getRandomSymbolConfig();
                    symbol.setTexture(`symbol-${randomSymbolConfig.id}`);
                    // Fix: Ensure newly wrapped symbols are properly sized
                    symbol.setOrigin(0.5).setDisplaySize(dynamicSymbolSize.width, dynamicSymbolSize.height);
                }
            });
        },
        onComplete: () => { // D.1
            const landedPanesCount = this.targetPanesPerReel[reelIndex];
            this.currentPanesPerReel[reelIndex] = landedPanesCount;

            // D.1 Clear old symbolMap entries for this reel
            for (let r = 0; r < this.gridConfig.maxRowsForSymbolMap; r++) {
                delete this.symbolMap[`${reelIndex},${r}`];
            }

            reelSymbols.forEach((symbol, i) => { // D.1 Loop through all symbols in reel column
                if (i < landedPanesCount) {
                    const symbolConfig = this.gameConfig.game.symbols.find(s => s.id === targetSymbolIdsForThisReel[i]);
                    if (symbolConfig) {
                         symbol.setTexture(`symbol-${symbolConfig.id}`);
                    }
                    // Initial position for settle animation (slightly above)
                    const finalYPos = i * symbolHeightWithSpacing + dynamicSymbolSize.height / 2;
                    symbol.y = finalYPos - dynamicSymbolSize.height * 0.3; // Start slightly above

                    symbol.setVisible(true).setDepth(2);
                    // Ensure final symbols are properly sized
                    symbol.setOrigin(0.5).setDisplaySize(dynamicSymbolSize.width, dynamicSymbolSize.height);

                    // Add individual symbol settle animation
                    this.tweens.add({
                        targets: symbol,
                        y: finalYPos, // Animate to its correct final position
                        duration: 250, // Short duration
                        ease: 'Bounce.easeOut', // Bouncy effect
                        delay: Math.random() * 100, // Slight random delay
                        onComplete: () => {
                             // Ensure symbol is exactly at finalYPos after bounce
                            symbol.y = finalYPos;
                        }
                    });

                    this.symbolMap[`${reelIndex},${i}`] = symbol; // Update map for new visible symbols
                    symbol.setData('gridPosition', { col: reelIndex, row: i });
                } else {
                    symbol.setVisible(false); // Hide symbols beyond landedPanesCount
                }
            });
            reelContainer.y = startY; // Reset container to initial Y
            onCompleteCallback();
        }
    });
}

  onAllReelsStopped() {
      console.log('ModernSlotScene: All reels stopped.');
      this.isSpinning = false;
      this.isProcessingSpinResult = false; // Reset the processing flag
      // EventBus.$emit('spinAnimationComplete', this.lastSpinResponse); // Changed to phaserSpinResult

      const bonusConfig = this.gameConfig?.holdAndWinBonus;
      if (bonusConfig && bonusConfig.triggerSymbolId && bonusConfig.minTriggerCount && this.lastSpinResponse?.result) {
          const triggerSymbolId = bonusConfig.triggerSymbolId;
          let triggerCount = 0;
          const actualInitialCoins = [];

          // Determine grid structure from lastSpinResponse
          // Assuming this.lastSpinResponse.result.symbols_grid is [cols][rows] for multiway
          // and this.lastSpinResponse.result (which becomes formattedGrid) is [rows][cols] for standard
          const grid = this.isMultiwayGame ? this.lastSpinResponse.result.symbols_grid : this.transposeMatrix(this.formatSpinResult(this.lastSpinResponse.result));
          // Note: After transposeMatrix, standard grid is also [cols][rows] like multiway for this logic.

          if (grid) {
              for (let c = 0; c < grid.length; c++) {
                  const colSymbols = grid[c];
                  for (let r = 0; r < colSymbols.length; r++) {
                      if (colSymbols[r] === triggerSymbolId) {
                          triggerCount++;
                          // Store all found trigger symbols for potential use in initialCoins
                          // We'll only pass up to minTriggerCount or a specific number if defined in bonusConfig
                          actualInitialCoins.push({ col: c, row: r, value: bonusConfig.defaultCoinValue || 1 });
                      }
                  }
              }
          }

          console.log(`Hold and Win: Found ${triggerCount} of symbol ${triggerSymbolId}. Min required: ${bonusConfig.minTriggerCount}`);

          if (triggerCount >= bonusConfig.minTriggerCount) {
              console.log('Hold and Win Bonus Triggered!');
              this.playSound('snd-common-bonus-trigger'); // Make sure this is loaded

              // Optional: Select only minTriggerCount coins or specific logic from bonusConfig
              const coinsToPass = actualInitialCoins.slice(0, bonusConfig.maxInitialCoins || actualInitialCoins.length);


              const dataForBonus = {
                  gameConfig: this.gameConfig,
                  currentBet: this.lastSpinResponse.bet_amount,
                  initialCoins: coinsToPass
              };

              // EventBus.$emit('spinAnimationComplete', this.lastSpinResponse); // Changed to phaserSpinResult
              EventBus.$emit('phaserSpinResult', this.lastSpinResponse); // Emit before pausing for bonus

              this.scene.launch('BonusHoldAndWinScene', dataForBonus);
              this.scene.pause('ModernSlotScene');
              this.scene.pause('UIScene');
              return; // Return early to prevent normal win processing
          }
      }

      // If not a bonus trigger, emit the final spin result here.
      // If it was a bonus trigger, phaserSpinResult was emitted before launching bonus.
      EventBus.$emit('phaserSpinResult', this.lastSpinResponse);

      if (this.lastSpinResponse && this.lastSpinResponse.win_amount > 0) {
          const winMultiplier = this.lastSpinResponse.win_amount / this.lastSpinResponse.bet_amount;

          if (winMultiplier >= BIG_WIN_THRESHOLD_MULTIPLIER && !this.isProcessingBigWin) { // Ensure not already processing
              this.isProcessingBigWin = true;
              this.playBigWinSequence(this.lastSpinResponse.win_amount, winMultiplier, () => {
                  this.isProcessingBigWin = false;
                  if (this.lastSpinResponse.winning_lines && this.lastSpinResponse.winning_lines.length > 0) {
                      this.displayWinningLines(
                          this.lastSpinResponse.winning_lines || [],
                          this.lastSpinResponse.win_amount,
                          this.currentCascadeMultiplierLevel,
                          this.isCascadingSlot
                      );
                  } else {
                      this.clearWinAnimations();
                      EventBus.$emit('uiSetIdle');
                  }
                  EventBus.$emit('bigWinEnded'); // Emit when sequence and subsequent displays are done
              });
              return;
          }

          this.playSoundWin(this.lastSpinResponse.win_amount);
          // Display initial winning lines. Winning_lines in response is from initial spin.
          this.displayWinningLines(
              this.lastSpinResponse.winning_lines || [],
              this.lastSpinResponse.win_amount,
              this.currentCascadeMultiplierLevel, // Pass multiplier level
              this.isCascadingSlot
          );
      } else {
          // If no wins and no bonus, ensure UI is idle
          EventBus.$emit('uiSetIdle');
          // Also ensure multiplier display is reset if it wasn't a win
          EventBus.$emit('uiUpdateMultiplier', { level: 0, multipliersConfig: this.cascadeWinMultipliers });
      }
  }

  displayWinningLines(winningLines, totalWinAmountSats, currentCascadeLevel, isCascading) {
      // This function will now also handle updating the multiplier display after wins are shown.

      const hasInitialWins = winningLines && winningLines.length > 0;

      if (!hasInitialWins) {
           if (totalWinAmountSats > 0) { // Win might come purely from cascades not reflected in initial winning_lines
                this.showTotalWinAmount(totalWinAmountSats);
                // If it's a cascading slot and there was a total win, update multiplier display
                if (isCascading) {
                    EventBus.$emit('uiUpdateMultiplier', { level: currentCascadeLevel, multipliersConfig: this.cascadeWinMultipliers });
                }
                this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => {
                    this.clearWinAnimations();
                    if (isCascading && totalWinAmountSats > 0) {
                        // TODO: Here, ideally, we would show the final grid IF backend provided it.
                        // For now, symbols that popped just remain empty or grid resets on next spin.
                        // A quick "grid shimmer" or "cascade complete" effect could be added.
                        this.playCascadeSettleEffect();
                    }
                });
           } else {
               EventBus.$emit('uiSetIdle'); // No total win, ensure UI is idle
           }
          return;
      }

      // Process initial winning lines
      let currentLineIndex = 0;
      const displayNextLine = () => {
            this.clearWinAnimations(false); // Don't clear total win text yet
            if (currentLineIndex >= winningLines.length) { // All initial lines shown
                 console.log('ModernSlotScene: All lines shown, showing total win amount:', totalWinAmountSats);
                 this.showTotalWinAmount(totalWinAmountSats);
                 if (isCascading) { // If cascading, update multiplier display after initial lines
                    EventBus.$emit('uiUpdateMultiplier', { level: currentCascadeLevel, multipliersConfig: this.cascadeWinMultipliers });
                 }
                 if (this.paylineTimer) this.paylineTimer.remove();
                 this.paylineTimer = this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => {
                    this.clearWinAnimations(); // Clear everything including total win
                     if (isCascading && totalWinAmountSats > 0) {
                        // TODO: Animate final grid if available, or settle effect
                        this.playCascadeSettleEffect();
                    }
                 });
                return;
            }
            const winData = winningLines[currentLineIndex];
            // Only pop symbols in cascading slots, not regular slots
            this.highlightWin(winData, isCascading); // Pass isCascading instead of always true
            this.showIndividualWinAmount(winData.win_amount_sats, winData);
            currentLineIndex++;
            if (this.paylineTimer) this.paylineTimer.remove();
            this.paylineTimer = this.time.delayedCall(PAYLINE_SHOW_DURATION, displayNextLine);
        };
        displayNextLine();
  }

  highlightWin(winData, shouldPopSymbols = false) {
    this.paylineGraphics.clear();

    // Properly stop all existing win tweens and reset symbol properties
    this.activeWinTweens.forEach(({symbol, tween}) => {
        if (tween && tween.isPlaying()) tween.stop();
        if (symbol && symbol.active) {
            // Kill all tweens on this symbol to prevent accumulation
            this.tweens.killTweensOf(symbol);
            symbol.setScale(1).setDepth(2).setVisible(true).setAlpha(1); // Ensure proper reset
            // Ensure proper display size is maintained
            symbol.setDisplaySize(this.dynamicSymbolSize.width, this.dynamicSymbolSize.height);
        }
    });
    this.activeWinTweens = [];

    const animateSymbol = (col, row) => {
        const symbol = this.getSymbolAt(col, row);
        if (symbol && symbol.active) {
            // Kill any existing tweens on this symbol before starting new ones
            this.tweens.killTweensOf(symbol);

            // Ensure symbol is properly sized before animation
            symbol.setDisplaySize(this.dynamicSymbolSize.width, this.dynamicSymbolSize.height);
            symbol.setOrigin(0.5);
            symbol.setDepth(5);

            const symbolId = symbol.texture?.key?.split('-')[1];
            const symbolConfig = this.gameConfig.game.symbols.find(s => s.id.toString() === symbolId);

            const winAnimType = symbolConfig?.animations?.win?.type || 'pulse';
            const winAnimScale = symbolConfig?.animations?.win?.scale || 1.25;
            const winAnimDuration = symbolConfig?.animations?.win?.duration || SYMBOL_WIN_ANIM_DURATION;

            if (winAnimType === 'pulse') {
                const tween = this.tweens.add({
                    targets: symbol,
                    scale: { from: 1, to: winAnimScale },
                    ease: 'Sine.easeInOut',
                    duration: winAnimDuration,
                    yoyo: true,
                    repeat: shouldPopSymbols ? 1 : -1,
                    onUpdate: () => {
                        if (symbol && symbol.active) {
                            const currentScale = symbol.scale;
                            symbol.setDisplaySize(
                                this.dynamicSymbolSize.width * currentScale,
                                this.dynamicSymbolSize.height * currentScale
                            );
                        }
                    },
                    onComplete: () => {
                        if (shouldPopSymbols && symbol && symbol.active) {
                            this.tweens.add({
                                targets: symbol,
                                alpha: 0,
                                scale: 0.5,
                                duration: CASCADE_POP_DURATION,
                                ease: 'Power2',
                                onComplete: () => {
                                    if (symbol.active) symbol.setVisible(false);
                                }
                            });
                        } else {
                            if (symbol && symbol.active) {
                                symbol.setScale(1);
                                symbol.setDisplaySize(this.dynamicSymbolSize.width, this.dynamicSymbolSize.height);
                            }
                        }
                    }
                });
                this.activeWinTweens.push({ symbol, tween });
            } else if (winAnimType === 'shake') {
                const originalX = symbol.x;
                const tween = this.tweens.add({
                    targets: symbol,
                    x: originalX - 3,
                    duration: winAnimDuration / 4,
                    ease: 'Sine.easeInOut',
                    yoyo: true,
                    repeat: 3,
                    onComplete: () => { if(symbol.active) symbol.x = originalX; }
                });
                 this.activeWinTweens.push({ symbol, tween });
            }

            const worldPos = this.getSymbolWorldPosition(col, row);
            if (worldPos) this.winEmitter?.explode(10, worldPos.x, worldPos.y);
        }
    };

    const positionsToProcess = winData.positions; // F.3

    if (this.isMultiwayGame && !winData.is_scatter) { // F.4 Multiway (non-scatter)
        // positionsToProcess is expected as [[reel0_pos_list], [reel1_pos_list], ...]
        // where pos_list is [[c,r], [c,r], ...]
        if (Array.isArray(positionsToProcess)) {
            positionsToProcess.forEach(reelMatchPositions => { // Iterate over each reel's matches
                if (Array.isArray(reelMatchPositions)) {
                    reelMatchPositions.forEach(pos => { // Iterate over [c,r] in that reel
                        if (Array.isArray(pos) && pos.length === 2) {
                           animateSymbol(pos[0], pos[1]); // pos[0] is col, pos[1] is row
                        }
                    });
                }
            });
        }
    } else if (winData.is_scatter) { // F.5 Scatter (for both game types)
        // positionsToProcess is [[c,r], [c,r], ...]
         if (Array.isArray(positionsToProcess)) {
            positionsToProcess.forEach(pos => {
                if (Array.isArray(pos) && pos.length === 2) {
                    animateSymbol(pos[0], pos[1]); // pos[0] is col, pos[1] is row
                }
            });
        }
    } else { // F.6 Standard Payline game
        // positionsToProcess is [[r_backend,c_backend], ...]
        const linePoints = [];
        if (Array.isArray(positionsToProcess)) {
            positionsToProcess.forEach(pos => { // pos is [backend_row, backend_col]
                 if (Array.isArray(pos) && pos.length === 2) {
                    const col = pos[1]; // Backend sends [row, col]
                    const row = pos[0];
                    animateSymbol(col, row);
                    const worldPos = this.getSymbolWorldPosition(col, row);
                    if (worldPos) linePoints.push(new Phaser.Math.Vector2(worldPos.x, worldPos.y));
                }
            });
        }
        if (linePoints.length > 1) {
            const lineColor = this.getPaylineColor(winData.line_id || 0); // Use line_id or default
            console.log('ModernSlotScene: Drawing payline with', linePoints.length, 'points, color:', lineColor);
            this.paylineGraphics.lineStyle(5, lineColor, 0.9);
            this.paylineGraphics.fillStyle(lineColor, 0.8);
            for (let i = 0; i < linePoints.length - 1; i++) {
                this.paylineGraphics.lineBetween(linePoints[i].x, linePoints[i].y, linePoints[i + 1].x, linePoints[i + 1].y);
            }
            linePoints.forEach(p => this.paylineGraphics.fillCircle(p.x, p.y, 8));
            console.log('ModernSlotScene: Payline drawn successfully');

            this.tweens.killTweensOf(this.paylineGraphics); // Kill previous payline tween
            this.paylineGraphics.alpha = 0.5;
            this.tweens.add({
                targets: this.paylineGraphics,
                alpha: 0.9,
                duration: PAYLINE_SHOW_DURATION / 4,
                ease: 'Sine.easeInOut',
                yoyo: true,
                repeat: -1
            });
        } else {
            console.log('ModernSlotScene: Not enough points to draw payline, points:', linePoints.length);
        }
    }
}

clearWinAnimations(clearTotalWinText = true) { // H
    this.tweens.killTweensOf(this.bigWinTextDisplay);
    this.bigWinTextDisplay.setVisible(false);
    this.tweens.killTweensOf(this.paylineGraphics);
    this.paylineGraphics.alpha = 1;

    // First, stop all active win tweens and reset their symbols
    this.activeWinTweens.forEach(({symbol, tween}) => {
        if (tween && tween.isPlaying()) tween.stop();
        if (symbol && symbol.active) {
            // Kill all tweens on this symbol to prevent conflicts
            this.tweens.killTweensOf(symbol);
            symbol.setScale(1); // Reset scale
            symbol.setDepth(2); // H.1 Reset depth
            symbol.setAlpha(1); // Reset alpha in case it was changed
            // Ensure proper display size is reset
            symbol.setDisplaySize(this.dynamicSymbolSize.width, this.dynamicSymbolSize.height);
            symbol.setOrigin(0.5); // Ensure proper origin
        }
    });
    this.activeWinTweens = [];

    // Additional safety: Reset ALL visible symbols to ensure no symbols remain zoomed
    // This catches any symbols that might have completed their tweens but weren't properly reset
    for (let col = 0; col < this.gridConfig.cols; col++) {
        const maxRows = this.isMultiwayGame ? this.currentPanesPerReel[col] : this.gridConfig.rows;
        for (let row = 0; row < maxRows; row++) {
            const symbol = this.getSymbolAt(col, row);
            if (symbol && symbol.active) {
                // Kill any remaining tweens and ensure proper reset
                this.tweens.killTweensOf(symbol);
                symbol.setScale(1);
                symbol.setDepth(2);
                symbol.setAlpha(1);
                // Force proper display size reset
                symbol.setDisplaySize(this.dynamicSymbolSize.width, this.dynamicSymbolSize.height);
                symbol.setOrigin(0.5);
            }
        }
    }

    this.paylineGraphics?.clear();
    if (this.paylineTimer) {
        this.paylineTimer.remove(false);
        this.paylineTimer = null;
    }
    if (this.currentWinDisplay && clearTotalWinText) {
        this.tweens.killTweensOf(this.currentWinDisplay);
        this.currentWinDisplay.setVisible(false).setText('');
    }

    // Ensure UI is set to idle after clearing win animations
    if (clearTotalWinText) {
        EventBus.$emit('uiSetIdle');
    }
  }

  // Helper methods
  getSymbolAt(col, row) {
      return this.symbolMap[`${col},${row}`] || null;
  }

  getSymbolWorldPosition(col, row) {
      const symbol = this.getSymbolAt(col, row);
      if (!symbol) return null;
      const container = this.reelContainers[col];
      return {
          x: container.x + symbol.x,
          y: container.y + symbol.y
      };
  }

  showTotalWinAmount(totalWinAmountSats) {
      const winAmountBtc = formatSatsToBtc(totalWinAmountSats);
      this.currentWinDisplay.setText(`Total Win: ${winAmountBtc} BTC`);
      this.currentWinDisplay.setVisible(true);
      EventBus.$emit('lineWinUpdate', { winAmount: totalWinAmountSats, isScatter: false, ways: undefined });
  }

  showIndividualWinAmount(winAmountSats, winData) {
      const winAmountBtc = formatSatsToBtc(winAmountSats);
      let winText = `Line Win: ${winAmountBtc} BTC`;

      if (winData.is_scatter) {
          winText = `Scatter Win: ${winAmountBtc} BTC`;
      } else if (this.isMultiwayGame && winData.ways) {
          winText = `${winData.ways} Ways: ${winAmountBtc} BTC`;
      }

      this.currentWinDisplay.setText(winText);
      this.currentWinDisplay.setVisible(true);
      EventBus.$emit('lineWinUpdate', {
          winAmount: winAmountSats,
          isScatter: winData.is_scatter || false,
          ways: winData.ways
      });
  }

  getPaylineColor(lineId) {
      const colors = [0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff, 0x00ffff, 0xffa500, 0x800080];
      return colors[lineId % colors.length] || 0xffffff;
  }

  // Sound methods
  playSound(soundKey) {
      if (!this.soundEnabled || !soundKey) return;

      // Check if the sound exists before trying to play it
      const sound = this.sound.get(soundKey);
      if (sound) {
          this.sound.play(soundKey);
      } else {
          console.warn(`ModernSlotScene: Sound key "${soundKey}" not found or not loaded.`);
      }
  }

  playSoundWin(winAmount) {
      if (!this.soundEnabled) return;

      // Play different win sounds based on win amount
      if (winAmount > 100000) { // Big win
          this.playSound('snd-common-big-win');
      } else if (winAmount > 10000) { // Medium win
          this.playSound('snd-common-medium-win');
      } else {
          this.playSound('snd-common-small-win');
      }
  }

  playCascadeSettleEffect() {
      // Visual effect when cascades complete
      console.log('ModernSlotScene: Playing cascade settle effect');
      // Add visual shimmer or settling animation here if needed
  }

  // Utility methods for data formatting
  formatSpinResult(result) {
      if (Array.isArray(result) && Array.isArray(result[0])) {
          return result; // Already in correct format
      }
      console.warn('ModernSlotScene: Unexpected spin result format:', result);
      return [];
  }

  transposeMatrix(matrix) {
      if (!Array.isArray(matrix) || matrix.length === 0) return [];
      return matrix[0].map((_, colIndex) => matrix.map(row => row[colIndex]));
  }

  // Bonus game handler
  handleBonusComplete(data) {
      console.log('ModernSlotScene: Bonus game complete', data);
      this.scene.resume('ModernSlotScene');
      this.scene.resume('UIScene');

      // Handle any bonus winnings or state updates
      if (data.totalWin > 0) {
          // EventBus.$emit('balanceUpdate', data.totalWin); // Changed event
          EventBus.$emit('bonusWinningsCalculated', { totalWin: data.totalWin });
          this.showTotalWinAmount(data.totalWin); // Still show it locally in game scene
          this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => {
              this.clearWinAnimations();
                EventBus.$emit('uiSetIdle'); // Ensure UI is idle after bonus win display
          });
      } else {
        EventBus.$emit('uiSetIdle'); // Ensure UI is idle if bonus had no win
      }
  }

  createBigWinDisplay() {
    this.bigWinTextDisplay = this.add.text(
        this.cameras.main.width / 2,
        this.cameras.main.height / 2, // Centered
        '',
        {
            font: 'bold 64px ArialBlack, Arial, sans-serif', // More impactful font
            fill: '#FFDF00', // Gold
            stroke: '#A0522D', // Darker outline
            strokeThickness: 8,
            align: 'center',
            shadow: { offsetX: 3, offsetY: 3, color: '#000', blur: 5, stroke: true, fill: true }
        }
    ).setOrigin(0.5).setDepth(30).setVisible(false); // Above everything, initially hidden
  }

  playBigWinSequence(totalWinAmount, multiplier, onCompleteCallback) {
    EventBus.$emit('bigWinStarted');
    this.clearWinAnimations(true); // Clear previous wins first

    let bigWinText = 'BIG WIN!';
    if (multiplier >= MEGA_WIN_THRESHOLD_MULTIPLIER) bigWinText = 'MEGA WIN!';

    this.bigWinTextDisplay.setText(bigWinText).setVisible(true).setScale(0.5).setAlpha(0);
    this.tweens.add({
        targets: this.bigWinTextDisplay,
        scale: 1,
        alpha: 1,
        duration: 500,
        ease: 'Back.easeOut',
        yoyo: true, // Text briefly scales up then back to 1, then fades with main timer
        hold: BIG_WIN_DISPLAY_DURATION - 1000, // Hold for most of the sequence
        onComplete: () => {
            // Fade out at the end of the hold
             this.tweens.add({
                targets: this.bigWinTextDisplay,
                alpha: 0,
                duration: 500, // Fade out duration
                ease: 'Power1',
                onComplete: () => {
                    this.bigWinTextDisplay.setVisible(false);
                }
            });
        }
    });

    this.cameras.main.shake(500, 0.01);
    this.winEmitter?.explode(50, this.cameras.main.width / 2, this.cameras.main.height / 2);
    this.playSound('snd-common-big-win'); // Consider specific sounds for mega etc.

    this.currentWinDisplay.setText('0').setVisible(true);
    const displayObj = { value: 0 };
    this.tweens.add({
        targets: displayObj,
        value: totalWinAmount,
        duration: WIN_COUNTUP_DURATION,
        ease: 'Power1',
        onUpdate: () => {
            if(this.currentWinDisplay && this.currentWinDisplay.active) {
                 this.currentWinDisplay.setText(formatSatsToBtc(Math.floor(displayObj.value)));
            }
        },
        onComplete: () => {
            if(this.currentWinDisplay && this.currentWinDisplay.active) {
                this.currentWinDisplay.setText(formatSatsToBtc(totalWinAmount));
            }
            // Delay before calling the main onCompleteCallback for the big win sequence
            this.time.delayedCall(BIG_WIN_DISPLAY_DURATION - WIN_COUNTUP_DURATION, () => {
                // bigWinTextDisplay fadeout is handled by its own tween's onComplete
                // EventBus.$emit('bigWinEnded'); // Moved to onAllReelsStopped callback
                onCompleteCallback();
            });
        }
    });
  }
}