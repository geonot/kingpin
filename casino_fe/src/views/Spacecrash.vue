<template>
  <div class="spacecrash-container">
    <h1>Spacecrash Game</h1>

    <!-- Game Section -->
    <div class="game-section">
      <!-- Phaser Game Container -->
      <div class="game-wrapper">
        <div id="spacecrash-game-container">
          <!-- Phaser game will attach here -->
          <p class="loading-text">Loading game...</p>
        </div>
        
        <!-- Game Status Overlay -->
        <div class="game-overlay">
          <div class="multiplier-display">
            <span class="multiplier-value">
              {{ currentMultiplierForDisplay }}x
            </span>
          </div>
          
          <!-- Game Status -->
          <div class="game-status">
            <span v-if="currentGame" class="status-badge" :class="getStatusClass(currentGame.status)">
              {{ getStatusText(currentGame.status) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Game Info Panel -->
      <div class="game-info-panel">
        <h3>Game Information</h3>
        <div class="info-grid">
          <div class="info-item">
            <label>Status:</label>
            <span>{{ currentGame?.status || 'Loading...' }}</span>
          </div>
          <div class="info-item">
            <label>Current Multiplier:</label>
            <span class="multiplier">{{ currentMultiplierForDisplay }}x</span>
          </div>
          <div v-if="currentGame?.crash_point" class="info-item">
            <label>Crashed at:</label>
            <span class="crash-point" :class="getCrashPointClass(currentGame.crash_point)">
              {{ currentGame.crash_point.toFixed(2) }}x
            </span>
          </div>
          <div v-if="isInGame" class="info-item">
            <label>Your Bet:</label>
            <span class="bet-amount">{{ activeBetAmount }} sats</span>
          </div>
          <div v-if="isInGame && activeAutoEjectAt" class="info-item">
            <label>Auto-Eject:</label>
            <span class="auto-eject">{{ activeAutoEjectAt }}x</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Controls Section -->
    <div class="controls-section">
      <!-- Betting Controls -->
      <div v-if="isBettingPhase" class="betting-panel">
        <h3>Place Your Bet</h3>
        <div class="betting-form">
          <div class="input-group">
            <label for="bet-amount">Bet Amount (sats):</label>
            <input 
              type="number" 
              id="bet-amount" 
              v-model.number="betAmount" 
              placeholder="Enter bet amount"
              min="1"
            />
          </div>
          <div class="input-group">
            <label for="auto-eject">Auto-Eject At (optional):</label>
            <input 
              type="number" 
              id="auto-eject" 
              v-model.number="autoEjectAt" 
              placeholder="e.g., 2.5" 
              step="0.01" 
              min="1.01" 
            />
          </div>
          <button class="bet-button" @click="placeBet" :disabled="bettingDisabled">
            {{ bettingDisabled ? 'Placing Bet...' : 'Place Bet' }}
          </button>
          <div v-if="betError" class="message error-message">{{ betError }}</div>
          <div v-if="betSuccessMessage" class="message success-message">{{ betSuccessMessage }}</div>
        </div>
      </div>

      <!-- Eject Controls -->
      <div v-else-if="isInGame" class="eject-panel">
        <h3>Your Active Bet</h3>
        <div class="bet-info">
          <p><strong>Bet Amount:</strong> {{ activeBetAmount }} sats</p>
          <p v-if="activeAutoEjectAt"><strong>Auto-Eject at:</strong> {{ activeAutoEjectAt }}x</p>
        </div>
        <button 
          class="eject-button" 
          @click="ejectBet" 
          :disabled="ejectDisabled || !isGameInProgress"
        >
          {{ ejectDisabled ? 'Ejecting...' : `Eject @ ${currentMultiplierForDisplay}x` }}
        </button>
        <div v-if="ejectMessage" class="message" :class="{'success-message': isEjectSuccess, 'error-message': !isEjectSuccess}">
          {{ ejectMessage }}
        </div>
      </div>

      <!-- Waiting State -->
      <div v-else class="waiting-panel">
        <h3>Waiting for Next Round</h3>
        <p>{{ getWaitingMessage() }}</p>
      </div>
    </div>

    <!-- Players List -->
    <div class="players-section">
      <h3>Players in Current Round</h3>
      <div v-if="currentGame && currentGame.player_bets && currentGame.player_bets.length > 0" class="players-table">
        <div class="table-header">
          <span>Player</span>
          <span>Bet (sats)</span>
          <span>Status</span>
          <span>Multiplier</span>
          <span>Winnings</span>
        </div>
        <div v-for="bet in currentGame.player_bets" :key="bet.user_id" class="table-row" :class="getPlayerBetClass(bet)">
          <span class="player-id">User {{ bet.user_id.toString().slice(-4) }}</span>
          <span class="bet-amount">{{ bet.bet_amount }}</span>
          <span class="status" :class="'status-' + bet.status.toLowerCase()">{{ bet.status }}</span>
          <span class="multiplier">
            <span v-if="bet.ejected_at">{{ bet.ejected_at.toFixed(2) }}x</span>
            <span v-else-if="isGameInProgress && bet.status === 'placed'">Playing...</span>
            <span v-else-if="currentGame.status === 'completed' && bet.status === 'busted'">Busted</span>
            <span v-else>-</span>
          </span>
          <span class="winnings">
            <span v-if="bet.win_amount !== null && bet.win_amount > 0" class="win-amount">+{{ bet.win_amount }}</span>
            <span v-else-if="bet.status === 'busted' && bet.win_amount === 0" class="loss">-{{ bet.bet_amount }}</span>
            <span v-else>-</span>
          </span>
        </div>
      </div>
      <p v-else class="empty-state">No active players in this round yet.</p>
    </div>

    <!-- Game History -->
    <div class="history-section">
      <h3>Recent Games</h3>
      <div v-if="gameHistory && gameHistory.length > 0" class="history-table">
        <div class="table-header">
          <span>Game ID</span>
          <span>Crash Point</span>
          <span>Ended At</span>
          <span>Public Seed</span>
        </div>
        <div v-for="game in gameHistory" :key="game.id" class="table-row">
          <span>#{{ game.id }}</span>
          <span class="crash-point" :class="getCrashPointClass(game.crash_point)">
            {{ game.crash_point ? game.crash_point.toFixed(2) + 'x' : 'N/A' }}
          </span>
          <span class="timestamp">{{ formatTime(game.game_end_time) }}</span>
          <span class="public-seed" :title="game.public_seed">
            {{ game.public_seed ? game.public_seed.substring(0, 12) + '...' : 'N/A' }}
          </span>
        </div>
      </div>
      <p v-else class="empty-state">No game history available yet.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onUnmounted, computed, watch } from 'vue';
import api from '@/services/api'; // Assuming you have an api service module
import Phaser from 'phaser';
import SpacecrashBootScene from '@/phaser/scenes/SpacecrashBootScene';
import SpacecrashPreloadScene from '@/phaser/scenes/SpacecrashPreloadScene';
import SpacecrashGameScene from '@/phaser/scenes/SpacecrashGameScene';
import SpacecrashUIScene from '@/phaser/scenes/SpacecrashUIScene';
import { useWebSocket } from '@/composables/useWebSocket';
import { useStore } from 'vuex';

// Store and WebSocket
const store = useStore();
const { isConnected, connect, joinRoom, leaveRoom, on, off } = useWebSocket();

// Phaser game instance
const game = shallowRef(null); // Use shallowRef for Phaser game instance

// Game State
const currentGame = ref(null); // Holds data for the current/latest game from API
const gameHistory = ref([]); // Holds list of recent games from API
const currentMultiplier = ref(1.0); // Primarily for display when game is active, synced from currentGame or Phaser

// Betting
const betAmount = ref(100); // Default bet amount
const autoEjectAt = ref(null); // Default auto-eject
const bettingDisabled = ref(false);
const betError = ref('');
const betSuccessMessage = ref('');

// Active Bet Info (after placing a bet)
const activeBetAmount = ref(0);
const activeAutoEjectAt = ref(null);
const isInGame = ref(false); // Is the current user actively in the game round?

// Ejecting
const ejectDisabled = ref(false);
const ejectMessage = ref('');
const isEjectSuccess = ref(false);


// --- Computed Properties ---
const isBettingPhase = computed(() => currentGame.value && currentGame.value.status === 'betting');
const isGameInProgress = computed(() => currentGame.value && currentGame.value.status === 'in_progress');
const currentMultiplierForDisplay = computed(() => { // Used for the EJECT button text
  if (isGameInProgress.value && currentGame.value && typeof currentGame.value.current_multiplier === 'number') {
    return currentGame.value.current_multiplier.toFixed(2);
  }
  return currentMultiplier.value.toFixed(2); // Fallback to locally tracked multiplier
});

// --- Helper methods for styling and display ---
function getPlayerBetClass(bet) {
  return `bet-status-${bet.status.toLowerCase()}`;
}

function getCrashPointClass(crashPoint) {
  if (crashPoint === null || crashPoint === undefined) return '';
  return crashPoint >= 2.0 ? 'crash-point-good' : 'crash-point-bad';
}

function getStatusClass(status) {
  return `status-${status}`;
}

function getStatusText(status) {
  switch (status) {
    case 'betting': return 'Betting Phase';
    case 'in_progress': return 'Game Active';
    case 'completed': return 'Game Completed';
    default: return status;
  }
}

function getWaitingMessage() {
  if (!currentGame.value) return 'Loading game state...';
  if (currentGame.value.status === 'completed') return 'Waiting for next betting phase...';
  if (currentGame.value.status === 'in_progress') return 'Game in progress. Wait for next round to bet.';
  return 'Waiting for game to start...';
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString();
}

// --- API Calls & Handlers ---
async function fetchCurrentGame() {
  try {
    const response = await api.get('/spacecrash/current_game');
    if (response.data.status && response.data.game) {
      const oldGameStatus = currentGame.value?.status;
      const newGameData = response.data.game;
      currentGame.value = newGameData; // Update reactive ref

      // Phaser game instance interaction
      if (game.value && game.value.scene && game.value.scene.isActive('SpacecrashGameScene')) {
        game.value.registry.events.emit('updateGameStatus', newGameData); // General update

        if (newGameData.status === 'in_progress' && oldGameStatus !== 'in_progress') {
          console.log("Vue: Game status changed to in_progress. Emitting START_GAME to Phaser.");
          game.value.registry.events.emit('START_GAME', {});
        } else if (newGameData.status === 'completed' && oldGameStatus === 'in_progress') {
          console.log("Vue: Game status changed to completed. Emitting CRASH_AT to Phaser.");
          game.value.registry.events.emit('CRASH_AT', { crashPoint: newGameData.crash_point });
        } else if (newGameData.status === 'betting' && oldGameStatus !== 'betting') {
           console.log("Vue: Game status changed to betting. Emitting RESET_GAME_VIEW to Phaser.");
          game.value.registry.events.emit('RESET_GAME_VIEW');
        }
      }

      // Update Vue's local currentMultiplier for display purposes
      if (newGameData.status === 'in_progress' && newGameData.current_multiplier) {
        currentMultiplier.value = newGameData.current_multiplier;
      } else if (newGameData.status === 'completed' && newGameData.crash_point) {
        currentMultiplier.value = newGameData.crash_point;
      } else if (newGameData.status === 'betting') {
        currentMultiplier.value = 1.0;
      }
      
      // Simplified logic for isInGame based on current user's bet status in the received game data
      // This would require knowing the current user's ID. For now, this part is illustrative.
      // const currentUserId = store.state.user?.id; // Example: Get user ID from Vuex
      // if (currentUserId && newGameData.player_bets) {
      //   const myBet = newGameData.player_bets.find(b => b.user_id === currentUserId);
      //   if (myBet && myBet.status === 'placed' && newGameData.status === 'in_progress') {
      //     isInGame.value = true;
      //     activeBetAmount.value = myBet.bet_amount;
      //   } else {
      //     isInGame.value = false;
      //   }
      // }


    } else {
      // If API reports no game or error, reflect that in Vue state
      if (currentGame.value && game.value && game.value.scene && game.value.scene.isActive('SpacecrashGameScene')) {
         // If there was a game and now there isn't, reset Phaser view
        game.value.registry.events.emit('RESET_GAME_VIEW');
      }
      currentGame.value = null;
    }
  } catch (error) {
    console.error('Error fetching current game state:', error);
    if (currentGame.value && game.value && game.value.scene && game.value.scene.isActive('SpacecrashGameScene')) {
      game.value.registry.events.emit('RESET_GAME_VIEW');
    }
    currentGame.value = null;
  }
}

async function fetchGameHistory() {
  try {
    const response = await api.get('/spacecrash/history');
    if (response.data.status && response.data.history) {
      gameHistory.value = response.data.history;
    }
  } catch (error) {
    console.error('Error fetching game history:', error);
  }
}

async function placeBet() {
  betError.value = '';
  betSuccessMessage.value = '';
  bettingDisabled.value = true;
  try {
    const payload = {
      bet_amount: betAmount.value,
    };
    if (autoEjectAt.value && autoEjectAt.value >= 1.01) {
      payload.auto_eject_at = autoEjectAt.value;
    }
    const response = await api.post('/spacecrash/bet', payload);
    if (response.data.status) {
      betSuccessMessage.value = `Bet placed successfully for ${response.data.bet.bet_amount} sats!`;
      activeBetAmount.value = response.data.bet.bet_amount;
      activeAutoEjectAt.value = response.data.bet.auto_eject_at; // Assuming API returns this
      isInGame.value = true;
      
      // If the game immediately starts or is already in progress due to this bet (simplified flow)
      // The real-time updates will come via WebSocket, so we don't need to poll
      // await fetchCurrentGame(); // Removed - WebSocket will handle updates
      
    } else {
      betError.value = response.data.status_message || 'Failed to place bet.';
    }
  } catch (error) {
    console.error('Error placing bet:', error);
    betError.value = error.response?.data?.status_message || 'An error occurred while placing your bet.';
  } finally {
    bettingDisabled.value = false;
  }
}

async function ejectBet() {
  ejectMessage.value = '';
  ejectDisabled.value = true; // Disable button during API call
  isEjectSuccess.value = false;
  try {
    const response = await api.post('/spacecrash/eject'); // API call
    if (response.data.status) {
      ejectMessage.value = `Successfully ejected at ${response.data.ejected_at.toFixed(2)}x! You won ${response.data.win_amount} sats.`;
      isEjectSuccess.value = true;

      // Emit event to Phaser for visual feedback
      if (game.value && game.value.registry) {
        game.value.registry.events.emit('PLAYER_SUCCESSFULLY_EJECTED');
      }

      isInGame.value = false; // User is now out of the current round
      // Sound play is moved to Phaser's handlePlayerEjectedVisuals
    } else {
      ejectMessage.value = response.data.status_message || 'Failed to eject.';
      isEjectSuccess.value = false;
      if (response.data.status_message && (response.data.status_message.toLowerCase().includes('busted') || response.data.status_message.toLowerCase().includes('crashed'))) {
        isInGame.value = false; // User is out (busted)
      }
    }
    // Real-time updates will come via WebSocket, so we don't need to poll
    // await fetchCurrentGame(); // Removed - WebSocket will handle updates
    
    // TODO: Refresh user balance from store if not handled by WebSocket updates implicitly
    // const authStore = useStore(); authStore.dispatch('fetchUser');
  } catch (error) {
    console.error('Error ejecting bet:', error);
    ejectMessage.value = error.response?.data?.status_message || 'An error occurred while ejecting.';
    isEjectSuccess.value = false;
     if (error.response?.data?.status_message && error.response.data.status_message.toLowerCase().includes('busted')) {
        isInGame.value = false; 
      }
  } finally {
    ejectDisabled.value = false; // Re-enable button
  }
}

// --- Lifecycle Hooks & Watchers ---

// WebSocket event handlers
function handleSpacecrashUpdate(data) {
  console.log('Received spacecrash update:', data);
  
  if (data.game) {
    const oldGameStatus = currentGame.value?.status;
    const newGameData = data.game;
    currentGame.value = newGameData; // Update reactive ref

    // Check if current user is in this game
    const currentUserId = store.state.user?.id;
    let userBet = null;
    
    if (currentUserId && newGameData.player_bets) {
      userBet = newGameData.player_bets.find(bet => bet.user_id === currentUserId);
    }

    // Update user's in-game state based on their bet status
    if (userBet) {
      isInGame.value = userBet.status === 'placed'; // User is in game if bet is still placed
      activeBetAmount.value = userBet.bet_amount;
      activeAutoEjectAt.value = userBet.auto_eject_at;
      
      // Handle bet status changes
      if (userBet.status === 'ejected' && userBet.win_amount > 0) {
        ejectMessage.value = `Successfully ejected at ${userBet.ejected_at.toFixed(2)}x! You won ${userBet.win_amount} sats.`;
        isEjectSuccess.value = true;
      } else if (userBet.status === 'busted') {
        ejectMessage.value = `Game crashed at ${newGameData.crash_point.toFixed(2)}x. You busted.`;
        isEjectSuccess.value = false;
      }
    } else if (newGameData.status === 'betting') {
      // Reset user state for new betting phase
      isInGame.value = false;
      activeBetAmount.value = 0;
      activeAutoEjectAt.value = null;
      ejectMessage.value = '';
      betSuccessMessage.value = '';
      betError.value = '';
    }

    // Phaser game instance interaction
    if (game.value && game.value.scene && game.value.scene.isActive('SpacecrashGameScene')) {
      game.value.registry.events.emit('updateGameStatus', newGameData); // General update

      if (newGameData.status === 'in_progress' && oldGameStatus !== 'in_progress') {
        console.log("Vue: Game status changed to in_progress. Emitting START_GAME to Phaser.");
        game.value.registry.events.emit('START_GAME', {});
      } else if (newGameData.status === 'completed' && oldGameStatus === 'in_progress') {
        console.log("Vue: Game status changed to completed. Emitting CRASH_AT to Phaser.");
        game.value.registry.events.emit('CRASH_AT', { crashPoint: newGameData.crash_point });
      } else if (newGameData.status === 'betting' && oldGameStatus !== 'betting') {
         console.log("Vue: Game status changed to betting. Emitting RESET_GAME_VIEW to Phaser.");
        game.value.registry.events.emit('RESET_GAME_VIEW');
      }
    }

    // Update Vue's local currentMultiplier for display purposes
    if (newGameData.status === 'in_progress' && newGameData.current_multiplier) {
      currentMultiplier.value = newGameData.current_multiplier;
    } else if (newGameData.status === 'completed' && newGameData.crash_point) {
      currentMultiplier.value = newGameData.crash_point;
    } else if (newGameData.status === 'betting') {
      currentMultiplier.value = 1.0;
    }
  }
}

onMounted(() => {
  // Fetch game history (non-real-time data)
  fetchGameHistory();

  // Set up WebSocket connection for spacecrash if user is authenticated
  if (store.state.isAuthenticated && store.state.user) {
    // Connect WebSocket with user authentication
    connect(store.state.user);
    
    // Join spacecrash room for real-time updates
    joinRoom('spacecrash');
    
    // Set up WebSocket event listeners
    on('spacecrash:update', handleSpacecrashUpdate);
  } else {
    // If not authenticated, still fetch initial game state once
    fetchCurrentGame();
  }

  // Initialize Phaser game
  const config = {
    type: Phaser.AUTO,
    parent: 'spacecrash-game-container',
    width: 800, // Adjust as needed, can be responsive
    height: 450, // Adjusted for a 16:9 feel within the 400px container, or match container
    backgroundColor: '#000022', // Dark blue/black space theme
    physics: {
      default: 'arcade',
      arcade: {
        gravity: { y: 0 },
        debug: process.env.NODE_ENV === 'development' // Show debug outlines in dev
      }
    },
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH
    },
    scene: [SpacecrashBootScene, SpacecrashPreloadScene, SpacecrashGameScene, SpacecrashUIScene]
  };

  game.value = new Phaser.Game(config);

  // Setup event listeners from Phaser to Vue
  if (game.value && game.value.registry) { // Check if Phaser game is initialized
    game.value.registry.events.on('PHASER_GAME_OVER', (data) => {
      console.log('Vue: PHASER_GAME_OVER event received', data);
      // This event is more for Phaser to inform Vue that its animation/state is "game over".
      // Vue's game logic (like isInGame) should primarily be driven by WebSocket updates.
      // However, we can use this to update UI elements that reflect the crash immediately.
      if (currentGame.value && data.crashPoint) {
        currentGame.value.crash_point = data.crashPoint; // Update local model
        currentGame.value.status = 'completed'; // Assume it's completed
        currentMultiplier.value = data.crashPoint;
      }
      // If the user was still "inGame" according to Vue's state, mark them as busted now.
      if(isInGame.value) {
        ejectMessage.value = `Game crashed at ${data.crashPoint.toFixed(2)}x. You busted.`;
        isEjectSuccess.value = false;
        isInGame.value = false;
      }
    });
  } else {
    // Retry setting up listeners if game initializes late, or handle error
    console.warn("Phaser game instance not ready in onMounted to set up listeners.");
  }
});

onUnmounted(() => {
  // Clean up WebSocket listeners
  off('spacecrash:update', handleSpacecrashUpdate);
  leaveRoom();
  
  if (game.value) {
    // Clean up Phaser-to-Vue event listeners
    if (game.value.registry) {
        game.value.registry.events.off('PHASER_GAME_OVER');
    }
    game.value.destroy(true);
    game.value = null;
    console.log('Phaser game destroyed');
  }
});

// Watch for game status changes to reset UI elements
watch(() => currentGame.value?.status, (newStatus, oldStatus) => {
  if (newStatus === 'betting' && oldStatus !== 'betting') {
    isInGame.value = false; // Reset user's in-game status
    betSuccessMessage.value = ''; // Clear previous bet success
    betError.value = '';
    ejectMessage.value = '';
    // Potentially reset betAmount and autoEjectAt if desired
  } else if (newStatus === 'completed' && isInGame.value) {
    // If game completed and user was still "inGame" (didn't eject or get busted status explicitly)
    // it means they busted.
    isInGame.value = false;
    ejectMessage.value = `Game crashed at ${currentGame.value.crash_point.toFixed(2)}x. You busted.`;
    isEjectSuccess.value = false;
  }
});

</script>

<style scoped>
.spacecrash-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Arial', sans-serif;
  @apply bg-gradient-to-br from-gray-900 to-blue-900 dark:from-gray-900 dark:to-blue-900;
  min-height: 100vh;
  @apply text-gray-100 dark:text-gray-100;
}

.spacecrash-container h1 {
  text-align: center;
  margin-bottom: 30px;
  @apply text-green-400 dark:text-green-400;
  text-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
}

/* Game Section Layout */
.game-section {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
  margin-bottom: 30px;
}

@media (min-width: 1024px) {
  .game-section {
    grid-template-columns: 2fr 1fr;
  }
}

.game-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  @apply border-2 border-gray-600 dark:border-gray-600;
}

#spacecrash-game-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #000033 0%, #000066 100%);
}

.loading-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 1.2em;
  @apply text-gray-400 dark:text-gray-400;
  text-align: center;
}

.game-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 10;
}

.multiplier-display {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: clamp(2rem, 8vw, 4rem);
  font-weight: 900;
  @apply text-green-400 dark:text-green-400;
  text-shadow: 
    0 0 20px rgba(0, 255, 136, 0.8),
    0 0 40px rgba(0, 255, 136, 0.4);
  letter-spacing: 0.1em;
}

.game-status {
  position: absolute;
  top: 15px;
  right: 15px;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: bold;
  font-size: 0.9em;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  backdrop-filter: blur(10px);
}

.status-betting {
  @apply bg-orange-500 text-black dark:bg-orange-500 dark:text-black;
  box-shadow: 0 0 15px rgba(255, 165, 0, 0.5);
}

.status-in_progress {
  @apply bg-green-400 text-black dark:bg-green-400 dark:text-black;
  box-shadow: 0 0 15px rgba(0, 255, 136, 0.5);
}

.status-completed {
  @apply bg-red-500 text-white dark:bg-red-500 dark:text-white;
  box-shadow: 0 0 15px rgba(255, 68, 68, 0.5);
}

/* Game Info Panel */
.game-info-panel {
  padding: 20px;
  border-radius: 12px;
  @apply bg-gray-800/80 dark:bg-gray-800/80 border border-gray-600/30 dark:border-gray-600/30;
  backdrop-filter: blur(10px);
  height: fit-content;
}

.game-info-panel h3 {
  margin: 0 0 15px 0;
  @apply text-green-400 dark:text-green-400;
  font-size: 1.2em;
}

.info-grid {
  display: grid;
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  @apply border-b border-gray-600/30 dark:border-gray-600/30;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item label {
  @apply text-gray-300 dark:text-gray-300;
  font-size: 0.9em;
}

.info-item span {
  font-weight: bold;
}

.multiplier {
  @apply text-green-400 dark:text-green-400;
}

.crash-point-good {
  @apply text-green-500 dark:text-green-400;
  font-weight: bold;
}

.crash-point-bad {
  @apply text-red-500 dark:text-red-400;
  font-weight: bold;
}

/* Controls Section */
.controls-section {
  margin: 30px 0;
}

.betting-panel, .eject-panel, .waiting-panel {
  padding: 25px;
  border-radius: 12px;
  @apply bg-gray-800/80 dark:bg-gray-800/80 border border-gray-600/30 dark:border-gray-600/30;
  backdrop-filter: blur(10px);
  margin-bottom: 20px;
}

.betting-panel h3, .eject-panel h3, .waiting-panel h3 {
  margin: 0 0 20px 0;
  @apply text-green-400 dark:text-green-400;
  font-size: 1.3em;
}

.betting-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  align-items: end;
}

@media (max-width: 768px) {
  .betting-form {
    grid-template-columns: 1fr;
  }
}

.input-group {
  display: flex;
  flex-direction: column;
}

.input-group label {
  margin-bottom: 8px;
  font-weight: 600;
  @apply text-gray-200 dark:text-gray-200;
  font-size: 0.9em;
}

input[type="number"] {
  padding: 12px 15px;
  @apply border-2 border-gray-600 dark:border-gray-600 bg-gray-700/50 dark:bg-gray-700/50 text-white dark:text-white;
  border-radius: 8px;
  font-size: 1em;
  transition: all 0.3s ease;
}

input[type="number"]:focus {
  outline: none;
  @apply border-green-400 dark:border-green-400;
  box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
}

/* Buttons */
button {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 1em;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.bet-button {
  @apply bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 dark:from-green-500 dark:to-green-600 dark:hover:from-green-600 dark:hover:to-green-700 text-black dark:text-black;
  grid-column: 1 / -1;
}

.bet-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 255, 136, 0.4);
}

.eject-button {
  @apply bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 dark:from-orange-500 dark:to-red-500 dark:hover:from-orange-600 dark:hover:to-red-600 text-white dark:text-white;
  font-size: 1.1em;
  padding: 15px 30px;
}

.eject-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(255, 107, 53, 0.4);
}

button:disabled {
  @apply bg-gray-600 text-gray-400 dark:bg-gray-600 dark:text-gray-400;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.bet-info {
  @apply bg-gray-700/50 dark:bg-gray-700/50;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 15px;
}

.bet-info p {
  margin: 5px 0;
}

/* Tables */
.players-section, .history-section {
  margin: 30px 0;
  padding: 25px;
  border-radius: 12px;
  @apply bg-gray-800/80 dark:bg-gray-800/80 border border-gray-600/30 dark:border-gray-600/30;
  backdrop-filter: blur(10px);
}

.players-section h3, .history-section h3 {
  margin: 0 0 20px 0;
  @apply text-green-400 dark:text-green-400;
  font-size: 1.3em;
}

.players-table, .history-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin-top: 15px;
  border-radius: 8px;
  overflow: hidden;
}

.table-header {
  @apply bg-gradient-to-r from-gray-700 to-gray-600 dark:from-gray-700 dark:to-gray-600 text-green-400 dark:text-green-400;
  font-weight: bold;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  padding: 15px 10px;
  font-size: 0.9em;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  padding: 12px 10px;
  @apply bg-gray-700/50 dark:bg-gray-700/50 border-b border-gray-600/30 dark:border-gray-600/30;
  transition: background-color 0.3s ease;
}

.table-row:hover {
  @apply bg-gray-600/70 dark:bg-gray-600/70;
}

.table-row:last-child {
  border-bottom: none;
}

.table-row span {
  display: flex;
  align-items: center;
  font-size: 0.9em;
}

.player-id {
  font-family: monospace;
  @apply text-gray-300 dark:text-gray-300;
}

.status-placed { 
  @apply text-orange-400 dark:text-orange-400;
  font-weight: bold;
}

.status-ejected { 
  @apply text-green-500 dark:text-green-400;
  font-weight: bold;
}

.status-busted { 
  @apply text-red-500 dark:text-red-400;
  font-weight: bold;
}

.win-amount { 
  @apply text-green-500 dark:text-green-400;
  font-weight: bold;
}

.loss { 
  @apply text-red-500 dark:text-red-400;
  font-weight: bold;
}

.public-seed {
  font-family: monospace;
  font-size: 0.8em;
  @apply text-gray-400 dark:text-gray-400;
  cursor: help;
}

.timestamp {
  font-size: 0.85em;
  @apply text-gray-300 dark:text-gray-300;
}

.empty-state {
  @apply text-gray-400 dark:text-gray-400;
  font-style: italic;
  text-align: center;
  padding: 30px;
}

/* Messages */
.message {
  margin-top: 15px;
  padding: 12px 15px;
  border-radius: 8px;
  font-weight: 500;
}

.error-message {
  @apply bg-red-900/20 border border-red-500/30 text-red-400 dark:bg-red-900/20 dark:border-red-500/30 dark:text-red-400;
}

.success-message {
  @apply bg-green-900/20 border border-green-500/30 text-green-400 dark:bg-green-900/20 dark:border-green-500/30 dark:text-green-400;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .spacecrash-container {
    padding: 15px;
  }
  
  .game-wrapper {
    aspect-ratio: 4 / 3;
  }
  
  .multiplier-display {
    font-size: 2rem;
  }
  
  .table-header, .table-row {
    grid-template-columns: 1fr 1fr 1fr;
    font-size: 0.8em;
  }
  
  .table-row span:nth-child(4),
  .table-row span:nth-child(5),
  .table-header span:nth-child(4),
  .table-header span:nth-child(5) {
    display: none;
  }
}
</style>
