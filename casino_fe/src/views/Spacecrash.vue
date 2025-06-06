<template>
  <div class="spacecrash-container">
    <h1>Spacecrash Game</h1>

    <div class="game-area">
      <div id="spacecrash-game-container">
        <!-- Phaser game will attach here -->
        <p>Loading game...</p>
      </div>
      <div class="game-info">
        <h2>Game Information</h2>
        <div v-if="currentGame">
          <p>Status: {{ currentGame.status }}</p>
          <p>Multiplier: {{ currentGame.current_multiplier ? currentGame.current_multiplier.toFixed(2) + 'x' : 'Waiting...' }}</p>
          <p v.if="currentGame.crash_point">Crashed at: {{ currentGame.crash_point.toFixed(2) }}x</p>
        </div>
        <div v-else>
          <p>Fetching game state...</p>
        </div>
      </div>
    </div>

    <div class="controls-area">
      <h2>Place Your Bet</h2>
      <div v-if="isBettingPhase" class="betting-form">
        <div>
          <label for="bet-amount">Bet Amount (sats):</label>
          <input type="number" id="bet-amount" v-model.number="betAmount" placeholder="Enter bet amount" />
        </div>
        <div>
          <label for="auto-eject">Auto-Eject At (multiplier):</label>
          <input type="number" id="auto-eject" v.model.number="autoEjectAt" placeholder="e.g., 2.5" step="0.01" min="1.01" />
        </div>
        <button @click="placeBet" :disabled="bettingDisabled">Place Bet</button>
        <div v-if="betError" class="error-message">{{ betError }}</div>
        <div v-if="betSuccessMessage" class="success-message">{{ betSuccessMessage }}</div>
      </div>
      <div v-else-if="isInGame" class="eject-form">
        <p>Bet Placed: {{ activeBetAmount }} sats</p>
        <p v-if="activeAutoEjectAt">Auto-ejecting at: {{ activeAutoEjectAt }}x</p>
        <button @click="ejectBet" :disabled="ejectDisabled">Eject @ {{ currentMultiplierForDisplay }}x</button>
        <div v-if="ejectMessage" :class="{'success-message': isEjectSuccess, 'error-message': !isEjectSuccess}">{{ ejectMessage }}</div>
      </div>
      <div v-else>
        <p>Waiting for betting phase or game to start...</p>
      </div>
    </div>

    <div class="players-list">
      <h2>Players in Current Round</h2>
      <div v-if="currentGame && currentGame.player_bets && currentGame.player_bets.length > 0" class="player-bets-table">
        <div class="player-bet-row header">
          <span>Player</span>
          <span>Bet (sats)</span>
          <span>Status</span>
          <span>Multiplier</span>
          <span>Winnings</span>
        </div>
        <div v-for="bet in currentGame.player_bets" :key="bet.user_id" class="player-bet-row" :class="getPlayerBetClass(bet)">
          <span>User {{ бет.user_id.toString().slice(-4) }}</span> <!-- Masked User ID -->
          <span>{{ bet.bet_amount }}</span>
          <span class="status-cell status-{{ bet.status.toLowerCase() }}">{{ bet.status }}</span>
          <span v-if="bet.ejected_at">{{ bet.ejected_at.toFixed(2) }}x</span>
          <span v-else-if="isGameInProgress && bet.status === 'placed'">Playing...</span>
          <span v-else-if="currentGame.status === 'completed' && bet.status === 'busted'">Busted</span>
          <span v-else>-</span>
          <span v-if="bet.win_amount !== null && bet.win_amount > 0" class="win-amount">+{{ bet.win_amount }}</span>
          <span v-else-if="bet.status === 'busted' && bet.win_amount === 0">-</span>
          <span v-else>-</span>
        </div>
      </div>
      <p v-else class="empty-state">No active players in this round yet.</p>
    </div>

    <div class="game-history">
      <h2>Recent Games</h2>
      <div v-if="gameHistory && gameHistory.length > 0" class="history-table">
        <div class="history-row header">
          <span>Game ID</span>
          <span>Crash Point</span>
          <span>Ended At</span>
          <span>Public Seed (Verify)</span>
        </div>
        <div v-for="game in gameHistory" :key="game.id" class="history-row">
          <span>#{{ game.id }}</span>
          <span :class="getCrashPointClass(game.crash_point)">
            {{ game.crash_point ? game.crash_point.toFixed(2) + 'x' : 'N/A' }}
          </span>
          <span>{{ new Date(game.game_end_time).toLocaleTimeString() }}</span>
          <span class="public-seed" :title="game.public_seed">{{ game.public_seed ? game.public_seed.substring(0, 10) + '...' : 'N/A' }}</span>
        </div>
      </div>
      <p v-else class="empty-state">No game history available yet.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onUnmounted, computed, watch } from 'vue';
import api from '@/services/api'; // Assuming you have an api service module
import { socket, connectSocket } from '../../services/socketService.js';
import Phaser from 'phaser';
import SpacecrashBootScene from '@/phaser/scenes/SpacecrashBootScene';
import SpacecrashPreloadScene from '@/phaser/scenes/SpacecrashPreloadScene';
import SpacecrashGameScene from '@/phaser/scenes/SpacecrashGameScene';
import SpacecrashUIScene from '@/phaser/scenes/SpacecrashUIScene';

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

// --- Helper methods for styling ---
function getPlayerBetClass(bet) {
  // TODO: Could return specific classes based on win/loss/eject for row styling
  return `status-${bet.status.toLowerCase()}`;
}

function getCrashPointClass(crashPoint) {
  if (crashPoint === null || crashPoint === undefined) return '';
  return crashPoint >= 2.0 ? 'crash-point-good' : 'crash-point-bad';
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
// Renamed from placeBet to handlePlaceBet for clarity
async function handlePlaceBet() {
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
      // This part is tricky because game start is usually server-driven after betting phase.
      // For now, let's assume placing a bet when game is 'betting' implies user is ready.
      // The actual 'START_GAME' signal to Phaser should ideally come when the game *status* changes to 'in_progress'.
      // The fetchCurrentGame() polling will handle emitting START_GAME to Phaser when status changes.
      // await fetchCurrentGame(); // Refresh game state, which will then trigger Phaser via watchers or direct emit.
      // WebSocket update will now handle refreshing the state.
      
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

// Renamed from ejectBet to handleEject for clarity
async function handleEject() {
  ejectMessage.value = '';
  ejectDisabled.value = true; // Disable button during API call
  isEjectSuccess.value = false;
  try {
    const response = await api.post('/spacecrash/eject'); // API call
    if (response.data.status) {
      ejectMessage.value = `Successfully ejected at ${response.data.ejected_at.toFixed(2)}x! You won ${response.data.win_amount} sats.`;
      isEjectSuccess.value = true;
      isInGame.value = false; // User is now out of the current round
      // Play eject sound - can be done here or in Phaser based on an event
      if (game.value && game.value.sound && game.value.sound.get('eject_sound')) {
         try { game.value.sound.play('eject_sound', { volume: 0.5 }); } catch(e) { console.warn("eject sound play error", e)}
      }
    } else {
      ejectMessage.value = response.data.status_message || 'Failed to eject.';
      isEjectSuccess.value = false;
      if (response.data.status_message && (response.data.status_message.toLowerCase().includes('busted') || response.data.status_message.toLowerCase().includes('crashed'))) {
        isInGame.value = false; // User is out (busted)
      }
    }
    // await fetchCurrentGame(); // Refresh game state
    // WebSocket update will now handle refreshing the state.
    // TODO: Refresh user balance from store if not handled by fetchCurrentGame implicitly
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
// let gameUpdateInterval; // Removed

onMounted(() => {
  connectSocket(); // Establish WebSocket connection

  // Initial fetch
  fetchCurrentGame();
  fetchGameHistory();

  // Poll for game updates - REMOVED
  // gameUpdateInterval = setInterval(() => {
  //   if (game.value) { // Only poll if Phaser instance exists
  //     fetchCurrentGame();
  //     // Fetch history less frequently or only when game is not active
  //     if (!isGameInProgress.value && !isBettingPhase.value) {
  //       fetchGameHistory();
  //     }
  //   }
  // }, 2500); // Adjusted polling interval

  socket.on('spacecrash_update', (data) => {
    console.log('Received spacecrash_update:', data);
    if (data && data.id && data.status) { // Check for essential data properties
      const oldGameStatus = currentGame.value?.status;
      currentGame.value = data; // Update the main game state object

      // Handle Phaser updates based on the new game state
      if (game.value && game.value.scene && game.value.scene.isActive('SpacecrashGameScene')) {
          game.value.registry.events.emit('updateGameStatus', data); // General update for Phaser scene

          if (data.status === 'in_progress' && oldGameStatus !== 'in_progress') {
              console.log("Vue (WS): Game status to in_progress. Emitting START_GAME to Phaser.");
              game.value.registry.events.emit('START_GAME', { gameData: data });
          } else if (data.status === 'completed' && oldGameStatus === 'in_progress') {
              console.log("Vue (WS): Game status to completed. Emitting CRASH_AT to Phaser.");
              game.value.registry.events.emit('CRASH_AT', { crashPoint: data.crash_point, gameData: data });
          } else if (data.status === 'betting' && oldGameStatus !== 'betting') {
              console.log("Vue (WS): Game status to betting. Emitting RESET_GAME_VIEW to Phaser.");
              game.value.registry.events.emit('RESET_GAME_VIEW');
          }
      }

      // Update local currentMultiplier for display if needed (though Phaser might handle visuals)
      if (data.status === 'in_progress' && data.current_multiplier) {
        currentMultiplier.value = data.current_multiplier; // Should be 1.0 at start
      } else if (data.status === 'completed' && data.crash_point) {
        currentMultiplier.value = data.crash_point;
      } else if (data.status === 'betting') {
        currentMultiplier.value = 1.0;
      }

      // Refresh game history if the new game state indicates a game just completed
      if (data.status === 'completed' && oldGameStatus === 'in_progress') {
          fetchGameHistory(); // Refresh history when a game completes
      }
    } else {
      console.warn('Received incomplete spacecrash_update data:', data);
    }
  });

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
    game.value.registry.events.on('PLAYER_EJECT', handleEject, this); // 'this' context might be an issue here if not careful
    game.value.registry.events.on('PHASER_GAME_OVER', (data) => {
      console.log('Vue: PHASER_GAME_OVER event received', data);
      // This event is more for Phaser to inform Vue that its animation/state is "game over".
      // Vue's game logic (like isInGame) should primarily be driven by API responses via fetchCurrentGame.
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
    console.warn("Phaser game instance not ready in onMounted to set up PLAYER_EJECT listener.");
  }
});

onUnmounted(() => {
  // clearInterval(gameUpdateInterval); // Polling removed
  socket.off('spacecrash_update');

  if (game.value) {
    // Clean up Phaser-to-Vue event listeners
    if (game.value.registry) {
        game.value.registry.events.off('PLAYER_EJECT', handleEject, this); // 'this' context might be problematic here, ensure handleEject is stable if passed this way
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
  max-width: 900px;
  margin: 20px auto;
  padding: 20px;
  font-family: Arial, sans-serif;
  /* color: #333; */ /* Base color set by dark/light mode usually */
}

.game-area {
  display: flex;
  flex-direction: column; /* Stack game and info on smaller screens */
  align-items: center; /* Center game container */
  margin-bottom: 20px;
  gap: 20px;
}

@media (min-width: 768px) { /* md breakpoint or similar */
  .game-area {
    flex-direction: row;
    align-items: flex-start; /* Align items to the top */
  }
}


#spacecrash-game-container {
  width: 100%; /* Take full width of its column */
  max-width: 800px; /* Max width of game */
  height: 450px; /* Aspect ratio 16:9 for 800px width */
  background-color: #000000; /* Fallback, but Phaser config sets its own */
  border: 1px solid #444; /* Darker border for dark themes */
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5em;
  color: #777;
}

.game-info {
  width: 100%; 
  max-width: 800px; 
  padding: 10px;
  border: 1px solid #444;
  background-color: #2c2c2c;
  border-radius: 5px;
  color: #ddd; /* Light text for dark background */
}

@media (min-width: 768px) {
 .game-info {
    width: 300px; 
    flex-shrink: 0; 
  }
}

.controls-area, .players-list, .game-history {
  margin-bottom: 30px;
  padding: 15px;
  border: 1px solid #444;
  border-radius: 5px;
  background-color: #232323;
  color: #ddd; /* Light text for dark background */
}

.player-bets-table, .history-table {
  display: flex;
  flex-direction: column;
  gap: 5px; /* Space between rows */
}
.player-bet-row, .history-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr); /* Adjust for player bets */
  padding: 8px 5px;
  border-bottom: 1px solid #3a3a3a;
  align-items: center;
}
.history-row {
  grid-template-columns: 1fr 2fr 2fr 3fr; /* Adjust for history */
}

.player-bet-row.header, .history-row.header {
  font-weight: bold;
  color: #00aaff; /* Header color */
  border-bottom-width: 2px;
  border-bottom-color: #00aaff;
}
.player-bet-row span, .history-row span {
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-cell.status-ejected { color: #00cc00; } /* Green */
.status-cell.status-busted { color: #ff4444; } /* Red */
.status-cell.status-placed { color: #ffa500; } /* Orange */

.win-amount { color: #00cc00; font-weight: bold; }

.crash-point-good { color: #00cc00; font-weight: bold; } /* Green for >= 2x */
.crash-point-bad { color: #ff4444; font-weight: bold; } /* Red for < 2x */

.public-seed {
  font-family: monospace;
  font-size: 0.8em;
  color: #aaa;
  cursor: help; /* Indicate it's hoverable for full seed */
}
.empty-state {
  color: #888;
  font-style: italic;
}

.betting-form div, .eject-form div {
  margin-bottom: 10px;
}

.betting-form label, .eject-form label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.betting-form input[type="number"], .eject-form input[type="number"] {
  width: calc(100% - 22px);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

button {
  padding: 10px 15px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1em;
}

button:disabled {
  background-color: #aaa;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  background-color: #0056b3;
}

ul {
  list-style-type: none;
  padding: 0;
}

li {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

li:last-child {
  border-bottom: none;
}

.error-message {
  color: red;
  margin-top: 10px;
}

.success-message {
  color: green;
  margin-top: 10px;
}
</style>
