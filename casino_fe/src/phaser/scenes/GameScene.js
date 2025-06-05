import Phaser from 'phaser';
import EventBus from '@/event-bus';
import { formatSatsToBtc } from '@utils/currencyFormatter'; // For win display formatting

// Constants for animations and timings
const REEL_SPIN_DURATION_BASE = 800; // Base duration for a reel spin (ms)
const REEL_SPIN_DURATION_TURBO = 200;
const REEL_START_DELAY = 150; // Stagger delay between starting each reel (ms)
const REEL_STOP_DELAY = 250; // Additional delay between stopping each reel (ms)
const SYMBOL_WIN_ANIM_DURATION = 250; // Duration for symbol scale/pulse animation
const PAYLINE_SHOW_DURATION = 1500; // How long each winning payline is shown (ms)
const TOTAL_WIN_DISPLAY_DURATION = 3000; // How long the total win amount is shown prominently
const SYMBOL_WIN_ANIM_DURATION = 250; // Already defined, ensure this is the one used


export default class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });

    // Game state properties
    this.isSpinning = false;
    this.isMultiwayGame = false; // A.2
    this.currentPanesPerReel = []; // A.2
    this.targetPanesPerReel = []; // A.2
    this.reels = []; // Array of Phaser Groups, one for each reel column
    this.reelContainers = []; // Array of containers holding each reel's symbols
    this.symbolMap = {}; // Map to easily access symbols at [col, row] -> symbol object
    this.paylineGraphics = null; // Graphics object for drawing paylines
    this.winEmitter = null; // Particle emitter for wins
    this.currentWinDisplay = null; // Text object for showing individual line wins or total win
    this.activeWinTweens = []; // Store tweens related to winning symbols/lines
    this.paylineTimer = null; // Timer event for cycling through paylines

    // Settings synced from registry/events
    this.turboSpinEnabled = false;
    this.soundEnabled = true;

    // Config loaded from registry
    this.gameConfig = null;
    this.slotId = null;
    this.symbolSize = { width: 100, height: 100 }; // Default, loaded from config
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
  }

  // No preload here - assets are loaded in PreloadScene

  create() {
    console.log('GameScene: Create');
    this.gameConfig = this.registry.get('gameConfig');
    this.slotId = this.registry.get('slotId');
    this.turboSpinEnabled = this.registry.get('turboEnabled');
    this.soundEnabled = this.registry.get('soundEnabled');
    // Apply initial sound setting
    this.sound.mute = !this.soundEnabled;

    if (!this.gameConfig || !this.slotId) {
        console.error("GameScene: Missing game configuration or Slot ID!");
        EventBus.$emit('phaserError', 'Game initialization failed: Missing configuration.');
        return;
    }

    // A.3: Game Type and Grid Configuration
    this.isMultiwayGame = (this.gameConfig.type === 'multiway');
    const { rows, columns } = this.gameConfig.layout; // Base definitions

    this.gridConfig.cols = columns;

    if (this.isMultiwayGame) {
        this.gridConfig.initialRowsPerReel = this.gameConfig.layout.default_pane_counts || Array(columns).fill(rows || 3);
        // Effective rows for initial grid height calculation (max of initial panes)
        this.gridConfig.rows = Math.max(...this.gridConfig.initialRowsPerReel);
        // Max possible rows any symbol could occupy across all reels for symbol map buffer
        this.gridConfig.maxRowsForSymbolMap = Math.max(...(this.gameConfig.layout.possible_pane_counts || [[rows || 3]]).flat());
    } else {
        this.gridConfig.rows = rows || 3;
        this.gridConfig.initialRowsPerReel = Array(columns).fill(this.gridConfig.rows);
        this.gridConfig.maxRowsForSymbolMap = this.gridConfig.rows;
    }
    this.currentPanesPerReel = [...this.gridConfig.initialRowsPerReel];
    this.gridConfig.currentActualMaxRows = Math.max(...this.currentPanesPerReel, this.gridConfig.rows);


    this.symbolSize = this.gameConfig.reel.symbolSize || { width: 100, height: 100 };
    // Calculate totalReelWidth and totalReelHeight based on the effective gridConfig.rows for multiway
    const totalReelWidth = this.gridConfig.cols * this.symbolSize.width + (this.gridConfig.cols - 1) * (this.gameConfig.reel.reelSpacing || 0);
    const totalReelHeight = this.gridConfig.rows * this.symbolSize.height + (this.gridConfig.rows - 1) * (this.gameConfig.reel.symbolSpacing || 0);

    const configStartX = this.gameConfig.reel.position?.x ?? (this.cameras.main.width - totalReelWidth) / 2;
    const configStartY = this.gameConfig.reel.position?.y ?? 100;

    // Update gridConfig with calculated dimensions
    this.gridConfig.startX = configStartX;
    this.gridConfig.startY = configStartY;
    this.gridConfig.width = totalReelWidth;
    this.gridConfig.height = totalReelHeight;

    this.createBackground();
    this.createReels(); // Creates reel containers and initial symbols
    this.createMask(); // Masks symbols outside the visible grid area
    this.createBorders(); // Adds visual borders around reels/grid
    this.createParticles(); // Creates particle emitter for win effects
    this.createPaylineGraphics(); // Graphics object for drawing lines
    this.createWinDisplay(); // Text object for showing win amounts

    // --- Event Listeners ---
    // Listen for settings changes from SettingsModalScene or Vue
    EventBus.$on('turboSettingChanged', (isEnabled) => {
      this.turboSpinEnabled = isEnabled;
      console.log('GameScene: Turbo spin set to', this.turboSpinEnabled);
    });
     EventBus.$on('soundSettingChanged', (isEnabled) => {
      this.soundEnabled = isEnabled;
      this.sound.mute = !this.soundEnabled;
      console.log('GameScene: Sound set to', this.soundEnabled ? 'ON' : 'OFF');
    });

    console.log('GameScene: Ready.');
    // Notify Vue that Phaser is ready (if needed)
    // EventBus.$emit('phaserReady');

    EventBus.$on('bonusGameComplete', this.handleBonusComplete, this);
  }

  shutdown() {
    console.log('GameScene: shutdown');
    EventBus.$off('turboSettingChanged');
    EventBus.$off('soundSettingChanged');
    EventBus.$off('bonusGameComplete', this.handleBonusComplete, this);

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
    // Scale background to cover the whole game area
    const scaleX = width / bg.width;
    const scaleY = height / bg.height;
    bg.setScale(Math.max(scaleX, scaleY)).setScrollFactor(0); // Cover and don't scroll
    bg.setDepth(-1); // Ensure background is behind everything
  }

 createReels() {
    this.reels = [];
    this.reelContainers = [];
    this.symbolMap = {};

    const { cols, startX, startY } = this.gridConfig; // Use gridConfig.cols
    const { symbolSize } = this;
    const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;

    // B.1: Number of symbols per reel: max possible rows + buffer
    const symbolsToCreatePerReel = this.gridConfig.maxRowsForSymbolMap + 2;

    for (let c = 0; c < cols; c++) {
      const reelX = startX + c * (symbolSize.width + reelSpacing);
      const reelContainer = this.add.container(reelX, startY);
      this.reelContainers.push(reelContainer);

      const currentReelSymbols = [];

      for (let i = 0; i < symbolsToCreatePerReel; i++) {
        const randomSymbolConfig = this.getRandomSymbolConfig();
        const symbolKey = `${this.slotId}_${randomSymbolConfig.asset.replace(/\..+$/, '')}`; // Construct key like "slot1_symbol_1"
        const symbolY = i * (symbolSize.height + symbolSpacing);

        const symbol = this.add.image(symbolSize.width / 2, symbolY + symbolSize.height / 2, symbolKey)
          .setDisplaySize(symbolSize.width, symbolSize.height)
          .setOrigin(0.5);
        
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
    const { rows, cols, startX, startY } = this.gridConfig;
    const { symbolSize } = this;
    const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;

    const maskWidth = cols * symbolSize.width + (cols - 1) * reelSpacing;
    // For multiway, the mask height should accommodate the maximum possible symbols on any reel,
    // but visually it's often tied to the initial display or a fixed max.
    // For now, use this.gridConfig.rows which is set to max(initialPanes) for multiway.
    const maskHeight = this.gridConfig.rows * symbolSize.height + (this.gridConfig.rows - 1) * symbolSpacing;

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
    const { rows, cols, startX, startY, width, height } = this.gridConfig;
    const { symbolSize } = this;
    const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;

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
      const x = startX + c * (symbolSize.width + reelSpacing) - reelSpacing / 2;
      borderGraphics.lineBetween(x, startY, x, startY + height);
    }

    // Inner horizontal lines (between rows)
    for (let r = 1; r < rows; r++) {
      const y = startY + r * (symbolSize.height + symbolSpacing) - symbolSpacing / 2;
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

  handleSpinResult(responseData) { // C
      console.log('GameScene received spin result:', responseData);
      this.lastSpinResponse = responseData;
      let transposedTargetGrid;

      if (this.isMultiwayGame) { // C.1
          this.targetPanesPerReel = responseData.result.panes_per_reel; // result from API is spin_result_data.spin_result
          this.gridConfig.currentActualMaxRows = Math.max(...this.targetPanesPerReel);
          // Backend sends multiway as { "panes_per_reel": [...], "symbols_grid": [[col0_syms], [col1_syms],...] }
          // symbols_grid is already effectively transposedTargetGrid
          transposedTargetGrid = responseData.result.symbols_grid;
      } else { // C.2
          this.targetPanesPerReel = Array(this.gridConfig.cols).fill(this.gridConfig.rows);
          const formattedGrid = this.formatSpinResult(responseData.result); // Expects [rows][cols] from API's "result" field for standard
          transposedTargetGrid = this.transposeMatrix(formattedGrid);
      }

      this.startReelSpinAnimation(transposedTargetGrid); // C.3
  }

  startReelSpinAnimation(transposedTargetGrid) {
      if (this.isSpinning) return;
      this.isSpinning = true;
      this.clearWinAnimations();
      EventBus.$emit('lineWinUpdate', { winAmount: 0, isScatter: false, ways: undefined });
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
    const { symbolSize } = this;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;
    const symbolHeightWithSpacing = symbolSize.height + symbolSpacing;
    const reelContainer = this.reelContainers[reelIndex];

    // totalReelHeight for wrapping based on max possible symbols
    const totalReelHeight = reelSymbols.length * symbolHeightWithSpacing;
    // visibleHeight based on *current* number of panes for this reel for stop positioning
    // This might need adjustment if the reel "shrinks" or "grows" visually during spin.
    // For now, assume it spins to fill its targetPanesPerReel space.
    const targetVisibleHeightThisReel = (this.targetPanesPerReel[reelIndex] || this.gridConfig.rows) * symbolHeightWithSpacing;


    const wraps = 3;
    const wrapDistance = wraps * totalReelHeight;
    const spinDuration = (baseDuration + reelIndex * REEL_STOP_DELAY); // Removed *1.5 for now
    const spinDistance = wrapDistance + targetVisibleHeightThisReel; // Spin relative to target height

    this.tweens.add({
        targets: reelContainer,
        y: `+=${spinDistance}`,
        duration: spinDuration,
        ease: 'Cubic.easeOut',
        onUpdate: () => {
            reelSymbols.forEach((symbol) => {
                const symbolWorldY = reelContainer.y + symbol.y;
                if (symbolWorldY > startY + targetVisibleHeightThisReel + symbolHeightWithSpacing) { // Adjust condition based on dynamic height?
                    symbol.y -= totalReelHeight;
                    const randomSymbolConfig = this.getRandomSymbolConfig();
                    symbol.setTexture(`${this.slotId}_${randomSymbolConfig.asset.replace(/\..+$/, '')}`);
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
                         symbol.setTexture(`${this.slotId}_${symbolConfig.asset.replace(/\..+$/, '')}`);
                    }
                    // Position based on landedPanesCount
                    symbol.y = i * symbolHeightWithSpacing + symbolSize.height / 2;
                    symbol.setVisible(true).setDepth(2); // Ensure visible and set depth
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
      console.log('GameScene: All reels stopped.');
      this.isSpinning = false;
      // EventBus.$emit('spinAnimationComplete', this.lastSpinResponse); // Emit after bonus check or normal win processing

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

              EventBus.$emit('spinAnimationComplete', this.lastSpinResponse); // Emit before pausing

              this.scene.launch('BonusHoldAndWinScene', dataForBonus);
              this.scene.pause('GameScene');
              this.scene.pause('UIScene');
              return; // Return early to prevent normal win processing
          }
      }

      EventBus.$emit('spinAnimationComplete', this.lastSpinResponse); // Emit if bonus not triggered

      if (this.lastSpinResponse && this.lastSpinResponse.win_amount > 0 && this.lastSpinResponse.winning_lines) {
          this.playSoundWin(this.lastSpinResponse.win_amount);
          this.displayWinningLines(this.lastSpinResponse.winning_lines, this.lastSpinResponse.win_amount);
      } else {
          // If no wins and no bonus, ensure UI is idle
          EventBus.$emit('uiSetIdle');
      }
  }

  displayWinningLines(winningLines, totalWinAmountSats) {
      if (!winningLines || winningLines.length === 0) {
           if (totalWinAmountSats > 0) {
                this.showTotalWinAmount(totalWinAmountSats);
                this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => this.clearWinAnimations());
           }
          return;
      }
      let currentLineIndex = 0;
      const displayNextLine = () => {
            this.clearWinAnimations(false);
            if (currentLineIndex >= winningLines.length) {
                 this.showTotalWinAmount(totalWinAmountSats);
                 if (this.paylineTimer) this.paylineTimer.remove();
                 this.paylineTimer = this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => this.clearWinAnimations());
                return;
            }
            const winData = winningLines[currentLineIndex]; // winData is the individual line/way/scatter object
            this.highlightWin(winData);
            this.showIndividualWinAmount(winData.win_amount_sats, winData); // Pass full winData
            currentLineIndex++;
            if (this.paylineTimer) this.paylineTimer.remove();
            this.paylineTimer = this.time.delayedCall(PAYLINE_SHOW_DURATION, displayNextLine);
        };
        displayNextLine();
  }

  highlightWin(winData) { // F
    this.paylineGraphics.clear();
    this.activeWinTweens.forEach(({symbol, tween}) => { // F.2 Reset existing
        if (tween && tween.isPlaying()) tween.stop();
        if (symbol && symbol.active) symbol.setScale(1).setDepth(2);
    });
    this.activeWinTweens = [];

    const animateSymbol = (col, row) => { // F.1 Helper
        const symbol = this.getSymbolAt(col, row);
        if (symbol && symbol.active) {
            symbol.setDepth(5);
            const existingTween = this.tweens.getTweensOf(symbol).find(tw => tw.callbacks && tw.callbacks.onYoyo);
            if(existingTween) existingTween.stop();

            const tween = this.tweens.add({
                targets: symbol,
                scale: { from: 1, to: 1.2 },
                ease: 'Sine.easeInOut',
                duration: SYMBOL_WIN_ANIM_DURATION,
                yoyo: true,
                repeat: -1,
            });
            this.activeWinTweens.push({ symbol, tween });
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
            this.paylineGraphics.lineStyle(5, lineColor, 0.9);
            this.paylineGraphics.fillStyle(lineColor, 0.8);
            for (let i = 0; i < linePoints.length - 1; i++) {
                this.paylineGraphics.lineBetween(linePoints[i].x, linePoints[i].y, linePoints[i + 1].x, linePoints[i + 1].y);
            }
            linePoints.forEach(p => this.paylineGraphics.fillCircle(p.x, p.y, 8));
        }
    }
}

  showIndividualWinAmount(amountSats, winData) { // G
      if (!this.currentWinDisplay) return;
      let textToShow = ''; // G.1
      if (this.isMultiwayGame && !winData.is_scatter) {
          const waysCount = winData.ways_count || winData.ways; // Support "ways" or "ways_count"
          textToShow = `Way Win: ${formatSatsToBtc(amountSats)} (${waysCount} Ways)`;
      } else if (winData.is_scatter || winData.type === 'scatter') { // Check type for robustness
          textToShow = `Scatter: ${formatSatsToBtc(amountSats)}`;
      } else { // Standard payline
          const lineIdText = typeof winData.line_id === 'string' ? winData.line_id : (winData.line_index !== undefined ? `Line ${winData.line_index + 1}` : 'Line Win');
          textToShow = `${lineIdText}: ${formatSatsToBtc(amountSats)}`;
      }

      this.currentWinDisplay.setText(textToShow).setAlpha(0).setVisible(true); // G.2
      this.tweens.killTweensOf(this.currentWinDisplay);
      this.tweens.add({
          targets: this.currentWinDisplay, alpha: 1, duration: 300, ease: 'Linear', yoyo: true,
          hold: PAYLINE_SHOW_DURATION - 600,
          onComplete: () => { if (this.currentWinDisplay) this.currentWinDisplay.setVisible(false); }
      });
      // G.3 Emit event
      EventBus.$emit('lineWinUpdate', {
          winAmount: amountSats,
          isScatter: (winData.is_scatter || winData.type === 'scatter'),
          ways: (this.isMultiwayGame && !(winData.is_scatter || winData.type === 'scatter')) ? (winData.ways_count || winData.ways) : undefined
      });
  }

   showTotalWinAmount(amountSats) {
        if (!this.currentWinDisplay) return;
        const amountBtc = formatSatsToBtc(amountSats);
        this.currentWinDisplay.setText(`Total Win: ${amountBtc}`) // Removed BTC suffix, formatter adds it
             .setAlpha(0).setVisible(true);
        EventBus.$emit('lineWinUpdate', { winAmount: amountSats, isScatter: false, ways: undefined }); // Total win update
        this.tweens.killTweensOf(this.currentWinDisplay);
        this.tweens.add({ targets: this.currentWinDisplay, alpha: 1, duration: 500, ease: 'Back.easeOut' });
    }

  clearWinAnimations(clearTotalWinText = true) { // H
    this.activeWinTweens.forEach(({symbol, tween}) => {
        if (tween && tween.isPlaying()) tween.stop();
        if (symbol && symbol.active) {
            symbol.setScale(1); // Reset scale
            symbol.setDepth(2); // H.1 Reset depth
        }
    });
    this.activeWinTweens = [];
    this.paylineGraphics?.clear();
    if (this.paylineTimer) {
        this.paylineTimer.remove(false);
        this.paylineTimer = null;
    }
    if (this.currentWinDisplay && clearTotalWinText) {
        this.tweens.killTweensOf(this.currentWinDisplay);
        this.currentWinDisplay.setVisible(false).setText('');
    }
  }

  // --- Helper Methods ---
   getSymbolAt(col, row) { // E
    if (this.isMultiwayGame) { // E.1
        if (!this.currentPanesPerReel || col < 0 || col >= this.gridConfig.cols || row < 0 || !this.currentPanesPerReel[col] || row >= this.currentPanesPerReel[col]) {
            return null;
        }
    } else { // E.1
        if (row < 0 || col < 0 || col >= this.gridConfig.cols || row >= this.gridConfig.rows) {
            return null;
        }
    }
    return this.symbolMap[`${col},${row}`]; // E.1
  }

  getSymbolWorldPosition(col, row) { // I
      const symbol = this.getSymbolAt(col, row); // I.1
      if (!symbol) return null; // I.1

      if (!symbol.parentContainer) {
            const { startX, startY } = this.gridConfig;
            const { symbolSize } = this;
            const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
            const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0; // Not typically used for Y per symbol in container
            return {
                x: startX + col * (symbolSize.width + reelSpacing) + symbolSize.width / 2,
                y: startY + row * (symbolSize.height + symbolSpacing) + symbolSize.height / 2 // This Y is relative to grid top for this symbol
            };
      }
       const symbolLocalX = symbol.x;
       const symbolLocalY = symbol.y;
       const containerX = symbol.parentContainer.x;
       const containerY = symbol.parentContainer.y;
       return { x: containerX + symbolLocalX, y: containerY + symbolLocalY };
  }

   getPaylineColor(lineIndexOrId) { // Accept ID too
        // If lineIndexOrId is a string (like "payline_1"), try to parse an index from it
        let numericIndex = 0;
        if (typeof lineIndexOrId === 'string' && lineIndexOrId.includes('_')) {
            numericIndex = parseInt(lineIndexOrId.split('_')[1], 10) -1; // "payline_1" -> 0
            if (isNaN(numericIndex)) numericIndex = 0;
        } else if (typeof lineIndexOrId === 'number') {
            numericIndex = lineIndexOrId;
        }

        const colors = [
            0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff,
            0x00ffff, 0xffa500, 0x800080, 0x008000, 0xff1493,
            0xff4500, 0x1e90ff, 0xadff2f, 0xda70d6, 0x8a2be2
        ];
        return colors[numericIndex % colors.length];
    }

  formatSpinResult(spinResult) {
    // For standard games, API sends "result" as [rows][cols]
    // For multiway, API sends "result.symbols_grid" as [cols][rows_variable]
    // This function is primarily for standard games to ensure [rows][cols]
    if (this.isMultiwayGame) {
        console.warn("formatSpinResult called for multiway game, this should not happen if backend structure is {spin_result: {symbols_grid: ...}}");
        return spinResult; // Should be already in [cols][var_rows] or handled by handleSpinResult
    }

    const { rows, cols } = this.gridConfig;
    // Check if it's already in the correct [rows][cols] format
    if (Array.isArray(spinResult) && spinResult.length === rows &&
        Array.isArray(spinResult[0]) && spinResult[0].length === cols) {
        return spinResult;
    }
    // If it's a flat array, attempt to reshape. This is less likely with current backend.
    if (Array.isArray(spinResult) && spinResult.length === rows * cols && !Array.isArray(spinResult[0])) {
        console.warn("Received spin result as a flat array, reshaping to [rows][cols].");
        const reshaped = [];
        for (let r = 0; r < rows; r++) {
           reshaped.push(spinResult.slice(r * cols, (r + 1) * cols));
        }
        return reshaped;
    }
    console.error("Received spin result in unexpected format for standard game:", spinResult);
    // Fallback: return as is or an empty grid of correct dimensions
    return Array(rows).fill(null).map(() => Array(cols).fill(1)); // Default to symbol '1'
  }

  transposeMatrix(matrix) {
    if (!matrix || matrix.length === 0 || !Array.isArray(matrix[0])) return [];
    return matrix[0].map((_, colIndex) => matrix.map(row => row[colIndex]));
  }

   playSound(key) {
        if (this.soundEnabled && key) {
            const sound = this.sound.get(key);
            if (sound) {
                sound.play();
            } else {
                console.warn(`Sound key "${key}" not found or loaded.`);
            }
        }
    }

    playSoundWin(winAmountSats) {
        // Play different sounds based on win size relative to bet?
        // Needs bet amount context here. For now, just play generic win sounds.
        // We need the bet amount that triggered this win. Get from lastSpinResponse?
        // const betAmount = this.lastSpinResponse?.bet_amount ?? 1; // Get bet if possible

        if (winAmountSats > 0) {
            // Simple logic: small vs large win sound
            if (winAmountSats > (this.lastSpinResponse?.bet_amount ?? 10) * 10) { // Example: win > 10x bet
                 this.playSound('winLarge');
            } else if (winAmountSats > (this.lastSpinResponse?.bet_amount ?? 10) * 3) { // Example: win > 3x bet
                this.playSound('winMedium');
            } else {
                this.playSound('winSmall');
            }
        }
    }

  handleBonusComplete(data) {
    console.log('GameScene: Bonus game complete.', data);
    this.scene.stop('BonusHoldAndWinScene');
    // Ensure GameScene and UIScene are properly resumed and brought to top if necessary
    this.scene.resume('GameScene');
    this.scene.resume('UIScene');
    this.scene.bringToTop('GameScene');
    this.scene.bringToTop('UIScene');


    const bonusWinAmount = data.winAmount || 0;

    if (bonusWinAmount > 0) {
        // Add bonus win to the session's total or display separately
        // For now, let's assume lastSpinResponse might not be the right place if other wins already processed.
        // We can directly update UI or manage a separate "bonus_win" field if API supports.

        // Update global balance (example, actual implementation might differ)
        EventBus.$emit('updateBalance', bonusWinAmount); // This is a client-side reflection.

        // Display the bonus win amount prominently
        // Option 1: Use existing currentWinDisplay
        this.currentWinDisplay.setText(`Bonus Win: ${formatSatsToBtc(bonusWinAmount)}`).setVisible(true).setAlpha(1);
        this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION * 1.5, () => { // Show longer
            this.currentWinDisplay.setVisible(false);
            EventBus.$emit('uiSetIdle'); // Set UI to idle after bonus win display
        });

        // Option 2: Emit to UIScene to handle special bonus win display
        EventBus.$emit('uiUpdate', { winAmount: bonusWinAmount, isBonusWin: true, isTotalWin: true });

        // Play a win sound for the bonus total
        this.playSoundWin(bonusWinAmount); // You might want a specific sound for "bonus_total_win"

    } else {
      // No win from bonus, just set UI to idle
      EventBus.$emit('uiSetIdle');
    }

    // Ensure isSpinning is false and UI controls are enabled
    this.isSpinning = false;
    // EventBus.$emit('enableSpinButton'); // Or let uiSetIdle handle this
  }

}

