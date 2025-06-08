<template>
  <div class="plinko-game">
    <div class="game-container" ref="gameContainer"></div>
    <div class="ui-controls">
      <!-- Stake selection and play button will go here -->
      <div class="stake-selection">
        <button @click="setStake('low')" :class="{ 'bg-green-500 text-white border-green-500 dark:bg-green-600 dark:border-green-600': currentStake === 'low' }" class="mx-1 px-4 py-2 border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded cursor-pointer hover:bg-green-500 hover:text-white hover:border-green-500 dark:hover:bg-green-600 dark:hover:border-green-600 transition-colors">Low (Green)</button>
        <button @click="setStake('medium')" :class="{ 'bg-yellow-500 text-white border-yellow-500 dark:bg-yellow-600 dark:border-yellow-600': currentStake === 'medium' }" class="mx-1 px-4 py-2 border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded cursor-pointer hover:bg-yellow-500 hover:text-white hover:border-yellow-500 dark:hover:bg-yellow-600 dark:hover:border-yellow-600 transition-colors">Medium (Yellow)</button>
        <button @click="setStake('high')" :class="{ 'bg-red-500 text-white border-red-500 dark:bg-red-600 dark:border-red-600': currentStake === 'high' }" class="mx-1 px-4 py-2 border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded cursor-pointer hover:bg-red-500 hover:text-white hover:border-red-500 dark:hover:bg-red-600 dark:hover:border-red-600 transition-colors">High (Red)</button>
      </div>
      <button @click="dropBallHandler" :disabled="isBallDropping" class="px-6 py-3 bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors">Drop Ball</button>
      <div class="game-info">
        <p class="text-gray-900 dark:text-gray-100">Current Stake: {{ currentStake }}</p>
        <p class="text-gray-900 dark:text-gray-100">Last Winnings: {{ lastWinnings }}x</p>
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
.game-info p {
  margin: 5px 0;
}
</style>
