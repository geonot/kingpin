import Phaser from 'phaser';

export default class RouletteScene extends Phaser.Scene {
    constructor() {
        super({ key: 'RouletteScene' });
        this.vueComponent = null;
        
        // Game objects
        this.wheel = null;
        this.ball = null;
        this.wheelGraphics = null;
        this.ballGraphics = null;
        this.bettingTable = null;
        this.numberPositions = [];
        
        // Animation state
        this.isSpinning = false;
        this.wheelSpeed = 0;
        this.ballSpeed = 0;
        this.ballAngle = 0;
        this.ballRadius = 180;
        
        // Roulette numbers in wheel order
        this.wheelNumbers = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
            24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
        ];
    }

    init(data) {
        this.vueComponent = data ? data.vueComponent : null;
    }

    preload() {
        // Create simple graphics for wheel and ball if not loaded
        if (!this.textures.exists('wheel')) {
            this.createWheelTexture();
        }
    }

    create() {
        console.log('RouletteScene: create()');
        
        this.setupWheel();
        this.setupBall();
        this.setupBettingTable();
        this.setupNumberPositions();
        
        console.log('RouletteScene: Ready');
    }

    createWheelTexture() {
        const graphics = this.add.graphics();
        
        // Create wheel texture
        graphics.fillStyle(0x8B4513); // Brown wood
        graphics.fillCircle(200, 200, 190);
        
        // Create number pockets
        const angleStep = (Math.PI * 2) / 37; // 37 numbers (0-36)
        
        for (let i = 0; i < 37; i++) {
            const angle = i * angleStep;
            const number = this.wheelNumbers[i];
            const isRed = this.isRedNumber(number);
            const isBlack = this.isBlackNumber(number);
            
            // Pocket color
            let color = 0x008000; // Green for 0
            if (isRed) color = 0xFF0000;
            if (isBlack) color = 0x000000;
            
            // Draw pocket
            graphics.fillStyle(color);
            graphics.slice(200, 200, 150, 180, angle - angleStep/2, angle + angleStep/2);
            graphics.fillPath();
            
            // Number text
            const textX = 200 + Math.cos(angle) * 165;
            const textY = 200 + Math.sin(angle) * 165;
            
            this.add.text(textX, textY, number.toString(), {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: color === 0x000000 ? '#FFFFFF' : '#000000',
                fontStyle: 'bold'
            }).setOrigin(0.5);
        }
        
        // Center hub
        graphics.fillStyle(0x444444);
        graphics.fillCircle(200, 200, 30);
        
        graphics.generateTexture('wheel', 400, 400);
        graphics.destroy();
    }

    setupWheel() {
        this.wheel = this.add.image(300, 250, 'wheel')
            .setDisplaySize(350, 350)
            .setOrigin(0.5);
    }

    setupBall() {
        this.ballGraphics = this.add.graphics();
        this.updateBallPosition();
    }

    setupBettingTable() {
        const startX = 500;
        const startY = 100;
        const cellWidth = 40;
        const cellHeight = 30;
        
        // Create number grid (simplified)
        for (let row = 0; row < 3; row++) {
            for (let col = 0; col < 12; col++) {
                const number = (row * 12) + col + 1;
                const x = startX + (col * cellWidth);
                const y = startY + (row * cellHeight);
                
                const isRed = this.isRedNumber(number);
                const color = isRed ? 0xFF4444 : 0x444444;
                
                // Number cell
                const cell = this.add.rectangle(x, y, cellWidth - 2, cellHeight - 2, color)
                    .setStrokeStyle(1, 0xFFFFFF)
                    .setInteractive({ useHandCursor: true })
                    .on('pointerdown', () => this.onBetPlacement('straight_up', number));
                
                this.add.text(x, y, number.toString(), {
                    fontSize: '12px',
                    fontFamily: 'Arial',
                    fill: '#FFFFFF',
                    fontStyle: 'bold'
                }).setOrigin(0.5);
            }
        }
        
        // Zero
        this.add.rectangle(startX - cellWidth, startY + cellHeight, cellWidth * 2, cellHeight, 0x008000)
            .setStrokeStyle(1, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.onBetPlacement('straight_up', 0));
            
        this.add.text(startX - cellWidth, startY + cellHeight, '0', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Outside bets
        const outsideY = startY + (3 * cellHeight) + 20;
        
        // Red/Black
        this.add.rectangle(startX, outsideY, cellWidth * 3, cellHeight, 0xFF0000)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.onBetPlacement('red', null));
            
        this.add.text(startX, outsideY, 'RED', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.add.rectangle(startX + (cellWidth * 4), outsideY, cellWidth * 3, cellHeight, 0x000000)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.onBetPlacement('black', null));
            
        this.add.text(startX + (cellWidth * 4), outsideY, 'BLACK', {
            fontSize: '14px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        // Even/Odd
        this.add.rectangle(startX + (cellWidth * 8), outsideY, cellWidth * 2, cellHeight, 0x666666)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.onBetPlacement('even', null));
            
        this.add.text(startX + (cellWidth * 8), outsideY, 'EVEN', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.add.rectangle(startX + (cellWidth * 10), outsideY, cellWidth * 2, cellHeight, 0x666666)
            .setStrokeStyle(2, 0xFFFFFF)
            .setInteractive({ useHandCursor: true })
            .on('pointerdown', () => this.onBetPlacement('odd', null));
            
        this.add.text(startX + (cellWidth * 10), outsideY, 'ODD', {
            fontSize: '12px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
    }

    setupNumberPositions() {
        // Calculate positions for each number on the wheel
        const angleStep = (Math.PI * 2) / 37;
        const centerX = 300;
        const centerY = 250;
        const radius = 165;
        
        this.wheelNumbers.forEach((number, index) => {
            const angle = index * angleStep;
            const x = centerX + Math.cos(angle) * radius;
            const y = centerY + Math.sin(angle) * radius;
            
            this.numberPositions[number] = { x, y, angle };
        });
    }

    onBetPlacement(betType, betValue) {
        console.log(`Phaser: Bet selected - Type: ${betType}, Value: ${betValue}`);
        if (this.vueComponent && this.vueComponent.selectBetType) {
            this.vueComponent.selectBetType(betType, betValue);
        } else {
            console.warn('Vue component or selectBetType method not available in Phaser scene.');
        }
    }

    startWheelSpin(winningNumber) {
        if (this.isSpinning) return;
        
        console.log(`Phaser: Starting spin for winning number ${winningNumber}`);
        this.isSpinning = true;
        
        // Initialize spin parameters
        this.wheelSpeed = 5 + Math.random() * 3; // Random wheel speed
        this.ballSpeed = 8 + Math.random() * 4; // Faster ball speed
        this.ballAngle = Math.random() * Math.PI * 2; // Random starting position
        this.ballRadius = 180; // Start at outer edge
        
        // Calculate target angle for winning number
        const numberIndex = this.wheelNumbers.indexOf(winningNumber);
        const targetAngle = (numberIndex / 37) * Math.PI * 2;
        
        // Animate the spin
        this.animateSpin(winningNumber, targetAngle);
    }

    animateSpin(winningNumber, targetAngle) {
        const spinDuration = 3000 + Math.random() * 2000; // 3-5 seconds
        const startTime = this.time.now;
        
        const spinTween = this.tweens.add({
            targets: this.wheel,
            rotation: this.wheel.rotation + (Math.PI * 8) + targetAngle, // Multiple spins plus target
            duration: spinDuration,
            ease: 'Cubic.easeOut',
            onComplete: () => {
                this.finalizeSpin(winningNumber);
            }
        });
        
        // Ball animation - moves in opposite direction and gradually slows down
        this.ballSpinAnimation(spinDuration, winningNumber);
    }

    ballSpinAnimation(duration, winningNumber) {
        const startTime = this.time.now;
        
        const ballUpdate = () => {
            if (!this.isSpinning) return;
            
            const elapsed = this.time.now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Gradually decrease ball speed and radius
            this.ballSpeed = (8 - progress * 7); // Slow down from 8 to 1
            this.ballRadius = 180 - (progress * 30); // Move inward
            
            // Update ball angle (opposite direction to wheel)
            this.ballAngle -= this.ballSpeed * 0.02;
            
            this.updateBallPosition();
            
            if (progress < 1) {
                this.time.delayedCall(16, ballUpdate); // ~60fps
            }
        };
        
        ballUpdate();
    }

    updateBallPosition() {
        const centerX = 300;
        const centerY = 250;
        const ballX = centerX + Math.cos(this.ballAngle) * this.ballRadius;
        const ballY = centerY + Math.sin(this.ballAngle) * this.ballRadius;
        
        this.ballGraphics.clear();
        this.ballGraphics.fillStyle(0xFFFFFF);
        this.ballGraphics.fillCircle(ballX, ballY, 8);
    }

    finalizeSpin(winningNumber) {
        this.isSpinning = false;
        
        // Position ball on winning number
        if (this.numberPositions[winningNumber]) {
            const pos = this.numberPositions[winningNumber];
            this.ballGraphics.clear();
            this.ballGraphics.fillStyle(0xFFD700); // Gold color for final position
            this.ballGraphics.fillCircle(pos.x, pos.y, 10);
        }
        
        // Flash winning number
        this.flashWinningNumber(winningNumber);
        
        console.log(`Phaser: Spin completed. Winning number: ${winningNumber}`);
    }

    flashWinningNumber(winningNumber) {
        const pos = this.numberPositions[winningNumber];
        if (!pos) return;
        
        const flash = this.add.circle(pos.x, pos.y, 25, 0xFFD700, 0.8);
        
        this.tweens.add({
            targets: flash,
            alpha: { from: 0.8, to: 0 },
            scale: { from: 1, to: 2 },
            duration: 1000,
            repeat: 2,
            onComplete: () => flash.destroy()
        });
    }

    isRedNumber(number) {
        const redNumbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36];
        return redNumbers.includes(number);
    }

    isBlackNumber(number) {
        return number > 0 && !this.isRedNumber(number);
    }

    update() {
        // Handle any continuous updates during spinning
        if (this.isSpinning && this.ballSpeed > 0) {
            // Ball physics could be updated here if needed
        }
    }
}
