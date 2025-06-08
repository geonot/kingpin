<template>
  <div class="roulette-game container mx-auto p-4">
    <h1 class="text-3xl font-bold mb-6 text-center">Roulette</h1>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- Game Info Section -->
      <div class="md:col-span-1 bg-gray-800 p-4 rounded-lg shadow-xl">
        <h2 class="text-xl font-semibold mb-3">Game Info</h2>
        <div v.if="user" class="mb-2">
          Balance: <span class="font-mono text-yellow-400">{{ formattedBalance }}</span>
        </div>
        <div class="mb-2">
          Current Bet: <span class="font-mono text-yellow-400">{{ currentBetAmount }}</span>
        </div>
        <div class="mb-4">
          Selected Bet Type: <span class="text-green-400">{{ selectedBetType || 'None' }}</span>
          <span v-if="selectedBetValue" class="text-green-400">: {{ selectedBetValue }}</span>
        </div>
        <div v-if="lastWinningNumber !== null" class="mb-2">
          Last Winning Number: <span :class="getNumberColorClass(lastWinningNumber)">{{ lastWinningNumber }}</span>
        </div>
        <div v-if="message" class="mt-4 p-3 rounded text-center" :class="messageType === 'error' ? 'bg-red-500' : 'bg-blue-500'">
          {{ message }}
        </div>
      </div>

      <!-- Phaser Game Canvas Section -->
      <div id="phaser-roulette-container" class="md:col-span-2 bg-gray-900 rounded-lg shadow-2xl flex items-center justify-center min-h-[400px] md:min-h-[500px]">
        <!-- Phaser game will be injected here -->
        <p class="text-gray-500">Loading Roulette Game...</p>
      </div>
    </div>

    <!-- Betting Controls Section -->
    <div class="mt-6 bg-gray-800 p-6 rounded-lg shadow-xl">
      <h2 class="text-xl font-semibold mb-4 text-center">Place Your Bet</h2>
      <div class="flex flex-col sm:flex-row items-center justify-center gap-4 mb-4">
        <div>
          <label for="betAmount" class="block text-sm font-medium text-gray-300 mb-1">Bet Amount:</label>
          <input type="number" id="betAmount" v.model.number="betAmountInput" min="1" class="bg-gray-700 border border-gray-600 text-white rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500" placeholder="Enter amount">
        </div>
        <button @click="placeBet" :disabled="!canPlaceBet || isLoading" class="bg-green-600 hover:bg-green-700 dark:bg-green-500 dark:hover:bg-green-600 text-white dark:text-white font-bold py-2 px-6 rounded-md shadow-md disabled:opacity-50 disabled:cursor-not-allowed border border-green-600 dark:border-green-500">
          <span v-if="isLoading">Spinning...</span>
          <span v-else>Place Bet & Spin</span>
        </button>
      </div>
      <p class="text-xs text-gray-400 dark:text-gray-500 text-center mt-2">Select bet type on the table above (table to be implemented in Phaser).</p>

      <!-- Simple Bet Type Buttons (Example) -->
      <div class="mt-4 flex flex-wrap justify-center gap-2">
        <button @click="selectBetType('red', null)" class="bg-red-600 hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-600 text-white dark:text-white border border-red-600 dark:border-red-500 px-3 py-1 rounded">Bet Red</button>
        <button @click="selectBetType('black', null)" class="bg-gray-800 hover:bg-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600 text-white dark:text-white border border-gray-800 dark:border-gray-700 px-3 py-1 rounded">Bet Black</button>
        <button @click="selectBetType('even', null)" class="bg-gray-500 hover:bg-gray-600 dark:bg-gray-600 dark:hover:bg-gray-500 text-white dark:text-white border border-gray-500 dark:border-gray-600 px-3 py-1 rounded">Bet Even</button>
        <button @click="selectBetType('odd', null)" class="bg-gray-500 hover:bg-gray-600 dark:bg-gray-600 dark:hover:bg-gray-500 text-white dark:text-white border border-gray-500 dark:border-gray-600 px-3 py-1 rounded">Bet Odd</button>
        <!-- Add more for columns, dozens, specific numbers as needed -->
      </div>
    </div>

  </div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex';
import api from '@/services/api'; // Assuming you have an API service
import Phaser from 'phaser';
import RouletteScene from '@/phaser/scenes/RouletteScene'; // Adjust path if needed

// Placeholder for Phaser game instance
let gameInstance = null;

export default {
  name: 'RouletteGame',
  data() {
    return {
      betAmountInput: 10, // Default bet amount
      currentBetAmount: 0,
      selectedBetType: null, // e.g., 'red', 'straight_up', 'column_1'
      selectedBetValue: null, // e.g., 7 for straight_up, 1 for column_1

      isLoading: false,
      message: '',
      messageType: 'info', // 'info' or 'error'
      lastWinningNumber: null,

      // Roulette number colors for display
      redNumbers: [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36],
      blackNumbers: [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35],
      greenNumber: 0,
    };
  },
  computed: {
    ...mapGetters(['user', 'isAuthenticated']), // Assuming Vuex store for user state
    formattedBalance() {
      return this.user && this.user.balance !== undefined ? parseFloat(this.user.balance).toFixed(2) : 'N/A';
    },
    canPlaceBet() {
      return this.betAmountInput > 0 && this.selectedBetType && !this.isLoading;
    }
  },
  methods: {
    ...mapActions(['fetchUser']), // Action to refresh user balance

    selectBetType(type, value = null) {
      this.selectedBetType = type;
      this.selectedBetValue = value;
      this.currentBetAmount = this.betAmountInput; // Lock in bet amount when type is selected
      this.message = `Selected ${type} ${value !== null ? value : ''}. Amount: ${this.currentBetAmount}`;
      this.messageType = 'info';
    },

    async placeBet() {
      if (!this.canPlaceBet) {
        this.message = 'Please set a valid bet amount and select a bet type.';
        this.messageType = 'error';
        return;
      }
      this.isLoading = true;
      this.message = 'Spinning the wheel...';
      this.messageType = 'info';

      try {
        const response = await api.post('/roulette/bet', {
          bet_amount: this.currentBetAmount,
          bet_type: this.selectedBetType,
          bet_value: this.selectedBetValue
        });

        this.lastWinningNumber = response.data.winning_number;
        const payout = response.data.payout;

        if (payout > 0) {
          this.message = `The number is ${this.lastWinningNumber}! You won ${payout.toFixed(2)}!`;
        } else {
          this.message = `The number is ${this.lastWinningNumber}. Better luck next time!`;
        }
        this.messageType = 'info';

        // Update user balance from Vuex store or directly if API returns it
        // await this.fetchUser(); // Or use response.data.new_balance
        if (response.data.new_balance !== undefined) {
             this.$store.commit('setUser', { ...this.user, balance: response.data.new_balance });
        }

        // Call Phaser scene to animate the spin
        if (gameInstance && gameInstance.scene.isActive('RouletteScene')) {
            const rouletteScene = gameInstance.scene.getScene('RouletteScene');
            if (rouletteScene && rouletteScene.startWheelSpin) {
                rouletteScene.startWheelSpin(this.lastWinningNumber);
            } else {
                console.warn('RouletteScene or startWheelSpin method not available.');
            }
        }

      } catch (error) {
        this.message = error.response?.data?.error || 'Failed to place bet.';
        this.messageType = 'error';
        this.lastWinningNumber = null; // Reset on error
      } finally {
        this.isLoading = false;
        // Reset selection after bet? Or let user re-bet?
        // this.selectedBetType = null;
        // this.selectedBetValue = null;
        // this.currentBetAmount = 0;
      }
    },

    initPhaserGame() {
      if (gameInstance) {
        console.log('Destroying existing Phaser game instance.');
        gameInstance.destroy(true);
        gameInstance = null;
      }

      const phaserContainer = document.getElementById('phaser-roulette-container');
      if (!phaserContainer) {
        console.error('Phaser container #phaser-roulette-container not found.');
        this.message = 'Error initializing game graphics.';
        this.messageType = 'error';
        return;
      }

      // Ensure container is clear (Phaser might add multiple canvases if not careful on re-init)
      while (phaserContainer.firstChild) {
        phaserContainer.removeChild(phaserContainer.firstChild);
      }

      const config = {
        type: Phaser.AUTO, // Or Phaser.CANVAS, Phaser.WEBGL
        parent: 'phaser-roulette-container', // ID of the div
        width: phaserContainer.clientWidth || 800, // Use container width or default
        height: phaserContainer.clientHeight || 500, // Use container height or default
        backgroundColor: '#2d2d2d',
        scene: [RouletteScene],
        physics: { // Optional: if you need physics later
            default: 'arcade',
            arcade: {
                debug: false // Set to true for debugging physics bodies
            }
        },
        callbacks: {
            postBoot: (game) => {
                // Make sure scene is ready before trying to access it
                const scene = game.scene.getScene('RouletteScene');
                if (scene) {
                    // Pass the Vue component instance to the scene
                    // Note: Scene's init method is better for this.
                } else {
                    console.error("RouletteScene not found after boot.");
                }
            }
        }
      };

      // Pass Vue component instance to the scene via scene's init method
      config.scene.forEach(sceneClass => {
          if (Object.prototype.hasOwnProperty.call(sceneClass, 'prototype') && sceneClass.prototype instanceof Phaser.Scene) {
              // This is a common way to pass initial data to the first scene
              // Phaser will call scene.init(data)
              config.scene[config.scene.indexOf(sceneClass)] = {
                  type: sceneClass,
                  key: sceneClass.name || 'RouletteScene', // Ensure a key if not named
                  data: { vueComponent: this } // Pass Vue instance here
              };
          } else if (typeof sceneClass === 'object' && sceneClass.scene) { // If already an object config
              sceneClass.data = { ...sceneClass.data, vueComponent: this };
          }
      });

      // Check if width or height is zero, provide defaults to avoid Phaser error
      if (config.width === 0) config.width = 800;
      if (config.height === 0) config.height = 500;


      console.log('Initializing Phaser game with config:', config);
      try {
        gameInstance = new Phaser.Game(config);
        // Remove the "Loading Roulette Game..." text once Phaser is supposed to take over
        const loadingText = phaserContainer.querySelector('p');
        if (loadingText) {
            loadingText.style.display = 'none';
        }
      } catch (error) {
        console.error("Error creating Phaser game instance:", error);
        this.message = "Failed to load game graphics. " + error.message;
        this.messageType = 'error';
      }
    },

    destroyPhaserGame() {
      if (gameInstance) {
        gameInstance.destroy(true);
        gameInstance = null;
        console.log('Phaser game destroyed.');
      }
    },

    getNumberColorClass(number) {
      if (this.redNumbers.includes(number)) return 'text-red-500 font-bold';
      if (this.blackNumbers.includes(number)) return 'text-gray-300 font-bold'; // Black might not show well on dark, use light gray
      if (number === this.greenNumber) return 'text-green-500 font-bold';
      return 'text-white';
    }
  },
  mounted() {
    if (!this.isAuthenticated) {
      // Redirect to login or show message if user is not authenticated
      // this.$router.push('/login');
      this.message = "Please log in to play.";
      this.messageType = 'error';
    }
    this.initPhaserGame();
  },
  beforeUnmount() {
    this.destroyPhaserGame();
  }
};
</script>

<style scoped>
/* Scoped styles for Roulette.vue */
#phaser-roulette-container canvas {
  /* Ensure canvas scales nicely if Phaser doesn't handle it internally */
  max-width: 100%;
  height: auto;
}
.font-mono { /* Ensure Tailwind's font-mono is available if used */
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
</style>
