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


export default class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });

    // Game state properties
    this.isSpinning = false;
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
    this.gridConfig = { rows: 3, cols: 5, startX: 0, startY: 0 }; // Default, loaded from config
  }

  // No preload here - assets are loaded in PreloadScene

  create() {
    console.log('GameScene: Create');
    this.gameConfig = this.registry.get('gameConfig');
    this.slotId = this.registry.get('slotId'); // Though slotId might not be directly used if gameConfig has all info
    this.turboSpinEnabled = this.registry.get('turboEnabled') ?? false;
    this.soundEnabled = this.registry.get('soundEnabled') ?? true;
    // User balance might be needed for some UI elements directly in GameScene, or passed to win displays
    // this.userBalance = this.registry.get('userBalance') ?? 0;
    this.eventBus = this.registry.get('eventBus'); // Get the event bus instance

    if (!this.eventBus) {
        console.warn("GameScene: EventBus not found in registry. Using fallback import.");
        this.eventBus = EventBus; // Fallback, assuming global import works
    }

    this.sound.mute = !this.soundEnabled;

    if (!this.gameConfig) { // slotId might not be strictly necessary if gameConfig is self-contained
        console.error("GameScene: Missing game configuration!");
        this.eventBus.emit('phaserError', 'Game initialization failed: Missing game configuration.');
        return;
    }

    this.symbolSize = this.gameConfig.reel?.symbolSize || { width: 100, height: 100 };
    const { rows, columns } = this.gameConfig.layout;
    const totalReelWidth = columns * this.symbolSize.width + (columns - 1) * (this.gameConfig.reel.reelSpacing || 0);
    const totalReelHeight = rows * this.symbolSize.height + (rows - 1) * (this.gameConfig.reel.symbolSpacing || 0);

    // Calculate starting position for the grid (centered with top margin)
    const configStartX = this.gameConfig.reel.position?.x ?? (this.cameras.main.width - totalReelWidth) / 2;
    const configStartY = this.gameConfig.reel.position?.y ?? 100; // Default top margin

    this.gridConfig = {
        rows,
        cols: columns,
        startX: configStartX,
        startY: configStartY,
        width: totalReelWidth,
        height: totalReelHeight
    };


    this.createBackground();
    this.createReels(); // Creates reel containers and initial symbols
    this.createMask(); // Masks symbols outside the visible grid area
    this.createBorders(); // Adds visual borders around reels/grid
    this.createParticles(); // Creates particle emitter for win effects
    this.createPaylineGraphics(); // Graphics object for drawing lines
    this.createWinDisplay(); // Text object for showing win amounts

    // --- Event Listeners from Vue ---
    this.eventBus.on('startSpinAnimationCommand', this.startReelSpinAnimation, this);
    this.eventBus.on('updateSettingsInPhaser', (settings) => {
        if (settings.soundEnabled !== undefined) {
            this.soundEnabled = settings.soundEnabled;
            this.sound.mute = !this.soundEnabled;
            console.log('GameScene: Sound setting updated from Vue to', this.soundEnabled ? 'ON' : 'OFF');
        }
        if (settings.turboEnabled !== undefined) {
            this.turboSpinEnabled = settings.turboEnabled;
            console.log('GameScene: Turbo spin updated from Vue to', this.turboSpinEnabled);
        }
    });

    // Listener for settings changes from SettingsModalScene (if it emits directly to Phaser scenes)
    // This might be redundant if SettingsModalScene emits to Vue, and Vue emits updateSettingsInPhaser
    // For now, we assume Vue is the central dispatcher for settings.
    // this.scene.get('SettingsModalScene').events.on('settingsChanged', (settings) => {
    //    this.soundEnabled = settings.sound;
    //    this.sound.mute = !this.soundEnabled;
    //    this.turboSpinEnabled = settings.turbo;
    // });


    console.log('GameScene: Ready.');
    // Notify Vue that Phaser GameScene is ready (if Slot.vue needs to know)
    // this.eventBus.emit('phaserGameSceneReady');
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

    const { rows, cols, startX, startY } = this.gridConfig;
    const { symbolSize } = this;
    const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0; // Vertical spacing (usually 0)

    // Number of symbols per reel: visible rows + buffer top/bottom (e.g., 1 top, 1 bottom)
    const totalSymbolsPerReel = rows + 2; // Adjust buffer as needed for smooth wrapping

    for (let c = 0; c < cols; c++) {
      const reelX = startX + c * (symbolSize.width + reelSpacing);
      const reelContainer = this.add.container(reelX, startY);
      this.reelContainers.push(reelContainer);

      const currentReelSymbols = [];
      const availableSymbolIds = this.gameConfig.symbols.map(s => s.id); // Get actual symbol IDs

      for (let i = 0; i < totalSymbolsPerReel; i++) {
        // Select a random symbol ID from the actual available symbols
        const randomSymbolId = Phaser.Utils.Array.GetRandom(availableSymbolIds);
        const symbolY = i * (symbolSize.height + symbolSpacing);

        const symbol = this.add.image(symbolSize.width / 2, symbolY + symbolSize.height / 2, `symbol_${randomSymbolId}`)
          .setDisplaySize(symbolSize.width, symbolSize.height)
          .setOrigin(0.5);

        reelContainer.add(symbol);
        currentReelSymbols.push(symbol);

        // Map visible symbols for easy access [col, row]
        if (i >= 0 && i < rows) { // Map the initially visible symbols
           this.symbolMap[`${c},${i}`] = symbol;
           symbol.setData('gridPosition', { col: c, row: i }); // Store grid position on symbol
        }
      }
      this.reels.push(currentReelSymbols); // Store array of symbols for this reel
    }
  }

  createMask() {
    const { rows, cols, startX, startY } = this.gridConfig;
    const { symbolSize } = this;
    const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;

    const maskWidth = cols * symbolSize.width + (cols - 1) * reelSpacing;
    const maskHeight = rows * symbolSize.height + (rows - 1) * symbolSpacing;

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

  // This method is triggered by an event from Slot.vue, e.g., 'startSpinAnimationCommand'
  // It receives the final grid and win data.
  startReelSpinAnimation({ finalGrid, winningLinesData, totalWinAmountSats }) {
    if (this.isSpinning) {
        console.warn("GameScene: Already spinning, ignoring new spin command.");
        return;
    }
    this.isSpinning = true;
    this.clearWinAnimations();

    // Reset win display in UI Scene
    this.eventBus.emit('lineWinUpdate', { winAmount: 0, isScatter: false });

    this.playSound(this.gameConfig.sound?.spinEffect || 'spin');

    const spinReelDuration = this.turboSpinEnabled ? REEL_SPIN_DURATION_TURBO : REEL_SPIN_DURATION_BASE;
    const numReels = this.gridConfig.cols;
    let completedReels = 0;

    // Ensure finalGrid is in [cols][rows] format for easier processing per reel
    const transposedFinalGrid = this.transposeMatrix(finalGrid); // if finalGrid is [rows][cols]

    this.reels.forEach((reelSymbols, reelIndex) => {
      this.time.delayedCall(reelIndex * REEL_START_DELAY, () => {
        this.spinReel(
          reelIndex,
          reelSymbols,
          spinReelDuration,
          transposedFinalGrid[reelIndex], // Pass the target symbols for this specific reel
          () => { // onCompleteCallback for this individual reel
            completedReels++;
            this.playSound(this.gameConfig.sound?.reelStopEffect || 'reelStop');
            if (completedReels === numReels) {
              this.onAllReelsStopped(winningLinesData, totalWinAmountSats);
            }
          }
        );
      });
    });
  }

  spinReel(reelIndex, reelSymbols, baseDuration, targetSymbols, onCompleteCallback) {
    const { rows, startY } = this.gridConfig;
    const { symbolSize } = this;
    const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;
    const symbolHeightWithSpacing = symbolSize.height + symbolSpacing;
    const reelContainer = this.reelContainers[reelIndex];

    const totalReelHeight = reelSymbols.length * symbolHeightWithSpacing;
    const visibleHeight = rows * symbolHeightWithSpacing;

    // Calculate spin distance: multiple full wraps + stopping position
    const wraps = 3; // Increased number of wraps for longer animation
    const wrapDistance = wraps * totalReelHeight;

    // Extend the spin duration for a smoother experience
    const spinDuration = (baseDuration + reelIndex * REEL_STOP_DELAY) * 1.5; // 50% longer
    const spinDistance = wrapDistance + visibleHeight; // Spin at least one visible height further

    // Prepare the final symbols array for smooth transition
    const finalSymbols = [];
    for (let i = 0; i < reelSymbols.length; i++) {
        if (i < rows) {
            finalSymbols.push(targetSymbols[i]);
        } else {
            // For buffer symbols, use random ones
            finalSymbols.push(Phaser.Math.Between(1, this.gameConfig.symbol_count));
        }
    }

    // --- Main Spin Tween ---
    this.tweens.add({
        targets: reelContainer,
        y: `+=${spinDistance}`, // Move container down
        duration: spinDuration,
        ease: 'Cubic.easeOut', // Start fast, slow down at the end
        onUpdate: (tween) => {
            // --- Symbol Wrapping Logic ---
            reelSymbols.forEach((symbol, symbolIndex) => {
                // Calculate symbol's world Y position
                const symbolWorldY = reelContainer.y + symbol.y;
                
                // If symbol center goes below the visible area's estimated bottom + buffer
                if (symbolWorldY > startY + visibleHeight + symbolHeightWithSpacing) {
                    // Wrap symbol from bottom to top
                    symbol.y -= totalReelHeight;
                    
                    // Always use a random symbol during the spinning phase
                    // This creates a more uniform blur effect
                    const randomSymbolId = Phaser.Math.Between(1, this.gameConfig.symbol_count);
                    symbol.setTexture(`symbol_${randomSymbolId}`);
                }
            });
            
            // In the last 10% of the animation, slow down the visual updates
            // This creates a smoother transition to the final state
            if (tween.progress > 0.9) {
                // Reduce the frequency of texture changes as we approach the end
                if (Math.random() > 0.7) {
                    // Only update some symbols occasionally
                    const randomIndex = Math.floor(Math.random() * reelSymbols.length);
                    if (randomIndex < reelSymbols.length) {
                        const symbol = reelSymbols[randomIndex];
                        const randomSymbolId = Phaser.Math.Between(1, this.gameConfig.symbol_count);
                        symbol.setTexture(`symbol_${randomSymbolId}`);
                    }
                }
            }
        },
        onComplete: () => {
            // --- Smooth Transition to Final Position ---
            
            // First, set all symbols to their exact final positions
            reelSymbols.forEach((symbol, index) => {
                // Set exact final positions without randomness
                symbol.y = index * symbolHeightWithSpacing + symbolSize.height / 2;
                
                // Set the final textures
                if (index < rows) {
                    symbol.setTexture(`symbol_${finalSymbols[index]}`);
                } else {
                    const randomSymbolId = Phaser.Math.Between(1, this.gameConfig.symbol_count);
                    symbol.setTexture(`symbol_${randomSymbolId}`);
                }
                
                // Update the symbolMap for the final visible state
                if (index < rows) {
                    this.symbolMap[`${reelIndex},${index}`] = symbol;
                    symbol.setData('gridPosition', { col: reelIndex, row: index });
                }
            });
            
            // Position the container at the exact final position
            reelContainer.y = startY;
            
            // No additional animations - just call the callback
            onCompleteCallback();
        }
    });
}


  onAllReelsStopped(winningLinesData, totalWinAmountSats) {
    console.log('GameScene: All reels stopped.');
    this.isSpinning = false;

    // Notify Vue that the visual part of the spin is done.
    // Slot.vue might use this to re-enable UI elements or perform other actions.
    this.eventBus.emit('visualSpinComplete');
      
    if (totalWinAmountSats > 0 && winningLinesData) {
      this.playSoundWin(totalWinAmountSats); // Play appropriate win sound
      this.displayWinningLines(winningLinesData, totalWinAmountSats);
    } else {
      // No win, ready for next spin
      // Optionally, inform UI that no win occurred if needed for specific UI states
      // this.eventBus.emit('noWin');
    }
  }

  displayWinningLines(winningLinesData, totalWinAmountSats) {
    if (!winningLinesData || winningLinesData.length === 0) {
        if (totalWinAmountSats > 0) { // Possible for scatter wins not detailed in lines
            this.showTotalWinAmount(totalWinAmountSats);
            this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => {
                this.clearWinAnimations();
            });
        }
        return;
    }

    let currentLineIndex = 0;
      const displayNextLine = () => {
            this.clearWinAnimations(false); // Clear previous line/symbol highlights, but keep total win if shown

            if (currentLineIndex >= winningLines.length) {
                 // Finished showing all lines, show total win amount prominently
                 this.showTotalWinAmount(totalWinAmountSats);
                 // Set timer to clear everything after a delay
                 if (this.paylineTimer) this.paylineTimer.remove();
                 this.paylineTimer = this.time.delayedCall(TOTAL_WIN_DISPLAY_DURATION, () => {
                    this.clearWinAnimations();
                });
                return;
            }

            const winLine = winningLines[currentLineIndex];
            this.highlightWin(winLine); // Highlight symbols and draw line

            // Show amount for this specific line (optional)
            this.showLineWinAmount(winLine.win_amount);

            currentLineIndex++;

            // Schedule the next line display
             if (this.paylineTimer) this.paylineTimer.remove();
            this.paylineTimer = this.time.delayedCall(PAYLINE_SHOW_DURATION, displayNextLine);
        };

        // Start the display cycle
        displayNextLine();
  }

 highlightWin(winLine) {
   this.paylineGraphics.clear(); // Clear previous lines
   const { symbolSize } = this;
   const { startX, startY } = this.gridConfig;
   const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
   const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;

   // Store whether this is a scatter win for later use
   this.isScatterWin = winLine.line_index === 'scatter';

   // 1. Animate Winning Symbols
   winLine.positions.forEach(([row, col]) => {
       const symbol = this.getSymbolAt(col, row);
       if (symbol) {
           // Bring symbol slightly forward
            symbol.setDepth(5);

           // Add a scale/pulse animation
           const tween = this.tweens.add({
               targets: symbol,
               duration: SYMBOL_WIN_ANIM_DURATION,
               ease: 'Sine.easeInOut',
               yoyo: true, // Scale back down
               repeat: -1, // Loop until cleared
                // delay: index * 50 // Optional stagger
           });
           this.activeWinTweens.push({symbol, tween}); // Store tween to stop later

            // Optional: Add particle burst at symbol location
            const worldPos = this.getSymbolWorldPosition(col, row);
            this.winEmitter?.explode(10, worldPos.x, worldPos.y); // Emit particles
       }
   });

   // 2. Draw Payline (if not a scatter win)
   if (!this.isScatterWin) {
       const paylineConfig = this.gameConfig.paylines.find(p => p.id === winLine.line_index);
       if (paylineConfig) {
            const paylineDef = this.gameConfig.layout.paylines.find(p => p.id === winLine.line_id); // line_id from backend
            if (paylineDef) { // Ensure payline definition exists
                const lineColor = this.getPaylineColor(paylineDef.id); // Use paylineDef.id or winLine.line_id
                this.paylineGraphics.lineStyle(5, lineColor, 0.9);
                this.paylineGraphics.fillStyle(lineColor, 0.8);

                const linePoints = [];
                // Draw based on the actual winning positions provided
                winLine.positions.forEach(([row, col]) => { // Assuming positions are [row, col] from backend
                    const pos = this.getSymbolWorldPosition(col, row); // Need to ensure getSymbolAt understands this
                    linePoints.push(new Phaser.Math.Vector2(pos.x, pos.y));
                    this.paylineGraphics.fillCircle(pos.x, pos.y, 8);
                });

                if (linePoints.length > 1) {
                    for (let i = 0; i < linePoints.length - 1; i++) {
                        this.paylineGraphics.lineBetween(linePoints[i].x, linePoints[i].y, linePoints[i+1].x, linePoints[i+1].y);
                    }
                }
            } else {
                console.warn(`Payline definition not found for ID: ${winLine.line_id}`);
            }
       }
   }
}


  showLineWinAmount(amountSats) {
      if (!this.currentWinDisplay) return;
      const amountBtc = formatSatsToBtc(amountSats); // Format for display
      
      // Use different text for scatter wins vs line wins
      const winType = this.isScatterWin ? 'Scatter Win' : 'Line Win';
      this.currentWinDisplay.setText(`${winType}: ${amountBtc} BTC`)
          .setAlpha(0)
          .setVisible(true);

      // Emit event to update the UI Scene with this line win
      // Include the win type (scatter or line) in the event data
      EventBus.$emit('lineWinUpdate', {
          winAmount: amountSats,
          isScatter: this.isScatterWin
      });

       // Fade in/out effect
       this.tweens.add({
            targets: this.currentWinDisplay,
            alpha: 1,
            duration: 300,
            ease: 'Linear',
            yoyo: true, // Fade out again
            hold: PAYLINE_SHOW_DURATION - 600, // Hold visible for most of the line duration
            onComplete: () => {
                 if(this.currentWinDisplay) this.currentWinDisplay.setVisible(false);
            }
        });
  }

   showTotalWinAmount(amountSats) {
        if (!this.currentWinDisplay) return;
        const amountBtc = formatSatsToBtc(amountSats);
        this.currentWinDisplay.setText(`Total Win: ${amountBtc} BTC`)
             .setAlpha(0)
             .setVisible(true); // Make total win larger initially

        // Emit event to update the UI Scene with the total win
        // For total win, we don't use the scatter flag since it's the sum of all wins
        EventBus.$emit('lineWinUpdate', {
            winAmount: amountSats,
            isScatter: false // Total win is not a scatter win
        });

        // Clear any existing tweens on this text
         this.tweens.killTweensOf(this.currentWinDisplay);

        // Scale down and fade in, then hold
        this.tweens.add({
            targets: this.currentWinDisplay,
            alpha: 1,
            duration: 500,
            ease: 'Back.easeOut' // Add a slight bounce effect
        });
    }

  clearWinAnimations(clearTotalWinText = true) {
     // Stop and remove symbol animations/tweens
    this.activeWinTweens.forEach(({symbol, tween}) => {
        if (tween && tween.isPlaying()) {
            tween.stop();
        }
         if (symbol && symbol.active) { // Check if symbol still exists
             //symbol.setScale(1); // Reset scale
             symbol.setDepth(0); // Reset depth
         }
    });
    this.activeWinTweens = [];

    // Clear drawn paylines
    this.paylineGraphics?.clear();

    // Stop particle emitter? (It might stop automatically if frequency is -1)
    // this.winEmitter?.stop();

    // Clear timers
     if (this.paylineTimer) {
         this.paylineTimer.remove(false); // Don't run callback on removal
         this.paylineTimer = null;
     }

    // Hide win amount text
     if (this.currentWinDisplay && clearTotalWinText) {
         this.tweens.killTweensOf(this.currentWinDisplay); // Stop any active tweens
         this.currentWinDisplay.setVisible(false).setText('');
     }
  }

  // --- Helper Methods ---
   getSymbolAt(col, row) {
    // Ensure indices are within bounds
    if (col < 0 || col >= this.gridConfig.cols || row < 0 || row >= this.gridConfig.rows) {
        return null;
    }
    return this.symbolMap[`${col},${row}`];
  }

  getSymbolWorldPosition(col, row) {
      const symbol = this.getSymbolAt(col, row);
      if (!symbol || !symbol.parentContainer) {
          // Fallback calculation if symbol not found or structure changed
            const { startX, startY } = this.gridConfig;
            const { symbolSize } = this;
            const reelSpacing = this.gameConfig.reel.reelSpacing || 0;
            const symbolSpacing = this.gameConfig.reel.symbolSpacing || 0;
            return {
                x: startX + col * (symbolSize.width + reelSpacing) + symbolSize.width / 2,
                y: startY + row * (symbolSize.height + symbolSpacing) + symbolSize.height / 2
            };
      }
      // Get position relative to the container, then add container's position
       const symbolLocalX = symbol.x;
       const symbolLocalY = symbol.y;
       const containerX = symbol.parentContainer.x;
       const containerY = symbol.parentContainer.y;

       return { x: containerX + symbolLocalX, y: containerY + symbolLocalY };
  }

   getPaylineColor(lineIndex) {
        const colors = [
            0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff, // Red, Green, Blue, Yellow, Magenta
            0x00ffff, 0xffa500, 0x800080, 0x008000, 0xff1493, // Cyan, Orange, Purple, DarkGreen, DeepPink
            // Add more colors if more than 10 paylines
            0xff4500, 0x1e90ff, 0xadff2f, 0xda70d6, 0x8a2be2
        ];
        return colors[lineIndex % colors.length];
    }

  formatSpinResult(spinResult) {
    // Ensure result is in [rows][cols] format
    const { rows, cols } = this.gridConfig;
    if (!Array.isArray(spinResult) || spinResult.length !== rows || !Array.isArray(spinResult[0]) || spinResult[0].length !== cols) {
        console.warn("Received spin result in unexpected format, attempting to reshape.", spinResult);
        // Add reshaping logic if backend might send flattened array, otherwise return as is or error
        // Example for flattened:
        // const reshaped = [];
        // for (let r = 0; r < rows; r++) {
        //    reshaped.push(spinResult.slice(r * cols, (r + 1) * cols));
        // }
        // return reshaped;
        return spinResult; // Assuming format is already correct
    }
    return spinResult;
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

}

