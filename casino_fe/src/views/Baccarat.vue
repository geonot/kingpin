<template>
  <div class="baccarat-page">
    <router-link to="/tables/baccarat" class="back-link">Back to Baccarat Tables</router-link>

    <div v.if="errorObject" class="error-container">
      <error-message :error="errorObject" />
    </div>

    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>{{ loadingMessage }}</p>
    </div>

    <div id="phaser-baccarat-container" class="phaser-container">
      <!-- Phaser game will attach here -->
    </div>

    <div v-if="tableInfo && !isLoading" class="table-info-display">
      <h2>{{ tableInfo.name }}</h2>
      <p>Min Bet: {{ formatSatsToBtc(tableInfo.min_bet) }} BTC | Max Bet (Player/Banker): {{ formatSatsToBtc(tableInfo.max_bet) }} BTC | Max Tie Bet: {{ formatSatsToBtc(tableInfo.max_tie_bet) }} BTC</p>
      <p>Commission: {{ (tableInfo.commission_rate * 100).toFixed(2) }}%</p>
    </div>

  </div>
</template>

<script setup>
import { shallowRef, ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
import Phaser from 'phaser';
// Placeholder for Baccarat game configuration - will be created later
import baccaratGameConfig from '@/baccarat/main.js';
import EventBus from '@/event-bus';
import ErrorMessage from '@/components/ErrorMessage.vue';
import { formatSatsToBtc } from '@/utils/currencyFormatter';

const store = useStore();
const route = useRoute();
const router = useRouter();

const game = shallowRef(null);
const baccaratHandId = ref(null); // To store the current hand ID after a bet
const tableInfo = ref(null);
const errorObject = ref(null);
const isLoading = ref(true);
const loadingMessage = ref('Loading table information...');

const isAuthenticated = computed(() => store.getters.isAuthenticated);
const userBalance = computed(() => store.getters.user?.balance || 0); // Sats

const initPhaserGame = (tableData) => {
  if (game.value) {
    game.value.destroy(true);
  }
  isLoading.value = true;
  loadingMessage.value = 'Initializing game engine...';

  const config = {
    ...baccaratGameConfig, // Spread the imported config
    parent: 'phaser-baccarat-container',
    // width, height might be part of baccaratGameConfig or set dynamically
  };

  // Pass data to Phaser game instance via registry
  const gameInstance = new Phaser.Game(config);
  gameInstance.registry.set('eventBus', EventBus);
  gameInstance.registry.set('tableData', tableData);
  gameInstance.registry.set('userBalance', userBalance.value); // Pass initial balance
  gameInstance.registry.set('soundSettings', store.getters.soundSettings);
  // Add other necessary data like JWT token if Phaser needs to make API calls directly (not typical)

  game.value = gameInstance;
  isLoading.value = false;
  loadingMessage.value = '';
};

const handleBetRequest = async (payload) => {
  errorObject.value = null;
  isLoading.value = true;
  loadingMessage.value = 'Placing bets...';

  if (!isAuthenticated.value) {
    errorObject.value = { status_message: "You must be logged in to place bets." };
    isLoading.value = false;
    EventBus.emit('baccaratHandResult', { success: false, error: "Not authenticated." });
    return;
  }

  const betData = {
    table_id: tableInfo.value.id,
    bet_on_player: payload.playerBet || 0,
    bet_on_banker: payload.bankerBet || 0,
    bet_on_tie: payload.tieBet || 0,
  };

  try {
    const result = await store.dispatch('placeBaccaratBet', betData);
    if (result && result.hand) {
      baccaratHandId.value = result.hand.id;
      // Update user balance from Vuex store after bet (Vuex action should handle this)
      // The game instance registry for balance might need an update if Phaser doesn't re-fetch
      if (game.value) {
        game.value.registry.set('userBalance', store.getters.user.balance);
      }
      EventBus.emit('baccaratHandResult', { success: true, hand: result.hand });
    } else {
      throw new Error(result.status_message || 'Failed to place bet or receive hand result.');
    }
  } catch (error) {
    const message = error.response?.data?.status_message || error.message || 'Error placing Baccarat bet.';
    errorObject.value = { status_message: message };
    EventBus.emit('baccaratHandResult', { success: false, error: message });
  } finally {
    isLoading.value = false;
    loadingMessage.value = '';
  }
};

const handlePhaserError = (message) => {
  errorObject.value = { status_message: message || "An error occurred in the game." };
};

const handleGameReady = () => {
  // This could be emitted by Phaser when its main scene is ready
  isLoading.value = false;
  loadingMessage.value = '';
};


onMounted(async () => {
  errorObject.value = null;
  isLoading.value = true;
  loadingMessage.value = 'Fetching table information...';

  if (!isAuthenticated.value) {
    router.push({ name: 'Login', query: { redirect: route.fullPath } });
    isLoading.value = false;
    return;
  }

  await store.dispatch('fetchUserProfile'); // Ensure user profile and balance are up-to-date

  const currentTableId = parseInt(route.params.id, 10);

  try {
    // This action needs to be created in Vuex store
    const fetchedTableInfo = await store.dispatch('fetchBaccaratTableConfig', currentTableId);
    if (fetchedTableInfo && fetchedTableInfo.id) {
      tableInfo.value = fetchedTableInfo;

      // Setup EventBus listeners
      EventBus.on('baccaratBetRequested', handleBetRequest);
      EventBus.on('phaserBaccaratError', handlePhaserError);
      EventBus.on('baccaratGameReady', handleGameReady); // Phaser emits this when ready

      // Initialize Phaser game
      // Ensure baccaratGameConfig is not undefined. If main.js is placeholder, this will fail.
      // For now, we assume baccaratGameConfig will be a valid Phaser config object.
      if (typeof baccaratGameConfig === 'object' && baccaratGameConfig !== null) {
        initPhaserGame(fetchedTableInfo);
      } else {
          errorObject.value = { status_message: "Baccarat game configuration is missing or invalid. Cannot start game."};
          isLoading.value = false;
      }

    } else {
      throw new Error('Baccarat table configuration not found or invalid.');
    }
  } catch (error) {
    errorObject.value = { status_message: error.response?.data?.status_message || error.message || 'Failed to load Baccarat table.' };
    isLoading.value = false;
  }
});

onBeforeUnmount(() => {
  EventBus.off('baccaratBetRequested', handleBetRequest);
  EventBus.off('phaserBaccaratError', handlePhaserError);
  EventBus.off('baccaratGameReady', handleGameReady);

  if (game.value) {
    game.value.destroy(true);
    game.value = null;
  }
});

</script>

<style scoped>
.baccarat-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  color: #fff; /* Assuming a dark theme */
  background-color: #1a202c; /* Example dark background */
  min-height: 100vh;
}

.back-link {
  align-self: flex-start;
  margin-bottom: 20px;
  color: #4a90e2;
  text-decoration: none;
}
.back-link:hover {
  text-decoration: underline;
}

.error-container {
  width: 100%;
  max-width: 800px; /* Or Phaser game width */
  margin-bottom: 20px;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  color: white;
}

.loading-spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #4a90e2;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

#phaser-baccarat-container {
  width: 800px; /* Example width, should match Phaser config */
  height: 600px; /* Example height */
  border: 1px solid #333;
  margin-bottom: 20px;
  /* If Phaser canvas is black/transparent, this background can be seen */
  background-color: #000;
}

.table-info-display {
  background-color: #2d3748;
  padding: 15px;
  border-radius: 8px;
  text-align: center;
  width: 100%;
  max-width: 800px; /* Match Phaser container width */
}
.table-info-display h2 {
  margin-top: 0;
  color: #a0aec0;
}
.table-info-display p {
  margin: 5px 0;
  color: #cbd5e0;
}
</style>
