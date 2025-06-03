import Phaser from 'phaser';
import EventBus from '@/event-bus';

export default class PlinkoScene extends Phaser.Scene {
  constructor() {
    super({ key: 'PlinkoScene' });
    this.isControlledByVue = false;
    this.activeBall = null; // Matter body
    this.activeBallVisual = null; // Phaser visual
    this.currentStakeLevel = null; // String: 'low', 'medium', 'high'
    this.collisionListener = null; 
  }

  preload() {
    // Preload assets here if needed in the future
    // e.g., this.load.image('ball_green', 'path/to/ball_green.png');
  }

  create() {
    this.cameras.main.setBackgroundColor('#2c3e50');
    this.add.text(this.cameras.main.width / 2, 50, 'Plinko', {
      fontSize: '48px', fill: '#ffffff', fontFamily: 'Arial'
    }).setOrigin(0.5);

    this.matter.world.setBounds(0, 0, this.cameras.main.width, this.cameras.main.height);

    this._createPegs();
    this._createPrizeSlots();

    // Setup collision listener once
    this.collisionListener = (event, bodyA, bodyB) => {
      let ballBody = null;
      let otherBody = null;

      // Identify which body is the ball and which is the other object
      if (this.activeBall && this.activeBall.body === bodyA) {
        ballBody = bodyA;
        otherBody = bodyB;
      } else if (this.activeBall && this.activeBall.body === bodyB) {
        ballBody = bodyB;
        otherBody = bodyA;
      }

      // If the active ball was involved and the other body is a slot
      if (ballBody && otherBody && otherBody.label && otherBody.label.startsWith('slot_')) {
        this.handleBallLanding(otherBody.label);
      }
    };
    this.matter.world.on('collisionstart', this.collisionListener);
    
    // Notify Vue that Phaser is ready if needed, or Vue calls setControlledByVue directly
    // EventBus.$emit('phaserReady'); // Example
  }

  setControlledByVue(isControlled) {
    this.isControlledByVue = isControlled;
    console.log('PlinkoScene: Controlled by Vue set to', isControlled);
    if (this.isControlledByVue) {
      // If there was any auto-dropped ball (e.g. from a non-Vue test mode), remove it.
      if (this.activeBall) {
        this.matter.world.remove(this.activeBall); // Remove Matter body
        this.activeBall = null;
      }
      if (this.activeBallVisual) {
        this.activeBallVisual.destroy(); // Remove Phaser visual
        this.activeBallVisual = null;
      }
      // Signal that the scene is ready for Vue-controlled drops
      EventBus.$emit('ballReady');
    }
  }

  _createPegs() {
    const pegColor = 0xffffff;
    const pegRadius = 8;
    const rows = 10;
    const firstRowY = 150;
    const spacingY = 50;
    const spacingX = 50;

    for (let i = 0; i < rows; i++) {
      const numPegsInRow = i + 4;
      const y = firstRowY + i * spacingY;
      const totalWidthForRow = (numPegsInRow - 1) * spacingX;
      let startX = (this.cameras.main.width - totalWidthForRow) / 2;

      for (let j = 0; j < numPegsInRow; j++) {
        const x = startX + j * spacingX;
        // Physics body for peg
        this.matter.add.circle(x, y, pegRadius, {
          isStatic: true, restitution: 0.5, friction: 0.1, label: 'peg'
        });
        // Visual for peg
        this.add.circle(x, y, pegRadius, pegColor);
      }
    }
  }

  _createPrizeSlots() {
    const slotHeight = 50;
    const slotValues = [0.5, 1, 2, 5, 2, 1, 0.5];
    const numSlots = slotValues.length;
    const slotWidth = this.cameras.main.width / numSlots;
    const slotY = this.cameras.main.height - slotHeight / 2;

    slotValues.forEach((value, index) => {
      const x = (index * slotWidth) + (slotWidth / 2);
      // Sensor for prize detection
      this.matter.add.rectangle(x, slotY + slotHeight / 2 - 5, slotWidth - 10, slotHeight - 10, {
        isStatic: true, isSensor: true, label: `slot_${value}x`
      });
      // Visual for slot
      this.add.rectangle(x, slotY, slotWidth - 2, slotHeight - 2, 0x333333).setStrokeStyle(2, 0x777777);
      this.add.text(x, slotY, `${value}x`, { fontSize: '20px', fill: '#ffffff', fontFamily: 'Arial' }).setOrigin(0.5);
    });

    const wallThickness = 10;
    const wallHeight = slotHeight * 1.5;
    for (let i = 0; i <= numSlots; i++) {
      const wallX = i * slotWidth;
      // Physical walls between slots
      this.matter.add.rectangle(wallX, slotY - wallHeight / 2 + slotHeight / 2, wallThickness, wallHeight, {
        isStatic: true, restitution: 0.1, friction: 0.1, label: 'slot_wall'
      });
    }
  }

  // Internal method to create ball visuals and physics body
  _makeActualBall(x, y, colorHex, stakeLevel) {
    const ballRadius = 10;
    this.activeBallVisual = this.add.circle(x, y, ballRadius, colorHex);
    this.activeBall = this.matter.add.circle(x, y, ballRadius, {
      restitution: 0.7, // Bounciness
      friction: 0.05,   // How much it slides against pegs
      label: 'ball',
      density: 0.005    // Affects how "heavy" it feels
    });
    this.currentStakeLevel = stakeLevel;
  }

  // Public method called by Vue to drop a ball
  dropBall(stakeLevel) {
    if (this.activeBall) {
      console.warn('PlinkoScene: Ball already active. Ignoring drop request.');
      return false; // Indicate drop failed / ball busy
    }
    // if (!this.isControlledByVue) {
    //   console.warn('PlinkoScene: Not controlled by Vue. Consider disabling direct calls.');
    //   // Decide if you want to allow drops even if not "officially" controlled.
    //   // For now, we'll allow it, assuming setControlledByVue(true) will be called by Vue.
    // }

    let ballColor;
    switch (stakeLevel ? stakeLevel.toLowerCase() : 'medium') { // Default to medium if stakeLevel is undefined
      case 'low': ballColor = 0x00ff00; break; // Green
      case 'medium': ballColor = 0xffff00; break; // Yellow
      case 'high': ballColor = 0xff0000; break; // Red
      default: ballColor = 0xffcc00; // A default orange/yellow
    }

    const ballX = this.cameras.main.width / 2 + Phaser.Math.Between(-5, 5); // Slight random X offset
    const ballY = 100; // Initial drop height from top
    
    this._makeActualBall(ballX, ballY, ballColor, stakeLevel);

    EventBus.$emit('ballDropped'); // Signal Vue that ball has been dropped (e.g., disable button)
    console.log(`PlinkoScene: Dropping ${stakeLevel} ball.`);
    return true; // Indicate drop was successful
  }

  handleBallLanding(slotLabel) {
    // Ensure this logic only runs if there's an active ball and it hasn't been processed
    if (!this.activeBall) {
        console.warn('PlinkoScene: handleBallLanding called without an active ball.');
        return; 
    }

    const prizeValueString = slotLabel.replace('slot_', '').replace('x', '');
    const prizeValue = parseFloat(prizeValueString);

    console.log(`PlinkoScene: Ball landed in ${slotLabel}. Stake: ${this.currentStakeLevel}, Prize: ${prizeValue}x`);

    // Remove the ball (physics and visual)
    if (this.activeBall) {
      this.matter.world.remove(this.activeBall); // Remove Matter body
      this.activeBall = null;
    }
    if (this.activeBallVisual) {
      this.activeBallVisual.destroy(); // Remove Phaser visual
      this.activeBallVisual = null;
    }

    // Only emit events if controlled by Vue
    if (this.isControlledByVue) {
      EventBus.$emit('ballLanded', { prizeValue: prizeValue, stake: this.currentStakeLevel });
      EventBus.$emit('ballReady'); // Signal Vue that a new ball can be dropped
    } else {
      // This block is for testing the scene directly without Vue.
      // No automatic respawn. A new ball must be manually triggered via dropBall() if testing.
      console.log('PlinkoScene: Ball landed (not Vue controlled). Ready for next manual drop.');
    }
    
    this.currentStakeLevel = null; // Reset for the next drop
  }

  update(time, delta) {
    // Keep the visual representation in sync with the physics body
    if (this.activeBall && this.activeBall.body && this.activeBallVisual) {
      this.activeBallVisual.setPosition(this.activeBall.position.x, this.activeBall.position.y);
      // For non-circular sprites, you might also sync rotation:
      // this.activeBallVisual.setRotation(this.activeBall.angle);
    }
  }

  shutdown() {
    // Remove the global collision listener when the scene shuts down
    if (this.collisionListener) {
      this.matter.world.off('collisionstart', this.collisionListener);
      this.collisionListener = null;
    }
    // Clean up any other resources or event listeners
    console.log('PlinkoScene shutdown successfully.');
  }
}
