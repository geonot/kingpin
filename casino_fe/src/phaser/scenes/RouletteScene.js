import Phaser from 'phaser';

export default class RouletteScene extends Phaser.Scene {
    constructor() {
        super({ key: 'RouletteScene' });
        this.vueComponent = null; // To store reference to the Vue component
    }

    init(data) {
        // Receive the Vue component instance
        this.vueComponent = data.vueComponent;
    }

    preload() {
        // Placeholder for assets - later load images for wheel, ball, table
        // For now, we'll use graphics
        console.log('RouletteScene: preload');
    }

    create() {
        console.log('RouletteScene: create');
        this.cameras.main.setBackgroundColor('#2d2d2d'); // Dark grey background

        // Event emitter for communication with Vue
        this.emitter = new Phaser.Events.EventEmitter();

        // --- Placeholder Graphics ---

        // 1. Roulette Wheel (Placeholder)
        this.wheel = this.add.graphics();
        this.wheel.fillStyle(0x1a1a1a, 1); // Darker grey for wheel
        this.wheel.fillCircle(200, 250, 150); // x, y, radius
        this.wheel.lineStyle(2, 0xffffff, 1);
        this.wheel.strokeCircle(200, 250, 150);
        this.add.text(160, 240, 'Wheel', { fontSize: '24px', fill: '#fff' });

        // 2. Ball (Placeholder)
        this.ball = this.add.graphics();
        this.ball.fillStyle(0xffffff, 1); // White ball
        this.ball.fillCircle(200, 150, 10); // Initially somewhere on the wheel path

        // 3. Betting Table (Placeholder Rectangle)
        this.bettingTable = this.add.graphics();
        this.bettingTable.fillStyle(0x006400, 1); // Dark green for table
        this.bettingTable.fillRect(400, 50, 550, 400); // x, y, width, height
        this.add.text(550, 30, 'Betting Table', { fontSize: '20px', fill: '#fff' });

        // --- Betting Areas (Simplified Placeholders) ---
        // These would be more complex with actual number grids

        let startX = 420;
        let startY = 80;
        let boxWidth = 40;
        let boxHeight = 30;
        let margin = 5;

        // Example: 0
        const zeroButton = this.add.graphics().fillStyle(0x008000, 1).fillRect(startX, startY, boxWidth * 2 + margin, boxHeight);
        this.add.text(startX + boxWidth/2 + margin, startY + 5, '0', { fontSize: '16px', fill: '#fff' })
            .setInteractive()
            .on('pointerdown', () => this.onBetPlacement('straight_up', 0));

        startY += boxHeight + margin;

        // Example: Numbers 1-3 (as a simple row)
        for (let i = 1; i <= 3; i++) {
            let x = startX + (i - 1) * (boxWidth + margin);
            this.add.graphics().fillStyle(0x555555, 1).fillRect(x, startY, boxWidth, boxHeight);
            this.add.text(x + 15, startY + 5, i.toString(), { fontSize: '16px', fill: '#fff' })
                .setInteractive()
                .on('pointerdown', () => this.onBetPlacement('straight_up', i));
        }
        startY += boxHeight + margin;

        // Example: Red/Black buttons
        const redButton = this.add.graphics().fillStyle(0xff0000, 1).fillRect(startX, startY, boxWidth * 2, boxHeight);
        this.add.text(startX + 10, startY + 5, 'RED', { fontSize: '16px', fill: '#fff' })
            .setInteractive()
            .on('pointerdown', () => this.onBetPlacement('red', null));

        const blackButton = this.add.graphics().fillStyle(0x000000, 1).fillRect(startX + boxWidth * 2 + margin, startY, boxWidth*2, boxHeight);
        this.add.text(startX + boxWidth * 2 + margin + 10, startY + 5, 'BLACK', { fontSize: '16px', fill: '#fff' })
             .setInteractive()
             .on('pointerdown', () => this.onBetPlacement('black', null));

        // More betting options (dozens, columns, even/odd, 1-18/19-36) would be added similarly.
        // This is a very simplified layout. A real roulette table is more complex.

        // Example of emitting an event to Vue
        // this.emitter.emit('phaserEvent', { message: 'Scene created!' });

        // Placeholder for spinning animation function
        this.spinAnim = null;
    }

    onBetPlacement(betType, betValue) {
        console.log(`Phaser: Bet selected - Type: ${betType}, Value: ${betValue}`);
        if (this.vueComponent && this.vueComponent.selectBetType) {
            this.vueComponent.selectBetType(betType, betValue);
        } else {
            console.warn('Vue component or selectBetType method not available in Phaser scene.');
        }
    }

    // --- Placeholder for Animation ---
    startWheelSpin(winningNumber) {
        console.log(`Phaser: Told to spin for ${winningNumber}. Animation to be implemented.`);
        // 1. Animate ball spinning around the wheel
        // 2. Animate wheel spinning (slower, maybe opposite direction)
        // 3. Ball "drops" and settles on the winningNumber
        // 4. Emit event when animation is complete

        // For now, just simulate delay and announce result
        this.ball.x = 200 + Math.random() * 100 - 50; // Randomize ball position a bit
        this.ball.y = 150 + Math.random() * 100 - 50;

        this.time.delayedCall(2000, () => { // Simulate 2s spin
            // Update ball graphic to position of winning number (highly simplified)
            // This needs a proper mapping of numbers to wheel positions
            this.ball.x = 200; // Center for now
            this.ball.y = 100; // Top for now
            console.log(`Phaser: Spin finished. Winning number (visual placeholder): ${winningNumber}`);
            if (this.vueComponent) {
                // this.vueComponent.handleSpinResult(winningNumber); // Vue component should handle result from API call
            }
        });
    }

    update() {
        // Any ongoing updates, e.g., for animations
    }
}
