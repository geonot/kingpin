<template>
  <div class="plinko-game">
    <div class="game-container" ref="gameContainer"></div>
    <div class="ui-controls">
      <!-- Stake selection and play button will go here -->
      <div class="stake-selection">
        <button @click="setStake('low')" :class="{ active: currentStake === 'low' }">Low (Green)</button>
        <button @click="setStake('medium')" :class="{ active: currentStake === 'medium' }">Medium (Yellow)</button>
        <button @click="setStake('high')" :class="{ active: currentStake === 'high' }">High (Red)</button>
      </div>
      <button @click="dropBallHandler" :disabled="isBallDropping">Drop Ball</button>
      <div class="game-info">
        <p>Current Stake: {{ currentStake }}</p>
        <p>Last Winnings: {{ lastWinnings }}x</p>
        <!-- Balance display can be added if a store is available -->
      </div>
    </div>
  </div>
</template>

<script>
import Phaser from 'phaser';
import PlinkoScene from '@/phaser/scenes/PlinkoScene';
// Assuming an EventBus for Phaser to Vue communication, if not, alternative will be used.
import EventBus from '@/event-bus'; // Adjust path if necessary

export default {
  name: 'PlinkoGame',
  data() {
    return {
      game: null,
      currentStake: 'medium', // Default stake
      lastWinnings: 0,
      isBallDropping: false, // To disable button while ball is active
    };
  },
  mounted() {
    const gameConfig = {
      type: Phaser.AUTO,
      width: 800, // Adjust as needed
      height: 700, // Adjust as needed
      parent: this.$refs.gameContainer,
      physics: {
        default: 'matter',
        matter: {
          gravity: { y: 0.8 },
          debug: false, // Set to true for physics debugging
          enableSleeping: true,
        },
      },
      scene: [PlinkoScene], // Add BootScene/PreloadScene if you have them
    };
    this.game = new Phaser.Game(gameConfig);

    // Listen for events from Phaser scene
    EventBus.$on('ballLanded', this.handleBallLandedEvent);
    EventBus.$on('ballDropped', () => { this.isBallDropping = true; });
    EventBus.$on('ballReady', () => { this.isBallDropping = false; });


    // A way to signal to Phaser scene that it's ready (optional, if scene needs early Vue data)
    // Or call a method on the scene once it's ready.
    this.game.events.on('ready', () => {
        const scene = this.game.scene.getScene('PlinkoScene');
        if (scene && scene.events) {
             // Example: scene.setInitialStake(this.currentStake);
             // Ensure PlinkoScene is set up to handle being controlled by Vue
             scene.events.emit('vueReady'); // Signal Vue is ready
             scene.setControlledByVue(true); // Add this method to PlinkoScene
        }
    });
  },
  beforeUnmount() {
    if (this.game) {
      this.game.destroy(true);
      this.game = null;
    }
    EventBus.$off('ballLanded', this.handleBallLandedEvent);
    EventBus.$off('ballDropped');
    EventBus.$off('ballReady');
  },
  methods: {
    setStake(stakeLevel) {
      this.currentStake = stakeLevel;
      // Optionally, communicate this to Phaser immediately if needed
      // const scene = this.game.scene.getScene('PlinkoScene');
      // if (scene && scene.setStake) {
      //   scene.setStake(this.currentStake);
      // }
    },
    dropBallHandler() {
      if (this.game && !this.isBallDropping) {
        const scene = this.game.scene.getScene('PlinkoScene');
        if (scene && scene.dropBall) {
          scene.dropBall(this.currentStake);
          this.isBallDropping = true; // Prevent multiple drops until ball lands or scene signals ready
        } else {
          console.error('PlinkoScene not found or dropBall method missing.');
          this.isBallDropping = false; // Reset if error
        }
      }
    },
    handleBallLandedEvent({ prizeValue, stake }) {
      // Ensure this is only processed if the stake matches the one that initiated the drop
      if (stake === this.currentStake) {
          this.lastWinnings = prizeValue;
          this.isBallDropping = false; // Allow another ball drop
          // Here you would typically update user balance, etc.
          console.log(`Received winnings: ${prizeValue}x for stake: ${stake}`);
      }
    },
  },
};
</script>

<style scoped>
.plinko-game {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
}
.game-container {
  width: 800px; /* Match Phaser config width */
  height: 700px; /* Match Phaser config height */
  border: 1px solid #ccc;
  margin-bottom: 20px;
}
.ui-controls {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
}
.stake-selection button {
  margin: 0 5px;
  padding: 10px 15px;
  border: 1px solid #ddd;
  background-color: #f0f0f0;
  cursor: pointer;
}
.stake-selection button.active {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
}
.ui-controls button {
  padding: 10px 20px;
  font-size: 16px;
  cursor: pointer;
}
.game-info p {
  margin: 5px 0;
}
</style>
