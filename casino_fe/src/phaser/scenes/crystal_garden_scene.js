import Phaser from 'phaser';

// Mock API service for frontend development
const API = {
    get: async (endpoint) => {
        console.log(`Mock API GET: ${endpoint}`);
        if (endpoint === '/crystal-garden/garden-state') {
            // Simulate fetching garden state
            return Promise.resolve({
                data: {
                    garden_id: 1, // Example garden ID
                    user_id: 1, // Example user ID
                    grid_size_x: 5,
                    grid_size_y: 5,
                    last_cycle_time: new Date().toISOString(),
                    flowers: [
                        // { id: 1, crystal_seed_id: 1, planted_at: new Date().toISOString(), growth_stage: 'seeded', position_x: 0, position_y: 0, color: null, size: null, clarity: null, special_type: null, appraised_value: null, active_power_ups: [] },
                        // { id: 2, crystal_seed_id: 2, planted_at: new Date().toISOString(), growth_stage: 'sprouting', position_x: 1, position_y: 1, color: null, size: null, clarity: null, special_type: null, appraised_value: null, active_power_ups: [] }
                    ],
                    user_balance: 1000 // Example balance
                }
            });
        }
        // Add other GET endpoints if needed, e.g., for all-seeds-info
        return Promise.resolve({ data: {} });
    },
    post: async (endpoint, data) => {
        console.log(`Mock API POST: ${endpoint}`, data);
        if (endpoint === '/crystal-garden/buy-seed') {
            const seedToBuy = CrystalGardenScene.HARDCODED_SEEDS.find(s => s.id === data.seed_id);
            if (seedToBuy) {
                 // Simulate balance deduction - actual balance managed by backend
                return Promise.resolve({ data: { message: 'Seed purchased', seed_id: data.seed_id, new_balance: `(simulated after buying ${seedToBuy.name})` } });
            } else {
                return Promise.reject({ response: { data: { message: 'Seed not found' }, status: 404 } });
            }
        }
        if (endpoint === '/crystal-garden/plant-seed') {
            return Promise.resolve({ data: { message: 'Seed planted', flower: { id: Date.now(), ...data, growth_stage: 'seeded', active_power_ups:[] } } });
        }
        if (endpoint === '/crystal-garden/process-cycle') {
            return Promise.resolve({ data: { message: 'Cycle processed', report: { updated_flowers: 1, newly_bloomed: 1 } } });
        }
        return Promise.resolve({ data: { message: 'Action successful' } });
    }
};


export default class CrystalGardenScene extends Phaser.Scene {
    static HARDCODED_SEEDS = [
        { id: 1, name: 'Terra Seed', cost: 50, asset_key: 'seed_terra_gfx', description: "A common earth seed." },
        { id: 2, name: 'Aqua Seed', cost: 75, asset_key: 'seed_aqua_gfx', description: "A seed from watery depths." },
        { id: 3, name: 'Ignis Seed', cost: 100, asset_key: 'seed_ignis_gfx', description: "A seed born of fire." }
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
    }

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

        CrystalGardenScene.HARDCODED_SEEDS.forEach(seed => {
             this.createPlaceholderTexture(seed.asset_key, 20, 20, Phaser.Display.Color.RandomRGB(100,200).color, seed.name.substring(0,1));
        });


        this.cameras.main.setBackgroundColor('#2E7D32');
        this.add.text(this.cameras.main.width / 2, 30, 'Crystal Garden', {
            fontSize: '28px', fill: '#fff', fontStyle: 'bold'
        }).setOrigin(0.5);

        this.initGardenGrid();
        this.createUI();
        this.fetchInitialData();
    }

    initGardenGrid() {
        for (let row = 0; row < this.gridSize.rows; row++) {
            this.gardenGrid[row] = [];
            for (let col = 0; col < this.gridSize.cols; col++) {
                const x = this.gridOffset.x + col * this.cellSize + this.cellSize / 2;
                const y = this.gridOffset.y + row * this.cellSize + this.cellSize / 2;
                const plotSprite = this.add.sprite(x, y, 'gfx_plot_empty').setInteractive();
                plotSprite.on('pointerdown', () => this.onPlotClicked(row, col));
                this.gardenGrid[row][col] = { sprite: plotSprite, flowerData: null, row: row, col: col };
            }
        }
    }

    createUI() {
        this.uiElements.clear(true, true); // Clear previous UI elements

        const uiAreaX = this.gridOffset.x + (this.gridSize.cols * this.cellSize) + 30;
        const uiAreaWidth = this.cameras.main.width - uiAreaX - 30;
        let currentY = this.gridOffset.y;

        this.balanceText = this.add.text(uiAreaX, currentY, `Balance: ${this.playerBalance}G`, {
            fontSize: '16px', fill: '#fff', backgroundColor: '#00000099', padding: {x:5, y:3}, wordWrap: {width: uiAreaWidth}
        });
        this.uiElements.add(this.balanceText);
        currentY += 40;

        this.uiElements.add(this.add.text(uiAreaX, currentY, 'Available Seeds:', { fontSize: '16px', fill: '#fff', fontStyle: 'bold' }));
        currentY += 30;

        this.seedsAvailable.forEach(seed => {
            const seedButton = this.add.text(uiAreaX, currentY, `Buy ${seed.name} (${seed.cost}G)`, {
                fontSize: '14px', fill: '#00FF00', backgroundColor: '#00000099', padding: {x:5, y:3}, wordWrap: {width: uiAreaWidth}
            }).setInteractive();
            seedButton.on('pointerdown', () => this.onBuySeedClicked(seed));
            this.uiElements.add(seedButton);
            currentY += 30;
        });

        currentY += 20; // Spacer

        this.selectedSeedText = this.add.text(uiAreaX, currentY, 'Selected: None', {
             fontSize: '14px', fill: '#FFD700', backgroundColor: '#00000099', padding: {x:5, y:3}, wordWrap: {width: uiAreaWidth}
        });
        this.uiElements.add(this.selectedSeedText);
        currentY += 40;

        const nextDayButton = this.add.text(uiAreaX, currentY, 'Next Day Cycle', {
            fontSize: '16px', fill: '#FFFF00', backgroundColor: '#000000CC', padding: {x:10, y:5}
        }).setInteractive();
        nextDayButton.on('pointerdown', () => this.onProcessCycleClicked());
        this.uiElements.add(nextDayButton);
        currentY += 50;

        this.statusText = this.add.text(uiAreaX, currentY, '', {
            fontSize: '12px', fill: '#FF0000', wordWrap: {width: uiAreaWidth}, lineSpacing: 5
        });
        this.uiElements.add(this.statusText);
    }

    async fetchInitialData() {
        this.showStatus("Loading garden...");
        try {
            const response = await API.get('/crystal-garden/garden-state');
            const gardenData = response.data;
            this.playerBalance = gardenData.user_balance;
            this.playerGardenId = gardenData.garden_id;
            this.gridSize = { rows: gardenData.grid_size_y, cols: gardenData.grid_size_x };
            // Note: If grid size changes, initGardenGrid would ideally be recalled or plots adjusted.
            // For this subtask, assume grid size is fixed after initial load or scene restart.
            this.updateBalanceDisplay();
            this.renderGarden(gardenData.flowers);
            this.showStatus("Garden loaded.", true);
        } catch (error) {
            console.error('Error fetching garden state:', error);
            this.showStatus(`Error: ${error.response?.data?.message || 'Could not load garden.'}`);
        }
    }

    renderGarden(flowers = []) {
        // Clear existing flower sprites/data from plots
        for (let r = 0; r < this.gridSize.rows; r++) {
            for (let c = 0; c < this.gridSize.cols; c++) {
                if (this.gardenGrid[r] && this.gardenGrid[r][c]) {
                    this.gardenGrid[r][c].flowerData = null;
                    this.gardenGrid[r][c].sprite.setTexture('gfx_plot_empty'); // Reset to empty
                    this.gardenGrid[r][c].sprite.setTint(0xFFFFFF); // Clear tint
                }
            }
        }
        // Render new flower states
        flowers.forEach(flower => {
            if (flower.position_y < this.gridSize.rows && flower.position_x < this.gridSize.cols) {
                const plot = this.gardenGrid[flower.position_y][flower.position_x];
                plot.flowerData = flower;
                let textureKey = 'gfx_plot_empty';
                switch(flower.growth_stage) {
                    case 'seeded': textureKey = 'gfx_seed_planted'; break;
                    case 'sprouting': textureKey = 'gfx_sprout'; break;
                    case 'blooming':
                        textureKey = 'gfx_flower_blooming';
                        // Could apply tint based on flower.color if gfx_flower_blooming is white/greyscale
                        // For example: plot.sprite.setTint(Phaser.Display.Color.HexStringToColor(flower.color || '#FFFFFF').color);
                        break;
                    // case 'withered': textureKey = 'gfx_withered'; break; // Placeholder
                }
                plot.sprite.setTexture(textureKey);
            }
        });
    }

    async onBuySeedClicked(seed) {
        this.showStatus(`Buying ${seed.name}...`);
        try {
            await API.post('/crystal-garden/buy-seed', { seed_id: seed.id });
            this.selectedSeed = seed;
            this.updateSelectedSeedDisplay();
            // Balance update will come from backend in a real scenario, or fetch it again.
            // For mock, we assume backend handles it. Refreshing full state for simplicity here.
            this.showStatus(`${seed.name} selected. Click a plot to plant.`, true);
            this.fetchInitialData(); // To update balance and reflect purchase (mocked)
        } catch (error) {
            console.error('Error buying seed:', error);
            this.showStatus(`Error: ${error.response?.data?.message || 'Could not buy seed.'}`);
        }
    }

    updateSelectedSeedDisplay() {
        if (this.selectedSeed) {
            this.selectedSeedText.setText(`Selected: ${this.selectedSeed.name}`);
        } else {
            this.selectedSeedText.setText('Selected: None');
        }
    }

    updateBalanceDisplay() {
        this.balanceText.setText(`Balance: ${this.playerBalance}G`);
    }

    showStatus(message, success = false) {
        this.statusText.setText(message);
        this.statusText.setFill(success ? '#00FF00' : '#FF0000');
        if(success && this.statusClearTimer) clearTimeout(this.statusClearTimer);
        if(success) {
            this.statusClearTimer = setTimeout(() => this.statusText.setText(''), 3000);
        }
    }

    onPlotClicked(row, col) {
        console.log(`Clicked plot ${row}, ${col}`);
        const plot = this.gardenGrid[row][col];

        if (plot.flowerData && plot.flowerData.growth_stage === 'blooming') {
            this.showStatus(`Flower Options: Appraise, Sell, Power-up (see console)`);
            console.log(`Blooming Flower [ID: ${plot.flowerData.id}] Options:`);
            console.log("- Appraise (Not implemented in UI)");
            console.log("- Sell (Not implemented in UI)");
            console.log("- Use Power-up (Not implemented in UI)");
            // Future: Show a small context menu or UI panel for these actions
        } else if (this.selectedSeed) {
            if (!plot.flowerData) { // Plot is empty
                this.plantSelectedSeed(this.selectedSeed, row, col);
            } else {
                this.showStatus('This plot is already occupied.');
                console.log('Plot already occupied.');
            }
        } else {
            this.showStatus('Select a seed from the list to plant.');
            console.log('No seed selected. Click a seed to buy/select it first.');
        }
    }

    async plantSelectedSeed(seed, row, col) {
        this.showStatus(`Planting ${seed.name}...`);
        try {
            const response = await API.post('/crystal-garden/plant-seed', {
                seed_id: seed.id,
                position_x: col, // API uses x for column
                position_y: row   // API uses y for row
            });
            // Update plot visually based on response
            const newFlowerData = response.data.flower;
            this.gardenGrid[row][col].flowerData = newFlowerData;
            this.gardenGrid[row][col].sprite.setTexture('gfx_seed_planted'); // Or based on newFlowerData.growth_stage

            this.showStatus(`${seed.name} planted at (${col}, ${row}).`, true);
            this.selectedSeed = null;
            this.updateSelectedSeedDisplay();
            // Refresh garden state to show new flower and potentially updated balance
            this.fetchInitialData();
        } catch (error) {
            console.error('Error planting seed:', error);
            this.showStatus(`Error: ${error.response?.data?.message || 'Could not plant seed.'}`);
        }
    }

    async onProcessCycleClicked() {
        if (this.playerGardenId === null) {
            this.showStatus("Garden not loaded yet.");
            return;
        }
        this.showStatus("Processing new day cycle...");
        try {
            await API.post('/crystal-garden/process-cycle', { garden_id: this.playerGardenId });
            // Refresh the entire garden state to see changes
            await this.fetchInitialData();
            this.showStatus("New day processed. Garden updated.", true);
        } catch (error) {
            console.error('Error processing cycle:', error);
            this.showStatus(`Error: ${error.response?.data?.message || 'Could not process cycle.'}`);
        }
    }

    update(time, delta) {
        // Game loop
    }
}
