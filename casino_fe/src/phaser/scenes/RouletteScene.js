import Phaser from 'phaser';

export default class RouletteScene extends Phaser.Scene {
    constructor() {
        super({ key: 'RouletteScene' });
        
        // Game state
        this.eventBus = null;
        this.gameConfig = null;
        this.tableData = null;
        
        // Wheel components
        this.wheelContainer = null;
        this.wheel = null;
        this.ball = null;
        this.wheelNumbers = [];
        
        // Betting table
        this.bettingTable = null;
        this.betSpots = [];
        this.playerBets = [];
        this.chipTextures = [];
        
        // Game state
        this.isSpinning = false;
        this.currentBets = {};
        this.selectedChipValue = 1;
        this.winningNumber = null;
        
        // Animation properties
        this.wheelSpeed = 0;
        this.ballSpeed = 0;
        this.targetAngle = 0;
        
        // Roulette wheel numbers in order (European wheel)
        this.wheelOrder = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
            24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
        ];
        
        // Number colors (true = red, false = black, null = green)
        this.numberColors = {
            0: null, // Green
            1: true, 3: true, 5: true, 7: true, 9: true, 12: true, 14: true, 16: true,
            18: true, 19: true, 21: true, 23: true, 25: true, 27: true, 30: true, 32: true, 34: true, 36: true,
            2: false, 4: false, 6: false, 8: false, 10: false, 11: false, 13: false, 15: false,
            17: false, 20: false, 22: false, 24: false, 26: false, 28: false, 29: false, 31: false, 33: false, 35: false
        };
    }

    init(data) {
        this.eventBus = this.registry.get('eventBus');
        this.gameConfig = this.registry.get('gameDefinition');
        this.tableData = this.registry.get('tableData');
    }

    create() {
        console.log('RouletteScene: create()');
        
        if (!this.eventBus || !this.gameConfig) {
            console.error('RouletteScene: Critical data missing');
            return;
        }

        this.createBackground();
        this.createWheel();
        this.createBettingTable();
        this.createChipSelection();
        this.createUI();
        this.setupEventListeners();
        
        this.eventBus.emit('rouletteGameReady');
        console.log('RouletteScene: Ready');
    }

    createBackground() {
        // Green felt background
        this.add.rectangle(
            this.cameras.main.centerX,
            this.cameras.main.centerY,
            this.cameras.main.width,
            this.cameras.main.height,
            0x0d5016
        );
        
        // Table border
        this.add.rectangle(
            this.cameras.main.centerX,
            this.cameras.main.centerY,
            this.cameras.main.width - 40,
            this.cameras.main.height - 40,
            0x0d5016
        ).setStrokeStyle(4, 0xFFD700);
        
        // Title
        this.add.text(this.cameras.main.centerX, 30, 'ROULETTE', {
            fontSize: '32px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold'
        }).setOrigin(0.5);
    }

    createWheel() {
        const centerX = 200;
        const centerY = 250;
        const wheelRadius = 120;
        
        // Create wheel container
        this.wheelContainer = this.add.container(centerX, centerY);
        
        // Wheel outer rim
        const outerRim = this.add.circle(0, 0, wheelRadius + 10, 0x8B4513)
            .setStrokeStyle(4, 0xFFD700);
        this.wheelContainer.add(outerRim);
        
        // Wheel inner background
        this.wheel = this.add.circle(0, 0, wheelRadius, 0x2F1B14);
        this.wheelContainer.add(this.wheel);
        
        // Create wheel segments
        this.createWheelSegments(wheelRadius);
        
        // Wheel center
        const center = this.add.circle(0, 0, 20, 0xFFD700)
            .setStrokeStyle(2, 0x000000);
        this.wheelContainer.add(center);
        
        // Ball
        this.ball = this.add.circle(0, -wheelRadius + 10, 8, 0xFFFFFF)
            .setStrokeStyle(1, 0x000000);
        this.wheelContainer.add(this.ball);
        
        // Wheel pointer
        const pointer = this.add.polygon(centerX, centerY - wheelRadius - 20, [
            0, 0, -10, -15, 10, -15
        ], 0xFFD700).setStrokeStyle(2, 0x000000);
    }

    createWheelSegments(radius) {
        const segmentAngle = (Math.PI * 2) / this.wheelOrder.length;
        
        this.wheelOrder.forEach((number, index) => {
            const angle = index * segmentAngle;
            const nextAngle = (index + 1) * segmentAngle;
            
            // Determine segment color
            let segmentColor;
            if (this.numberColors[number] === null) {
                segmentColor = 0x008000; // Green for 0
            } else if (this.numberColors[number]) {
                segmentColor = 0xFF0000; // Red
            } else {
                segmentColor = 0x000000; // Black
            }
            
            // Create segment
            const segment = this.add.graphics();
            segment.fillStyle(segmentColor);
            segment.beginPath();
            segment.moveTo(0, 0);
            segment.arc(0, 0, radius - 5, angle, nextAngle);
            segment.closePath();
            segment.fillPath();
            
            // White separator lines
            segment.lineStyle(1, 0xFFFFFF);
            segment.beginPath();
            segment.moveTo(0, 0);
            segment.lineTo(
                Math.cos(angle) * radius,
                Math.sin(angle) * radius
            );
            segment.strokePath();
            
            this.wheelContainer.add(segment);
            
            // Number text
            const textRadius = radius - 20;
            const textAngle = angle + segmentAngle / 2;
            const textX = Math.cos(textAngle) * textRadius;
            const textY = Math.sin(textAngle) * textRadius;
            
            const numberText = this.add.text(textX, textY, number.toString(), {
                fontSize: '14px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            this.wheelContainer.add(numberText);
            this.wheelNumbers.push({
                number: number,
                angle: textAngle,
                text: numberText
            });
        });
    }

    createBettingTable() {
        const tableX = 450;
        const tableY = 150;
        const cellWidth = 40;
        const cellHeight = 60;
        
        // Betting table background
        this.bettingTable = this.add.rectangle(tableX, tableY, 320, 280, 0x0d5016)
            .setStrokeStyle(2, 0xFFD700);
        
        // Number grid (1-36)
        for (let row = 0; row < 3; row++) {
            for (let col = 0; col < 12; col++) {
                const number = (col * 3) + row + 1;
                const x = tableX - 140 + (col * cellWidth);
                const y = tableY - 80 + (row * cellHeight);
                
                // Cell background color
                let cellColor;
                if (this.numberColors[number]) {
                    cellColor = 0x8B0000; // Dark red
                } else {
                    cellColor = 0x2F2F2F; // Dark gray (black)
                }
                
                // Create betting spot
                const betSpot = this.add.rectangle(x, y, cellWidth - 2, cellHeight - 2, cellColor)
                    .setStrokeStyle(1, 0xFFFFFF)
                    .setInteractive()
                    .setData('betType', 'straight')
                    .setData('betValue', number);
                
                // Number text
                this.add.text(x, y, number.toString(), {
                    fontSize: '16px',
                    fontFamily: 'Arial',
                    fill: '#FFFFFF',
                    fontStyle: 'bold'
                }).setOrigin(0.5);
                
                // Click handler
                betSpot.on('pointerdown', () => this.placeBet('straight', number));
                betSpot.on('pointerover', () => betSpot.setFillStyle(cellColor, 0.7));
                betSpot.on('pointerout', () => betSpot.setFillStyle(cellColor, 1));
                
                this.betSpots.push(betSpot);
            }
        }
        
        // Zero betting spot
        const zeroSpot = this.add.rectangle(tableX - 160, tableY - 40, cellWidth - 2, 180, 0x008000)
            .setStrokeStyle(1, 0xFFFFFF)
            .setInteractive()
            .setData('betType', 'straight')
            .setData('betValue', 0);
        
        this.add.text(tableX - 160, tableY - 40, '0', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        zeroSpot.on('pointerdown', () => this.placeBet('straight', 0));
        this.betSpots.push(zeroSpot);
        
        // Outside bets
        this.createOutsideBets(tableX, tableY + 120);
    }

    createOutsideBets(startX, startY) {
        const outsideBets = [
            { label: 'RED', type: 'color', value: 'red', color: 0x8B0000 },
            { label: 'BLACK', type: 'color', value: 'black', color: 0x2F2F2F },
            { label: 'EVEN', type: 'evenodd', value: 'even', color: 0x4A4A4A },
            { label: 'ODD', type: 'evenodd', value: 'odd', color: 0x4A4A4A },
            { label: '1-18', type: 'range', value: 'low', color: 0x4A4A4A },
            { label: '19-36', type: 'range', value: 'high', color: 0x4A4A4A },
            { label: '1st 12', type: 'dozen', value: 'first', color: 0x4A4A4A },
            { label: '2nd 12', type: 'dozen', value: 'second', color: 0x4A4A4A },
            { label: '3rd 12', type: 'dozen', value: 'third', color: 0x4A4A4A }
        ];
        
        outsideBets.forEach((bet, index) => {
            const x = startX - 140 + ((index % 3) * 80);
            const y = startY + Math.floor(index / 3) * 35;
            
            const betSpot = this.add.rectangle(x, y, 75, 30, bet.color)
                .setStrokeStyle(1, 0xFFFFFF)
                .setInteractive()
                .setData('betType', bet.type)
                .setData('betValue', bet.value);
            
            this.add.text(x, y, bet.label, {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            betSpot.on('pointerdown', () => this.placeBet(bet.type, bet.value));
            betSpot.on('pointerover', () => betSpot.setFillStyle(bet.color, 0.7));
            betSpot.on('pointerout', () => betSpot.setFillStyle(bet.color, 1));
            
            this.betSpots.push(betSpot);
        });
    }

    createChipSelection() {
        const chipValues = [1, 5, 25, 100, 500];
        const chipColors = [0xFFFFFF, 0xFF4444, 0x44AA44, 0x4444FF, 0x000000];
        
        chipValues.forEach((value, index) => {
            const chipX = 100 + (index * 60);
            const chipY = 500;
            
            // Chip background
            const chip = this.add.circle(chipX, chipY, 25, chipColors[index])
                .setStrokeStyle(3, 0xFFD700)
                .setInteractive()
                .setData('chipValue', value);
            
            // Chip value text
            this.add.text(chipX, chipY, `$${value}`, {
                fontSize: '12px',
                fontFamily: 'Arial',
                fill: value === 500 ? '#FFFFFF' : '#000000',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            // Selection indicator
            const indicator = this.add.circle(chipX, chipY, 30, 0x00FF00, 0)
                .setStrokeStyle(3, 0x00FF00)
                .setVisible(value === 1); // Default selection
            
            chip.on('pointerdown', () => {
                this.selectedChipValue = value;
                this.updateChipSelection();
                this.playSound('chipClick');
            });
            
            chip.on('pointerover', () => chip.setScale(1.1));
            chip.on('pointerout', () => chip.setScale(1.0));
            
            this.chipTextures.push({ chip, indicator, value });
        });
    }

    createUI() {
        // Control buttons
        this.createControlButtons();
        
        // Bet display
        this.totalBetText = this.add.text(600, 50, 'Total Bet: $0', {
            fontSize: '18px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold',
            backgroundColor: '#000000',
            padding: { x: 10, y: 5 }
        });
        
        // Balance display
        this.balanceText = this.add.text(600, 80, 'Balance: $1000', {
            fontSize: '16px',
            fontFamily: 'Arial',
            fill: '#FFFFFF',
            backgroundColor: '#000000',
            padding: { x: 10, y: 5 }
        });
        
        // Winning number display
        this.winningNumberText = this.add.text(400, 500, '', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FFD700',
            fontStyle: 'bold',
            backgroundColor: '#000000',
            padding: { x: 15, y: 8 }
        }).setOrigin(0.5).setVisible(false);
    }

    createControlButtons() {
        const buttonY = 450;
        const buttons = [
            { text: 'SPIN', action: 'spin', color: 0x4CAF50 },
            { text: 'CLEAR BETS', action: 'clear', color: 0xF44336 },
            { text: 'DOUBLE', action: 'double', color: 0xFF9800 },
            { text: 'REBET', action: 'rebet', color: 0x2196F3 }
        ];
        
        buttons.forEach((btn, index) => {
            const buttonX = 520 + (index * 80);
            
            const button = this.add.rectangle(buttonX, buttonY, 70, 35, btn.color)
                .setStrokeStyle(2, 0xFFFFFF)
                .setInteractive();
            
            this.add.text(buttonX, buttonY, btn.text, {
                fontSize: '10px',
                fontFamily: 'Arial',
                fill: '#FFFFFF',
                fontStyle: 'bold'
            }).setOrigin(0.5);
            
            button.on('pointerdown', () => this.handleButtonClick(btn.action));
            button.on('pointerover', () => button.setFillStyle(btn.color, 0.8));
            button.on('pointerout', () => button.setFillStyle(btn.color, 1));
        });
    }

    setupEventListeners() {
        if (this.eventBus) {
            this.eventBus.on('rouletteSpin', this.handleSpin, this);
            this.eventBus.on('rouletteBetPlaced', this.handleBetPlaced, this);
            this.eventBus.on('rouletteSpinComplete', this.handleSpinComplete, this);
        }
    }

    updateChipSelection() {
        this.chipTextures.forEach(chipData => {
            chipData.indicator.setVisible(chipData.value === this.selectedChipValue);
        });
    }

    placeBet(betType, betValue) {
        if (this.isSpinning) {
            console.log('Cannot bet while spinning');
            return;
        }
        
        const betKey = `${betType}_${betValue}`;
        
        if (!this.currentBets[betKey]) {
            this.currentBets[betKey] = {
                type: betType,
                value: betValue,
                amount: 0,
                chips: []
            };
        }
        
        this.currentBets[betKey].amount += this.selectedChipValue;
        
        // Visual chip placement
        this.placeChipVisual(betType, betValue);
        
        // Update UI
        this.updateBetDisplay();
        
        // Play sound
        this.playSound('chipPlace');
        
        console.log(`Placed ${this.selectedChipValue} on ${betType} ${betValue}`);
    }

    placeChipVisual(betType, betValue) {
        // Find the betting spot
        let spotX, spotY;
        
        if (betType === 'straight') {
            if (betValue === 0) {
                spotX = 290; // Zero position
                spotY = 210;
            } else {
                const row = (betValue - 1) % 3;
                const col = Math.floor((betValue - 1) / 3);
                spotX = 310 + (col * 40);
                spotY = 110 + (row * 60);
            }
        } else {
            // Handle outside bets positions
            spotX = 450; // Default position
            spotY = 270;
        }
        
        // Create chip visual
        const chipColor = this.getChipColor(this.selectedChipValue);
        const chip = this.add.circle(spotX, spotY, 12, chipColor)
            .setStrokeStyle(2, 0xFFD700)
            .setDepth(10);
        
        // Add chip value
        this.add.text(spotX, spotY, this.selectedChipValue.toString(), {
            fontSize: '10px',
            fontFamily: 'Arial',
            fill: this.selectedChipValue === 500 ? '#FFFFFF' : '#000000',
            fontStyle: 'bold'
        }).setOrigin(0.5).setDepth(11);
        
        // Store chip reference
        const betKey = `${betType}_${betValue}`;
        if (!this.currentBets[betKey].chips) {
            this.currentBets[betKey].chips = [];
        }
        this.currentBets[betKey].chips.push(chip);
    }

    getChipColor(value) {
        const colorMap = {
            1: 0xFFFFFF,
            5: 0xFF4444,
            25: 0x44AA44,
            100: 0x4444FF,
            500: 0x000000
        };
        return colorMap[value] || 0xFFFFFF;
    }

    handleButtonClick(action) {
        switch (action) {
            case 'spin':
                this.startSpin();
                break;
            case 'clear':
                this.clearAllBets();
                break;
            case 'double':
                this.doubleBets();
                break;
            case 'rebet':
                this.rebetLast();
                break;
        }
    }

    startSpin() {
        if (this.isSpinning) return;
        
        const totalBet = this.getTotalBetAmount();
        if (totalBet === 0) {
            console.log('No bets placed');
            return;
        }
        
        this.isSpinning = true;
        
        // Enhanced spin start effects
        this.createSpinStartEffects();
        
        // Generate random winning number
        this.winningNumber = Math.floor(Math.random() * 37); // 0-36
        
        // Calculate target angle for winning number
        const winningIndex = this.wheelOrder.indexOf(this.winningNumber);
        const segmentAngle = (Math.PI * 2) / this.wheelOrder.length;
        this.targetAngle = winningIndex * segmentAngle;
        
        // Start wheel animation
        this.animateWheel();
        
        // Play spin sound
        this.playSound('wheelSpin');
        
        console.log(`Spinning... Winning number will be: ${this.winningNumber}`);
    }

    createSpinStartEffects() {
        // Screen flash effect
        const flash = this.add.rectangle(400, 300, 800, 600, 0xFFD700, 0.3);
        this.tweens.add({
            targets: flash,
            alpha: 0,
            duration: 200,
            onComplete: () => flash.destroy()
        });
        
        // "No more bets" text
        const noMoreBetsText = this.add.text(400, 200, 'NO MORE BETS!', {
            fontSize: '24px',
            fontFamily: 'Arial',
            fill: '#FF0000',
            fontStyle: 'bold'
        }).setOrigin(0.5);
        
        this.tweens.add({
            targets: noMoreBetsText,
            alpha: 0,
            duration: 2000,
            delay: 500,
            onComplete: () => noMoreBetsText.destroy()
        });
        
        // Sparkle effects around wheel
        this.createWheelSparkles();
    }

    createWheelSparkles() {
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const distance = 140;
            const x = 200 + Math.cos(angle) * distance;
            const y = 250 + Math.sin(angle) * distance;
            
            const sparkle = this.add.circle(x, y, 3, 0xFFD700);
            
            this.tweens.add({
                targets: sparkle,
                scaleX: 0,
                scaleY: 0,
                alpha: 0,
                duration: 1000,
                delay: i * 100,
                onComplete: () => sparkle.destroy()
            });
        }
    }

    animateWheel() {
        // Initial wheel and ball speeds
        this.wheelSpeed = 0.3;
        this.ballSpeed = -0.5; // Opposite direction
        
        // Random number of full rotations before stopping
        const extraRotations = 3 + Math.random() * 2;
        const finalAngle = this.targetAngle + (extraRotations * Math.PI * 2);
        
        // Animate wheel
        this.tweens.add({
            targets: this.wheelContainer,
            rotation: finalAngle,
            duration: 4000,
            ease: 'Cubic.easeOut',
            onComplete: () => {
                this.isSpinning = false;
                this.handleSpinResult();
            }
        });
        
        // Animate ball
        this.animateBall();
    }

    animateBall() {
        // Ball follows opposite direction initially, then settles
        let ballAngle = 0;
        const ballRadius = 110;
        
        const ballTimer = this.time.addEvent({
            delay: 50,
            callback: () => {
                ballAngle += this.ballSpeed;
                
                // Gradually slow down the ball
                this.ballSpeed *= 0.995;
                
                // Position ball
                const ballX = Math.cos(ballAngle) * ballRadius;
                const ballY = Math.sin(ballAngle) * ballRadius;
                this.ball.setPosition(ballX, ballY);
                
                // Stop when ball is very slow
                if (Math.abs(this.ballSpeed) < 0.01) {
                    ballTimer.remove();
                    // Final ball position at winning number
                    const finalBallAngle = this.targetAngle + Math.PI; // Opposite side
                    const finalX = Math.cos(finalBallAngle) * (ballRadius - 10);
                    const finalY = Math.sin(finalBallAngle) * (ballRadius - 10);
                    
                    this.tweens.add({
                        targets: this.ball,
                        x: finalX,
                        y: finalY,
                        duration: 500,
                        ease: 'Back.easeIn'
                    });
                }
            },
            repeat: -1
        });
    }

    handleSpinResult() {
        // Show winning number
        this.displayWinningNumber();
        
        // Calculate winnings
        const winnings = this.calculateWinnings();
        
        // Highlight winning number
        this.highlightWinningNumber();
        
        // Show results
        setTimeout(() => {
            this.showSpinResults(winnings);
        }, 1000);
        
        // Play result sound
        if (winnings > 0) {
            this.playSound('win');
        } else {
            this.playSound('lose');
        }
    }

    displayWinningNumber() {
        let numberColor = '#FFFFFF';
        if (this.numberColors[this.winningNumber] === true) {
            numberColor = '#FF0000'; // Red
        } else if (this.numberColors[this.winningNumber] === false) {
            numberColor = '#000000'; // Black
        } else {
            numberColor = '#00FF00'; // Green
        }
        
        this.winningNumberText
            .setText(`Winning Number: ${this.winningNumber}`)
            .setFill(numberColor)
            .setVisible(true);
        
        // Animate winning number display
        this.tweens.add({
            targets: this.winningNumberText,
            scaleX: 1.2,
            scaleY: 1.2,
            duration: 200,
            yoyo: true,
            repeat: 2
        });
    }

    highlightWinningNumber() {
        // Find and highlight the winning number on the wheel
        const winningNumberData = this.wheelNumbers.find(n => n.number === this.winningNumber);
        if (winningNumberData) {
            // Create highlight effect
            const highlight = this.add.circle(0, 0, 15, 0xFFFF00, 0.5)
                .setStrokeStyle(3, 0xFFFF00);
            
            const highlightX = Math.cos(winningNumberData.angle) * 100;
            const highlightY = Math.sin(winningNumberData.angle) * 100;
            highlight.setPosition(highlightX, highlightY);
            
            this.wheelContainer.add(highlight);
            
            // Flash animation
            this.tweens.add({
                targets: highlight,
                alpha: 0,
                duration: 300,
                yoyo: true,
                repeat: 5,
                onComplete: () => highlight.destroy()
            });
        }
    }

    calculateWinnings() {
        let totalWinnings = 0;
        
        Object.entries(this.currentBets).forEach(([betKey, bet]) => {
            const payout = this.calculateBetPayout(bet);
            if (payout > 0) {
                totalWinnings += payout;
                console.log(`${bet.type} ${bet.value}: ${bet.amount} wins ${payout}`);
            }
        });
        
        return totalWinnings;
    }

    calculateBetPayout(bet) {
        const { type, value, amount } = bet;
        
        switch (type) {
            case 'straight':
                return value === this.winningNumber ? amount * 35 : 0;
                
            case 'color': {
                const isRed = this.numberColors[this.winningNumber] === true;
                const isBlack = this.numberColors[this.winningNumber] === false;
                if ((value === 'red' && isRed) || (value === 'black' && isBlack)) {
                    return amount * 2;
                }
                return 0;
            }
                
            case 'evenodd': {
                if (this.winningNumber === 0) return 0;
                const isEven = this.winningNumber % 2 === 0;
                if ((value === 'even' && isEven) || (value === 'odd' && !isEven)) {
                    return amount * 2;
                }
                return 0;
            }
                
            case 'range': {
                if (this.winningNumber === 0) return 0;
                if ((value === 'low' && this.winningNumber <= 18) || 
                    (value === 'high' && this.winningNumber >= 19)) {
                    return amount * 2;
                }
                return 0;
            }
                
            case 'dozen': {
                if (this.winningNumber === 0) return 0;
                const dozen = Math.ceil(this.winningNumber / 12);
                const dozenMap = { 'first': 1, 'second': 2, 'third': 3 };
                if (dozenMap[value] === dozen) {
                    return amount * 3;
                }
                return 0;
            }
                
            default:
                return 0;
        }
    }

    showSpinResults(winnings) {
        if (winnings > 0) {
            // Show win message with celebration
            const winText = this.add.text(400, 300, `YOU WIN $${winnings}!`, {
                fontSize: '32px',
                fontFamily: 'Arial',
                fill: '#FFD700',
                fontStyle: 'bold',
                backgroundColor: '#000000',
                padding: { x: 20, y: 10 }
            }).setOrigin(0.5).setDepth(100);
            
            // Win celebration effects
            this.createWinCelebration(400, 300, winnings);
            
            // Animate win text
            this.tweens.add({
                targets: winText,
                scaleX: 1.2,
                scaleY: 1.2,
                duration: 300,
                yoyo: true,
                repeat: 3,
                onComplete: () => {
                    winText.destroy();
                    this.clearAllBets();
                }
            });
        } else {
            // Show lose message
            const loseText = this.add.text(400, 300, 'HOUSE WINS', {
                fontSize: '24px',
                fontFamily: 'Arial',
                fill: '#FF0000',
                fontStyle: 'bold',
                backgroundColor: '#000000',
                padding: { x: 15, y: 8 }
            }).setOrigin(0.5).setDepth(100);
            
            setTimeout(() => {
                loseText.destroy();
                this.clearAllBets();
            }, 2000);
        }
        
        // Hide winning number after delay
        setTimeout(() => {
            this.winningNumberText.setVisible(false);
        }, 3000);
    }

    createWinCelebration(x, y, amount) {
        // Create golden particles explosion
        for (let i = 0; i < 20; i++) {
            const particle = this.add.circle(x, y, 5, 0xFFD700);
            
            const angle = (Math.PI * 2 * i) / 20;
            const distance = 100 + Math.random() * 50;
            
            this.tweens.add({
                targets: particle,
                x: x + Math.cos(angle) * distance,
                y: y + Math.sin(angle) * distance,
                alpha: 0,
                scaleX: 0.2,
                scaleY: 0.2,
                duration: 1000,
                delay: i * 30,
                onComplete: () => particle.destroy()
            });
        }
        
        // Create floating coins for big wins
        if (amount > 100) {
            this.createCoinRain(x, y);
        }
    }

    createCoinRain(x, y) {
        for (let i = 0; i < 10; i++) {
            const coin = this.add.circle(x + (Math.random() - 0.5) * 200, y - 100, 8, 0xFFD700)
                .setStrokeStyle(2, 0x000000);
            
            this.tweens.add({
                targets: coin,
                y: y + 200,
                rotation: Math.PI * 4,
                duration: 1500,
                delay: i * 100,
                ease: 'Bounce.easeOut',
                onComplete: () => coin.destroy()
            });
        }
    }

    clearAllBets() {
        // Remove chip visuals
        Object.values(this.currentBets).forEach(bet => {
            if (bet.chips) {
                bet.chips.forEach(chip => chip.destroy());
            }
        });
        
        // Clear bet data
        this.currentBets = {};
        
        // Update display
        this.updateBetDisplay();
        
        console.log('All bets cleared');
    }

    doubleBets() {
        Object.values(this.currentBets).forEach(bet => {
            bet.amount *= 2;
        });
        this.updateBetDisplay();
        console.log('Bets doubled');
    }

    rebetLast() {
        // Implementation for rebetting last round's bets
        console.log('Rebet last (not implemented)');
    }

    getTotalBetAmount() {
        return Object.values(this.currentBets).reduce((total, bet) => total + bet.amount, 0);
    }

    updateBetDisplay() {
        const totalBet = this.getTotalBetAmount();
        this.totalBetText.setText(`Total Bet: $${totalBet}`);
    }

    playSound(soundKey) {
        try {
            const sound = this.sound.get(soundKey);
            if (sound) {
                sound.play({ volume: 0.3 });
            }
        } catch (e) {
            console.warn(`Could not play sound: ${soundKey}`, e);
        }
    }

    shutdown() {
        if (this.eventBus) {
            this.eventBus.off('rouletteSpin', this.handleSpin, this);
            this.eventBus.off('rouletteBetPlaced', this.handleBetPlaced, this);
            this.eventBus.off('rouletteSpinComplete', this.handleSpinComplete, this);
        }
        
        // Clean up any active tweens
        this.tweens.killAll();
    }
}