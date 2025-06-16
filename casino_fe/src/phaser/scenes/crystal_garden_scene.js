import Phaser from 'phaser';
import api from '@/services/api'; // Import the actual API service

// Mock API service is now removed.

export default class CrystalGardenScene extends Phaser.Scene {
    // HARDCODED_SEEDS can be fetched from a config endpoint or be part of game data if dynamic
    // For now, keeping it if UI relies on it directly, but ideally this comes from backend.
    // Let's assume the backend will provide seed info if needed, or it's part of game assets.
    // For this task, we'll assume the scene might still use this for UI display if backend doesn't list all buyable seeds.
    // However, the `buyCrystalSeed` API only needs an ID.
    // IDs must match those in the database seeding migration.
    // However, the `buyCrystalSeed` API only needs an ID.
    // IDs must match those in the database seeding migration.
    static HARDCODED_SEEDS = [
        { id: 1, name: 'Common Rock Seed', cost: 5, asset_key: 'seed_rock_gfx', description: "Grows dull, simple crystals." },
        { id: 2, name: 'Geode Seed', cost: 20, asset_key: 'seed_geode_gfx', description: "May contain beautiful crystals." },
        { id: 3, name: 'Star Shard Seed', cost: 50, asset_key: 'seed_star_gfx', description: "Grows brilliant crystals." },
        { id: 4, name: 'Shadowvein Seed', cost: 75, asset_key: 'seed_shadow_gfx', description: "Pulses with mysterious energy." },
        { id: 5, name: 'Sunstone Seed', cost: 60, asset_key: 'seed_sun_gfx', description: "Radiates gentle warmth." },
        { id: 6, name: 'Rivergem Seed', cost: 30, asset_key: 'seed_river_gfx', description: "Yields serene clarity." },
        { id: 7, name: 'Heartwood Seed', cost: 40, asset_key: 'seed_heart_gfx', description: "Strong and resilient crystals." }
        // Not including 'Basic Test Seed' in the shop UI.
    ];

    static HARDCODED_POWERUPS = [
        { type: 'fertilizer', name: 'Fertilizer', cost: 10, asset_key: 'powerup_fertilizer_gfx', description: "Speeds up growth or boosts size."},
        { type: 'moon_glow', name: 'Moon Glow', cost: 15, asset_key: 'powerup_moonglow_gfx', description: "Enhances clarity & special traits."},
        { type: 'azure_dye', name: 'Azure Dye', cost: 25, asset_key: 'powerup_azure_dye_gfx', description: "Guarantees a blue crystal."},
        { type: 'clarity_elixir', name: 'Clarity Elixir', cost: 30, asset_key: 'powerup_clarity_elixir_gfx', description: "Ensures at least 'Clear' clarity."},
        { type: 'sparkle_infusion', name: 'Sparkle Infusion', cost: 40, asset_key: 'powerup_sparkle_infusion_gfx', description: "Greatly boosts rare special type chance."}
    ];

    constructor() {
        super({ key: 'CrystalGardenScene' });
        this.gardenGrid = [];
        this.gridSize = { rows: 5, cols: 5 };
        this.cellSize = 80;
        this.gridOffset = { x: 50, y: 80 };
        this.playerBalance = 0;
        this.seedsAvailable = CrystalGardenScene.HARDCODED_SEEDS;
        this.selectedSeed = null;
        this.playerGardenId = null;
        this.uiElements = new Phaser.GameObjects.Group(this); // Group for UI elements that might need refresh
        this.statusClearTimer = null; // Timer for clearing success messages

        // UI layout constants
        this.UI_PANEL_WIDTH = 280;
        this.UI_PANEL_PADDING = 10;
        this.UI_SECTION_SPACING = 15;
        this.BUTTON_HEIGHT = 30;
        this.TEXT_STYLE = { fontSize: '14px', fill: '#fff' };
        this.TITLE_STYLE = { fontSize: '16px', fill: '#fff', fontStyle: 'bold' };
        this.BUTTON_TEXT_STYLE = { fontSize: '14px', fill: '#000' };
        this.BUTTON_COLOR = 0x00ff00;
        this.BUTTON_HOVER_COLOR = 0x00cc00;

        this.flowerInfoPanel = null; // To hold the flower info display elements
        this.codexPanel = null; // To hold the codex display elements

        this.isSfxEnabled = true;
        this.isBgmEnabled = true;
        this.currentBgmKey = null; // To keep track of background music for logging
    }

    // --- Sound Helper Methods ---
    playSound(soundKey, volume = 1) {
        if (this.isSfxEnabled) {
            // In a real implementation: this.sound.play(soundKey, { volume });
            console.log(`SFX: Play ${soundKey} (vol: ${volume})`);
        }
    }

    playBackgroundMusic(musicKey, volume = 0.3) {
        if (this.isBgmEnabled) {
            // In a real implementation:
            // if (this.currentBgm) this.currentBgm.stop();
            // this.currentBgm = this.sound.add(musicKey, { loop: true, volume });
            // this.currentBgm.play();
            this.currentBgmKey = musicKey; // Store for logging purposes
            console.log(`BGM: Start ${musicKey} (vol: ${volume}, loop: true)`);
        } else {
            this.stopBackgroundMusic(); // Ensure it's stopped if BGM gets disabled
        }
    }

    stopBackgroundMusic() {
        // In a real implementation: if (this.currentBgm) this.currentBgm.stop();
        if (this.currentBgmKey) {
            console.log(`BGM: Stop ${this.currentBgmKey}`);
            this.currentBgmKey = null;
        }
    }

    toggleSfx() {
        this.isSfxEnabled = !this.isSfxEnabled;
        this.playSound('sfx_ui_click'); // Click sound for the button itself
        console.log(`SFX ${this.isSfxEnabled ? 'Enabled' : 'Disabled'}`);
        // Update button text - will be handled where button is created/managed
        this.updateMuteButtonTexts();
    }

    toggleBgm() {
        this.isBgmEnabled = !this.isBgmEnabled;
        if (this.isBgmEnabled) {
            this.playBackgroundMusic('bgm_crystal_garden'); // Or whatever BGM was playing
        } else {
            this.stopBackgroundMusic();
        }
        this.playSound('sfx_ui_click');
        console.log(`BGM ${this.isBgmEnabled ? 'Enabled' : 'Disabled'}`);
        // Update button text
        this.updateMuteButtonTexts();
    }
    // --- End Sound Helper Methods ---


    preload() {
        // Graphics objects will be used for placeholders, so no specific image loading here is critical
        // for basic functionality. Actual image assets would be added here.
        console.log("CrystalGardenScene: preload");
        // this.load.image('flower_bloom_generic', 'assets/images/flower_bloom_generic.png');
        // this.load.image('seed_basic', 'assets/images/seed_basic.png'); // Will be replaced by graphics
        // this.load.image('flower_sprout', 'assets/images/flower_sprout.png'); // Will be replaced by graphics
    }

    createPlaceholderTexture(name, width, height, color, text = null, textColor = '#ffffff') {
        const gfx = this.make.graphics();
        gfx.fillStyle(color);
        gfx.fillRect(0, 0, width, height);
        if (text) {
            const label = this.make.text({
                x: width / 2,
                y: height / 2,
                text: text,
                style: {
                    font: '10px Arial',
                    fill: textColor,
                    align: 'center'
                },
                origin: 0.5
            });
            gfx.renderTexture(label.texture, null, (width - label.width)/2, (height-label.height)/2); // Draw text onto graphics
            label.destroy();
        }
        gfx.generateTexture(name, width, height);
        gfx.destroy();
    }


    create() {
        this.createPlaceholderTexture('gfx_plot_empty', this.cellSize -2, this.cellSize -2, 0x5B4037); // Brown
        this.createPlaceholderTexture('gfx_seed_planted', this.cellSize -2, this.cellSize -2, 0x4A3227, 'S'); // Darker Brown with S
        this.createPlaceholderTexture('gfx_sprout', this.cellSize -2, this.cellSize -2, 0x556B2F, 'V'); // Olive Green with V
        this.createPlaceholderTexture('gfx_flower_blooming', this.cellSize -2, this.cellSize -2, 0xFFB6C1, 'B'); // Light Pink with B
        this.createPlaceholderTexture('particle_star', 5, 5, 0xffffff); // Simple white particle

        // Create placeholder textures for all seeds defined in HARDCODED_SEEDS
        CrystalGardenScene.HARDCODED_SEEDS.forEach(seed => {
            // Use a more deterministic color generation or pre-defined colors if desired
            const char = seed.name.substring(0,1).toUpperCase();
            let color = Phaser.Display.Color.RandomRGB(50, 200).color; // Keep random for now
            if (seed.asset_key === 'seed_rock_gfx') color = 0x8B4513; // Brown
            else if (seed.asset_key === 'seed_geode_gfx') color = 0xDA70D6; // Orchid
            else if (seed.asset_key === 'seed_star_gfx') color = 0xFFD700; // Gold
            else if (seed.asset_key === 'seed_shadow_gfx') color = 0x483D8B; // DarkSlateBlue
            else if (seed.asset_key === 'seed_sun_gfx') color = 0xFFA500; // Orange
            else if (seed.asset_key === 'seed_river_gfx') color = 0x40E0D0; // Turquoise
            else if (seed.asset_key === 'seed_heart_gfx') color = 0x228B22; // ForestGreen

            this.createPlaceholderTexture(seed.asset_key, 20, 20, color, char);
        });

        // Create placeholder textures for power-ups
        CrystalGardenScene.HARDCODED_POWERUPS.forEach(powerUp => {
            const char = powerUp.name.substring(0,1).toUpperCase();
            let color = Phaser.Display.Color.RandomRGB(100, 255).color;
            if (powerUp.asset_key === 'powerup_fertilizer_gfx') color = 0x008000; // Green
            else if (powerUp.asset_key === 'powerup_moonglow_gfx') color = 0xE6E6FA; // Lavender
            else if (powerUp.asset_key === 'powerup_azure_dye_gfx') color = 0x007FFF; // Azure
            else if (powerUp.asset_key === 'powerup_clarity_elixir_gfx') color = 0xADD8E6; // LightBlue
            else if (powerUp.asset_key === 'powerup_sparkle_infusion_gfx') color = 0xFFD700; // Gold
            this.createPlaceholderTexture(powerUp.asset_key, 20, 20, color, char);
        });


        this.cameras.main.setBackgroundColor('#2E7D32');
        this.add.text(this.cameras.main.width / 2, 30, 'Crystal Garden', {
            fontSize: '28px', fill: '#fff', fontStyle: 'bold'
        }).setOrigin(0.5);

        this.initGardenGrid();
        this.createMainUIPanel();
        this.createUIContents();
        this.fetchInitialData();
        this.playBackgroundMusic('bgm_crystal_garden');
    }

    initGardenGrid() {
        for (let row = 0; row < this.gridSize.rows; row++) {
            this.gardenGrid[row] = [];
            for (let col = 0; col < this.gridSize.cols; col++) {
                const x = this.gridOffset.x + col * this.cellSize + this.cellSize / 2;
                const y = this.gridOffset.y + row * this.cellSize + this.cellSize / 2;
                const plotSprite = this.add.sprite(x, y, 'gfx_plot_empty').setInteractive();
                plotSprite.setData('plotRow', row);
                plotSprite.setData('plotCol', col);
                plotSprite.on('pointerdown', () => this.onPlotClicked(plotSprite));

                // Hover effects for plots
                plotSprite.on('pointerover', () => {
                    if (!this.gardenGrid[row][col].flowerData && this.selectedSeed) { // Empty and seed selected
                        this.tweens.add({ targets: plotSprite, scale: 1.05, duration: 150, ease: 'Power1' });
                    }
                    plotSprite.setAlpha(0.8);
                });
                plotSprite.on('pointerout', () => {
                    if (!this.gardenGrid[row][col].flowerData && this.selectedSeed) {
                         this.tweens.add({ targets: plotSprite, scale: 1, duration: 150, ease: 'Power1' });
                    }
                    plotSprite.setAlpha(1);
                });

                this.gardenGrid[row][col] = { sprite: plotSprite, flowerData: null, row: row, col: col };
            }
        }
    }

    createMainUIPanel() {
        this.uiPanelX = this.gridOffset.x + (this.gridSize.cols * this.cellSize) + 20;
        const panelHeight = this.cameras.main.height - this.gridOffset.y - 20;

        // Add a background for the UI panel
        const uiPanelBg = this.add.graphics();
        uiPanelBg.fillStyle(0x000000, 0.5); // Semi-transparent black
        uiPanelBg.fillRect(this.uiPanelX - this.UI_PANEL_PADDING, this.gridOffset.y - this.UI_PANEL_PADDING, this.UI_PANEL_WIDTH, panelHeight);
        this.uiElements.add(uiPanelBg); // Add to group so it's managed
    }

    createUIContents() {
        // Clear only elements previously added by this function if re-called
        // For now, assuming createUI is called once in create() after panel background
        // If this needs to be dynamic, manage sub-groups for each section.
        this.uiElements.clear(true, true); // Clear previous elements if any (except panel bg if not in group)
        // Re-add the panel background if it was cleared
        if (this.uiPanelX) this.createMainUIPanel();


        let currentY = this.gridOffset.y;

        currentY = this.createBalanceDisplay(this.uiPanelX, currentY);
        currentY = this.createSeedShop(this.uiPanelX, currentY);
        currentY = this.createSelectedSeedDisplay(this.uiPanelX, currentY);
        currentY = this.createMainActionButtons(this.uiPanelX, currentY);

        // Flower Info Panel (initially hidden)
        this.flowerInfoPanel = this.add.container(this.uiPanelX, this.gridOffset.y).setVisible(false);
        this.uiElements.add(this.flowerInfoPanel); // Manage with main UI elements

        // Codex Panel (initially hidden)
        this.codexPanel = this.add.container(this.cameras.main.width / 2, this.cameras.main.height / 2).setVisible(false).setDepth(100);
        this.uiElements.add(this.codexPanel); // Manage with main UI elements

        currentY = this.createStatusDisplay(this.uiPanelX, this.cameras.main.height - 50); // Position at bottom of panel
    }

    createBalanceDisplay(x, y) {
        this.balanceText = this.add.text(x, y, `Balance: ${this.playerBalance}G`, {
            ...this.TEXT_STYLE, backgroundColor: '#00000099', padding: { x: 5, y: 3 }, fixedWidth: this.UI_PANEL_WIDTH - (2 * this.UI_PANEL_PADDING)
        });
        this.uiElements.add(this.balanceText);
        return y + this.balanceText.height + this.UI_SECTION_SPACING;
    }

    createSeedShop(x, y) {
        this.uiElements.add(this.add.text(x, y, 'Seed Shop', this.TITLE_STYLE));
        y += 25;

        this.seedsAvailable.forEach(seed => {
            const seedIcon = this.add.image(x + 15, y + 10, seed.asset_key);
            const seedNameText = this.add.text(x + 40, y, `${seed.name} (${seed.cost}G)`, this.TEXT_STYLE);
            const seedDescText = this.add.text(x + 40, y + 18, seed.description, { ...this.TEXT_STYLE, fontSize: '10px', wordWrap: { width: this.UI_PANEL_WIDTH - 60 } });

            const buyButton = this.createStyledButton(x + (this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 80)/2 , y + 40, 'Select', () => this.onBuySeedClicked(seed), 80);

            this.uiElements.add(seedIcon).add(seedNameText).add(seedDescText).add(buyButton.background).add(buyButton.text);
            y += 70; // Increased spacing for icon and description
        });
        return y + this.UI_SECTION_SPACING;
    }

    createSelectedSeedDisplay(x, y) {
        this.uiElements.add(this.add.text(x, y, 'Selected Seed:', this.TITLE_STYLE));
        y += 25;
        this.selectedSeedText = this.add.text(x, y, 'None', { ...this.TEXT_STYLE, fixedWidth: this.UI_PANEL_WIDTH - (2*this.UI_PANEL_PADDING), wordWrap: {width: this.UI_PANEL_WIDTH - (2*this.UI_PANEL_PADDING)} });
        this.uiElements.add(this.selectedSeedText);
        // Placeholder for selected seed icon
        this.selectedSeedIcon = this.add.image(x + 15, y + 30, '').setVisible(false);
        this.uiElements.add(this.selectedSeedIcon);

        const clearSeedButton = this.createStyledButton(x, y + 50, 'Clear Selection', () => {
            this.selectedSeed = null;
            this.updateSelectedSeedDisplay();
        });
        this.uiElements.add(clearSeedButton.background).add(clearSeedButton.text);

        return y + 80 + this.UI_SECTION_SPACING;
    }

    createMainActionButtons(x, y) {
        const processCycleButton = this.createStyledButton(x, y, 'Next Day', () => this.onProcessCycleClicked());
        this.uiElements.add(processCycleButton.background).add(processCycleButton.text);
        y += this.BUTTON_HEIGHT + 10;

        const codexButton = this.createStyledButton(x, y, 'Codex', () => this.toggleCodexUI());
        this.uiElements.add(codexButton.background).add(codexButton.text);
        y += this.BUTTON_HEIGHT + this.UI_SECTION_SPACING;

        // Audio Mute Buttons
        this.sfxMuteButtonText = this.add.text(0,0, '', this.BUTTON_TEXT_STYLE).setOrigin(0.5); // Will be positioned by createStyledButton
        this.bgmMuteButtonText = this.add.text(0,0, '', this.BUTTON_TEXT_STYLE).setOrigin(0.5);

        const sfxMuteButton = this.createStyledButton(x, y, this.isSfxEnabled ? 'Mute SFX' : 'Unmute SFX', () => this.toggleSfx(), this.UI_PANEL_WIDTH - (2*this.UI_PANEL_PADDING));
        this.sfxMuteButtonText = sfxMuteButton.text; // Store text object for updates
        this.uiElements.add(sfxMuteButton.background).add(this.sfxMuteButtonText);
        y += this.BUTTON_HEIGHT + 10;

        const bgmMuteButton = this.createStyledButton(x, y, this.isBgmEnabled ? 'Mute BGM' : 'Unmute BGM', () => this.toggleBgm(), this.UI_PANEL_WIDTH - (2*this.UI_PANEL_PADDING));
        this.bgmMuteButtonText = bgmMuteButton.text;
        this.uiElements.add(bgmMuteButton.background).add(this.bgmMuteButtonText);
        y += this.BUTTON_HEIGHT + this.UI_SECTION_SPACING;

        return y;
    }

    updateMuteButtonTexts() {
        if (this.sfxMuteButtonText) {
            this.sfxMuteButtonText.setText(this.isSfxEnabled ? 'Mute SFX' : 'Unmute SFX');
        }
        if (this.bgmMuteButtonText) {
            this.bgmMuteButtonText.setText(this.isBgmEnabled ? 'Mute BGM' : 'Unmute BGM');
        }
    }

    createStatusDisplay(x, y) {
        this.statusText = this.add.text(x, y, '', {
            ...this.TEXT_STYLE, fontSize: '12px', fill: '#FF0000',
            fixedWidth: this.UI_PANEL_WIDTH - (2 * this.UI_PANEL_PADDING),
            wordWrap: { width: this.UI_PANEL_WIDTH - (2 * this.UI_PANEL_PADDING) },
            lineSpacing: 5
        });
        this.uiElements.add(this.statusText);
        return y + 30;
    }

    createStyledButton(x, y, label, callback, width = this.UI_PANEL_WIDTH - (2*this.UI_PANEL_PADDING)) {
        const buttonBg = this.add.graphics()
            .fillStyle(this.BUTTON_COLOR, 1)
            .fillRoundedRect(x, y, width, this.BUTTON_HEIGHT, 5)
            .setInteractive(new Phaser.Geom.Rectangle(x, y, width, this.BUTTON_HEIGHT), Phaser.Geom.Rectangle.Contains);

        const buttonText = this.add.text(x + width / 2, y + this.BUTTON_HEIGHT / 2, label, this.BUTTON_TEXT_STYLE).setOrigin(0.5);

        buttonBg.on('pointerdown', () => {
            this.tweens.add({
                targets: [buttonBg, buttonText], // Scale both background and text if desired
                scaleX: 0.95,
                scaleY: 0.95,
                duration: 80,
                yoyo: true,
                ease: 'Power1',
                onComplete: () => {
                    if(buttonBg.active && buttonText.active) { // Check if objects haven't been destroyed
                       buttonBg.setScale(1); // Ensure scale is reset
                       buttonText.setScale(1);
                    }
                    if (callback) callback();
                    this.playSound('sfx_ui_click'); // Play click sound after animation for better feel
                }
            });
        });
        buttonBg.on('pointerover', () => {
            if (buttonBg.active) {
                buttonBg.clear().fillStyle(this.BUTTON_HOVER_COLOR, 1).fillRoundedRect(x, y, width, this.BUTTON_HEIGHT, 5);
            }
        });
        buttonBg.on('pointerout', () => {
            if (buttonBg.active) {
                 buttonBg.clear().fillStyle(this.BUTTON_COLOR, 1).fillRoundedRect(x, y, width, this.BUTTON_HEIGHT, 5);
            }
        });

        return { background: buttonBg, text: buttonText };
    }


    async fetchInitialData() {
        this.showStatus("Loading garden...");
        try {
            const response = await api.getGardenState(); // Use actual API
            // Assuming backend returns { message: "...", data: { garden_id: ..., user_id: ..., flowers: [], user_balance: ...}}
            // The actual backend route returns the garden state directly as response.data
            const gardenData = response.data.data; // Access the nested 'data' field from successful response structure

            this.playerBalance = gardenData.user_balance; // Make sure backend provides this or fetch separately
            this.playerGardenId = gardenData.garden_id;
            // Assuming grid size is fixed or fetched via another call if dynamic
            // this.gridSize = { rows: gardenData.grid_size_y, cols: gardenData.grid_size_x };

            this.updateBalanceDisplay();
            this.renderGarden(gardenData.flowers);
            this.showStatus("Garden loaded.", true); // Success sound will be played by showStatus
        } catch (error) {
            console.error('Error fetching garden state:', error);
            const errorMsg = error.response?.data?.error?.message || error.response?.data?.message || 'Could not load garden.';
            this.showStatus(`Error: ${errorMsg}`); // Error sound played by showStatus
        }
    }

    renderGarden(flowers = []) {
        flowers.forEach(flower => {
            if (flower.position_y < this.gridSize.rows && flower.position_x < this.gridSize.cols) {
                const plot = this.gardenGrid[flower.position_y][flower.position_x];
                const oldStage = plot.flowerData ? plot.flowerData.growth_stage : null;
                plot.flowerData = flower;

                let newTextureKey = 'gfx_plot_empty';
                switch(flower.growth_stage) {
                    case 'seeded': newTextureKey = 'gfx_seed_planted'; break;
                    case 'sprouting': newTextureKey = 'gfx_sprout'; break;
                    case 'blooming': newTextureKey = 'gfx_flower_blooming'; break;
                    // case 'withered': newTextureKey = 'gfx_withered'; break;
                }

                if (plot.sprite.texture.key !== newTextureKey) {
                    plot.sprite.setTexture(newTextureKey);
                    // Growth stage transition visual cue
                    if (oldStage && oldStage !== flower.growth_stage) {
                        this.tweens.add({
                            targets: plot.sprite,
                            scale: 1.15,
                            duration: 150,
                            yoyo: true,
                            ease: 'Sine.easeInOut'
                        });
                        if (this.textures.exists('particle_star')) {
                             const emitter = this.add.particles(plot.sprite.x, plot.sprite.y, 'particle_star', {
                                speed: { min: 20, max: 60 },
                                angle: { min: 0, max: 360 },
                                scale: { start: 0.8, end: 0 },
                                blendMode: 'ADD',
                                lifespan: 400,
                                quantity: 15
                            });
                            emitter.explode(15);
                            this.playSound('sfx_growth_stage');
                        }
                    }
                }
            }
        });
        // Reset plots that no longer have flowers
        for (let r = 0; r < this.gridSize.rows; r++) {
            for (let c = 0; c < this.gridSize.cols; c++) {
                const plot = this.gardenGrid[r][c];
                if (plot.flowerData) { // If plot has data
                    const flowerStillExists = flowers.find(f => f.id === plot.flowerData.id);
                    if (!flowerStillExists) { // And this flower is NOT in the new list from backend
                        plot.flowerData = null;
                        plot.sprite.setTexture('gfx_plot_empty');
                        plot.sprite.clearTint();
                    }
                }
            }
        }
    }

    async onBuySeedClicked(seed) {
        this.showStatus(`Buying ${seed.name}...`);
        try {
            const response = await api.buyCrystalSeed(seed.id); // Use actual API
            this.selectedSeed = seed; // Keep local representation for planting UI
            this.updateSelectedSeedDisplay();

            // Backend response for buy_seed includes new_balance in response.data.data.new_balance
            const oldBalance = this.playerBalance;
            if (response.data && response.data.data && typeof response.data.data.new_balance !== 'undefined') {
                this.playerBalance = response.data.data.new_balance;
                this.updateBalanceDisplay(oldBalance);
            } else {
                await this.fetchInitialData();
            }
            this.showStatus(`${seed.name} selected. Click a plot to plant.`, true);
            this.playSound('sfx_seed_purchase');

        } catch (error) {
            console.error('Error buying seed:', error);
            const errorMsg = error.response?.data?.error?.message || error.response?.data?.message || 'Could not buy seed.';
            this.showStatus(`Error: ${errorMsg}`); // showStatus will play error sound
        }
    }

    updateSelectedSeedDisplay() {
        this.clearPlotHighlights();
        if (this.selectedSeed) {
            this.selectedSeedText.setText(`${this.selectedSeed.name}\n${this.selectedSeed.description}`);
            this.selectedSeedIcon.setTexture(this.selectedSeed.asset_key).setVisible(true).setPosition(this.uiPanelX + (this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING)/2, this.selectedSeedText.y + this.selectedSeedText.height + 25);
            this.highlightEmptyPlots();
        } else {
            this.selectedSeedText.setText('None');
            this.selectedSeedIcon.setVisible(false);
        }
    }

    highlightEmptyPlots() {
        for (let r = 0; r < this.gridSize.rows; r++) {
            for (let c = 0; c < this.gridSize.cols; c++) {
                const plot = this.gardenGrid[r][c];
                if (!plot.flowerData) {
                    plot.sprite.setTint(0x00FF00); // Highlight with green tint
                }
            }
        }
    }

    clearPlotHighlights() {
        for (let r = 0; r < this.gridSize.rows; r++) {
            for (let c = 0; c < this.gridSize.cols; c++) {
                this.gardenGrid[r][c].sprite.clearTint();
            }
        }
    }

    updateBalanceDisplay(oldBalance = null) {
        if (this.balanceText && this.balanceText.active) { // Ensure text object is valid
            this.balanceText.setText(`Balance: ${this.playerBalance}G`);
            if (oldBalance !== null && oldBalance !== this.playerBalance) {
                // Ensure previous tweens are stopped before starting new ones if any
                this.tweens.killTweensOf(this.balanceText);
                this.balanceText.setScale(1); // Reset scale before tweening
                this.balanceText.setFill(this.playerBalance > oldBalance ? '#4CAF50' : '#F44336');

                this.tweens.add({
                    targets: this.balanceText,
                    scale: 1.15,
                    duration: 200, // Slightly longer for better visibility
                    yoyo: true,
                    ease: 'Bounce.easeOut', // Fun bouncy effect
                    onComplete: () => {
                         if(this.balanceText.active) {
                            this.balanceText.setFill(this.TEXT_STYLE.fill);
                            this.balanceText.setScale(1); // Explicitly reset scale
                         }
                    }
                });
            }
        }
    }

    showStatus(message, success = false) {
        if (!this.statusText || !this.statusText.scene) { // Check if scene is valid (object not destroyed)
            console.log("Status text object not available or scene inactive.");
            return;
        }
        this.statusText.setText(message);
        this.statusText.setFill(success ? '#4CAF50' : '#F44336');

        const originalY = this.statusText.y; // Store original Y for reset if needed
        this.statusText.setAlpha(0);
        if(this.statusText.y !== this._statusTextOriginalY && this._statusTextOriginalY) { // Reset if slid from previous message
             this.statusText.setY(this._statusTextOriginalY);
        } else if (!this._statusTextOriginalY) {
            this._statusTextOriginalY = this.statusText.y; // Store initial Y if not stored
        }


        this.tweens.killTweensOf(this.statusText);
        if (this.statusClearTimer) clearTimeout(this.statusClearTimer);

        this.tweens.add({
            targets: this.statusText,
            alpha: 1,
            y: this._statusTextOriginalY - 10, // Slide up
            duration: 300,
            ease: 'Power1',
            onComplete: () => {
                if (success) {
                    this.statusClearTimer = setTimeout(() => {
                        if (!this.statusText.scene) return; // Check again before tweening out
                        this.tweens.add({
                            targets: this.statusText,
                            alpha: 0,
                            y: this._statusTextOriginalY, // Slide back to original position before vanishing
                            duration: 300,
                            ease: 'Power1',
                            onComplete: () => {
                                if(this.statusText.active) this.statusText.setText('');
                            }
                        });
                    }, 2700);
                }
            }
        });
        if (!success) this.playSound('sfx_error_notify');
        // Success sounds are played by the calling function for more context
    }

    onPlotClicked(plotSprite) {
        const row = plotSprite.getData('plotRow');
        const col = plotSprite.getData('plotCol');
        const plot = this.gardenGrid[row][col];

        // Quick click feedback on plot
        this.tweens.add({ targets: plotSprite, scale: 0.95, duration: 80, yoyo: true, ease: 'Power1' });

        this.hideFlowerInfoPanel(); // Hide any existing flower info
        this.hideCodexUI(); // Hide codex if open

        if (plot.flowerData) {
            this.showFlowerInfoPanel(plot.flowerData);
        } else if (this.selectedSeed) {
            this.plantSelectedSeed(this.selectedSeed, row, col);
        } else {
            this.showStatus('Select a seed from the list to plant.');
        }
    }

    showFlowerInfoPanel(flowerData) {
        if (!this.flowerInfoPanel) {
            // Panel Creation (already done in createUIContents, just need to ensure it's built)
            // This should ideally be created once and then shown/hidden.
            // For safety, let's assume it might not be if createUIContents wasn't fully run or panel was destroyed.
            // The current structure creates it in createUIContents and adds to uiElements.
            // We just need to populate and show it.
            // Let's ensure the structure for the flowerInfoPanel content is defined here if not before.
            const panelX = 0; // Relative to container this.flowerInfoPanel
            const panelY = 0; // Relative to container

            const panelBg = this.add.graphics().fillStyle(0x222222, 0.9).fillRect(panelX, panelY, this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING, 450); // Increased height
            const title = this.add.text(panelX + 10, panelY + 10, "Flower Details", this.TITLE_STYLE);
            this.flowerInfoName = this.add.text(panelX + 10, panelY + 40, "", this.TEXT_STYLE);
            this.flowerInfoStage = this.add.text(panelX + 10, panelY + 60, "", this.TEXT_STYLE);
            this.flowerInfoAttributes = this.add.text(panelX + 10, panelY + 80, "", {...this.TEXT_STYLE, lineSpacing: 4, wordWrap: {width: this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 20}});

            // Placeholder buttons for flower actions
            const appraiseBtnY = panelY + 160;
            const appraiseBtn = this.createStyledButton(panelX + 10, appraiseBtnY, 'Appraise', () => console.log("Appraise: " + this.flowerInfoPanel.getData('flowerId')), this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 20);
            const sellBtn = this.createStyledButton(panelX + 10, appraiseBtnY + 40, 'Sell', () => console.log("Sell: " + this.flowerInfoPanel.getData('flowerId')), this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 20);

            // Power-up section
            const powerUpTitleY = sellBtn.background.y + this.BUTTON_HEIGHT + 15;
            const powerUpTitle = this.add.text(panelX + 10, powerUpTitleY, "Apply Power-up:", this.TITLE_STYLE);
            this.flowerInfoPanel.add([panelBg, title, this.flowerInfoName, this.flowerInfoStage, this.flowerInfoAttributes, appraiseBtn.background, appraiseBtn.text, sellBtn.background, sellBtn.text, powerUpTitle]);

            let currentPowerUpY = powerUpTitleY + 25;
            CrystalGardenScene.HARDCODED_POWERUPS.forEach(pu => {
                const puIcon = this.add.image(panelX + 20, currentPowerUpY + 5, pu.asset_key);
                const puText = this.add.text(panelX + 45, currentPowerUpY, `${pu.name} (${pu.cost}G)`, this.TEXT_STYLE);
                const puDesc = this.add.text(panelX + 45, currentPowerUpY + 18, pu.description, {...this.TEXT_STYLE, fontSize:'10px', wordWrap:{width: this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 95}});
                const applyPuBtn = this.createStyledButton(panelX + this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 20 - 60, currentPowerUpY + 5, 'Apply', () => {
                    const currentFlowerData = this.flowerInfoPanel.getData('currentFlowerData');
                    if (currentFlowerData) this.onApplyPowerUpClicked(currentFlowerData, pu.type);
                }, 60);
                this.flowerInfoPanel.add([puIcon, puText, puDesc, applyPuBtn.background, applyPuBtn.text]);
                currentPowerUpY += 55;
            });

            const closeBtnY = currentPowerUpY + 10; // Ensure close button is at the bottom
            const closeBtn = this.createStyledButton(panelX + 10, closeBtnY, 'Close', () => this.hideFlowerInfoPanel(), this.UI_PANEL_WIDTH - 2*this.UI_PANEL_PADDING - 20);
            this.flowerInfoPanel.add([closeBtn.background, closeBtn.text]);

            this.flowerInfoPanel.setPosition(this.uiPanelX + this.UI_PANEL_PADDING, this.gridOffset.y);
        }

        this.flowerInfoPanel.setData('flowerId', flowerData.id);
        this.flowerInfoPanel.setData('currentFlowerData', flowerData); // Store for apply power up
        const seedInfo = this.seedsAvailable.find(s => s.id === flowerData.crystal_seed_id) || { name: 'Unknown Seed' };
        this.flowerInfoName.setText(`Type: ${seedInfo.name} (ID: ${flowerData.id})`);
        this.flowerInfoStage.setText(`Stage: ${flowerData.growth_stage}`);
        let attributes = `Color: ${flowerData.color || 'N/A'}\nSize: ${flowerData.size?.toFixed(1) || 'N/A'}\nClarity: ${flowerData.clarity?.toFixed(2) || 'N/A'}`;
        attributes += `\nSpecial: ${flowerData.special_type || 'None'}`;
        if (flowerData.appraised_value) attributes += `\nValue: ${flowerData.appraised_value}G`;
        attributes += `\nPower-ups: ${flowerData.active_power_ups?.join(', ') || 'None'}`;
        this.flowerInfoAttributes.setText(attributes);

        this.flowerInfoPanel.setAlpha(0).setScale(0.95).setVisible(true).setDepth(50);
        this.tweens.add({ targets: this.flowerInfoPanel, alpha: 1, scale: 1, duration: 150, ease: 'Power1' });
        this.playSound('sfx_panel_open');
    }

    hideFlowerInfoPanel() {
        if (this.flowerInfoPanel && this.flowerInfoPanel.visible) {
            this.playSound('sfx_panel_close');
            this.tweens.add({
                targets: this.flowerInfoPanel, alpha: 0, scale: 0.95, duration: 150, ease: 'Power1',
                onComplete: () => { if(this.flowerInfoPanel) this.flowerInfoPanel.setVisible(false); }
            });
        }
    }

    toggleCodexUI() {
        this.hideFlowerInfoPanel();
        if (!this.codexPanel) {
            const panelWidth = this.cameras.main.width * 0.7;
            const panelHeight = this.cameras.main.height * 0.7;
            const panelBg = this.add.graphics().fillStyle(0x111111, 0.95).fillRect(0, 0, panelWidth, panelHeight);
            panelBg.setPosition(-panelWidth / 2, -panelHeight / 2);

            const title = this.add.text(0, -panelHeight/2 + 20, "Crystal Codex", {...this.TITLE_STYLE, fontSize: '24px'}).setOrigin(0.5);
            const content = this.add.text(0, 0, "Codex - Coming Soon!", this.TEXT_STYLE).setOrigin(0.5);
            const closeButton = this.createStyledButton(0 - 40, panelHeight/2 - this.BUTTON_HEIGHT - 10 , 'Close', () => this.hideCodexUI(), 80);

            this.codexPanel.add([panelBg, title, content, closeButton.background, closeButton.text]);
            this.codexPanel.setPosition(this.cameras.main.width / 2, this.cameras.main.height / 2);
        }

        if (this.codexPanel.visible) {
            this.hideCodexUI();
        } else {
            this.codexPanel.setAlpha(0).setScale(0.9).setVisible(true).setDepth(100);
            this.tweens.add({ targets: this.codexPanel, alpha: 1, scale: 1, duration: 200, ease: 'Power1' });
            this.playSound('sfx_panel_open');
        }
    }
    hideCodexUI() {
        if (this.codexPanel && this.codexPanel.visible) {
            this.playSound('sfx_panel_close');
            this.tweens.add({
                targets: this.codexPanel, alpha: 0, scale: 0.9, duration: 200, ease: 'Power1',
                onComplete: () => {if(this.codexPanel) this.codexPanel.setVisible(false);}
            });
        }
    }

    async plantSelectedSeed(seed, row, col) {
        this.showStatus(`Planting ${seed.name}...`);
        const plot = this.gardenGrid[row][col];
        try {
            const response = await api.plantCrystalSeed({ seed_id: seed.id, position_x: col, position_y: row });
            const newFlowerData = response.data.data.flower;

            if (plot) {
                plot.flowerData = newFlowerData;
                plot.sprite.setTexture('gfx_seed_planted');
                 // Planting Animation: Particle burst
                if (this.textures.exists('particle_star')) {
                    const emitter = this.add.particles(plot.sprite.x, plot.sprite.y, 'particle_star', {
                        speed: { min: 40, max: 100 },
                        angle: { min: -90-45, max: -90+45 }, // Upwards burst
                        scale: { start: 1, end: 0 },
                        blendMode: 'ADD', // For bright particles
                        lifespan: 300,
                        quantity: 15
                    });
                    emitter.explode(15);
                    this.playSound('sfx_plant_seed');
                }
            } else {
                console.error(`Error: Plot at (${row},${col}) not found in local grid representation.`);
            }
            this.showStatus(`${seed.name} planted at (${col}, ${row}).`, true);
            this.selectedSeed = null;
            this.updateSelectedSeedDisplay();
            await this.fetchInitialData();
        } catch (error) {
            console.error('Error planting seed:', error);
            const errorMsg = error.response?.data?.error?.message || error.response?.data?.message || 'Could not plant seed.';
            this.showStatus(`Error: ${errorMsg}`);
            if(plot) plot.sprite.clearTint();
        }
    }

    async onProcessCycleClicked() {
        // playerGardenId is not strictly needed for the API call as backend uses current_user
        // but good to have a check if scene thinks garden is loaded.
        if (this.playerGardenId === null && !this.scene.isActive(this.key)) { // Check if scene is active
             this.showStatus("Garden not loaded or scene not active.");
             return;
        }
        this.showStatus("Processing new day cycle...");
        try {
            // The API method processGardenCycle now sends {} as payload.
            await api.processGardenCycle();
            await this.fetchInitialData(); // Refresh garden state
            this.showStatus("New day processed. Garden updated.", true);
        } catch (error) {
            console.error('Error processing cycle:', error);
            const errorMsg = error.response?.data?.error?.message || error.response?.data?.message || 'Could not process cycle.';
            this.showStatus(`Error: ${errorMsg}`);
        }
    }

async onApplyPowerUpClicked(flowerData, powerUpType) {
    if (!flowerData || !powerUpType) return;
    const powerUpMeta = CrystalGardenScene.HARDCODED_POWERUPS.find(p => p.type === powerUpType);
    if (!powerUpMeta) {
        this.showStatus("Unknown power-up selected.");
        return;
    }

    this.showStatus(`Applying ${powerUpMeta.name} to Flower ID ${flowerData.id}...`);
    try {
        const response = await api.activatePowerUp({ flower_id: flowerData.id, power_up_type: powerUpType });
        const oldBalance = this.playerBalance;
        if (response.data && response.data.data && typeof response.data.data.new_balance !== 'undefined') {
            this.playerBalance = response.data.data.new_balance;
            this.updateBalanceDisplay(oldBalance);
        }

        const updatedFlower = response.data.data.flower;
        const plot = this.gardenGrid[updatedFlower.position_y][updatedFlower.position_x];
        if (plot) {
            plot.flowerData = updatedFlower;
        }
        this.showFlowerInfoPanel(updatedFlower);
        this.showStatus(`${powerUpMeta.name} applied successfully!`, true);
        this.playSound('sfx_apply_powerup');

    } catch (error) {
        console.error(`Error applying power-up ${powerUpType}:`, error);
        const errorMsg = error.response?.data?.error?.message || error.response?.data?.message || `Could not apply ${powerUpMeta.name}.`;
        this.showStatus(`Error: ${errorMsg}`);
    }
}

    update(time, delta) {
        // Game loop
    }
}
