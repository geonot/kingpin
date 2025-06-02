<template>
<div class="blackjack-page bg-gray-200 dark:bg-neutral-900 min-h-[calc(100vh-150px)] flex flex-col items-center justify-center p-2 md:p-4">
<div class="w-full max-w-4xl">
<!-- Back Button -->
<div class="mb-4 text-left">
<router-link to="/tables" class="text-royal-blue dark:text-light-purple hover:underline">
    <i class="fas fa-arrow-left mr-2"></i>Back to Tables
</router-link>
</div>

<!-- Error Message Display -->
<error-message :error="errorObject" @dismiss="errorObject = null" class="mb-4" />

<!-- Game Container -->
<div class="blackjack-container relative bg-gradient-to-b from-gray-800 to-black dark:from-neutral-800 dark:to-black rounded-lg shadow-2xl p-1 md:p-2">
<div id="phaser-blackjack" class="w-full aspect-video md:aspect-[4/3] max-h-[600px] mx-auto">
        <!-- Phaser canvas will mount here -->
</div>
<!-- Loading Overlay -->
<div v-if="isLoading" class="loading-overlay absolute inset-0 bg-black bg-opacity-80 flex flex-col justify-center items-center z-50 rounded-lg">
    <div class="loading-spinner border-t-4 border-b-4 border-gold w-16 h-16 mb-4"></div>
    <p class="loading-message text-white text-lg font-semibold">{{ loadingMessage }}</p>
</div>
</div>

<!-- Game Info / Controls (Optional outside Phaser) -->
<div class="mt-4 p-4 bg-white dark:bg-dark-card rounded-lg shadow-md text-center md:text-left">
    <h2 class="text-xl font-bold dark:text-white">{{ tableInfo?.name || 'Loading Table...' }}</h2>
    <p class="text-sm text-gray-600 dark:text-gray-400">{{ tableInfo?.description }}</p>
    <div class="mt-2 flex justify-between">
      <p class="dark:text-gray-300">Min Bet: {{ formatSatsToBtc(tableInfo?.min_bet || 0) }} BTC</p>
      <p class="dark:text-gray-300">Max Bet: {{ formatSatsToBtc(tableInfo?.max_bet || 0) }} BTC</p>
      <p class="dark:text-gray-300">Decks: {{ tableInfo?.deck_count || 0 }}</p>
    </div>
</div>
</div>
</div>
</template>

<script setup>
import { shallowRef, ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
import Phaser from 'phaser';
import blackjackGameConfig from '@/blackjack/main.js'; // Assuming this is your Phaser game config
import EventBus from '@/event-bus';
import ErrorMessage from '@components/ErrorMessage.vue';
import { formatSatsToBtc } from '@utils/currencyFormatter';

const store = useStore();
const route = useRoute();
const router = useRouter();

// Refs
const game = shallowRef(null);
const gameSessionId = ref(null);
const currentHandId = ref(null);
const tableInfo = ref(null);
const errorObject = ref(null);
const isLoading = ref(true);
const loadingMessage = ref('Loading table information...');
const isAuthenticated = computed(() => store.getters.isAuthenticated);

// --- Phaser Game Initialization ---
const initPhaserGame = (tableApiData, phaserBaseConfig) => {
  loadingMessage.value = 'Initializing game engine...';
  const parentElement = document.getElementById('phaser-blackjack');
  if (!parentElement) {
    console.error("Phaser parent element 'phaser-blackjack' not found.");
    handleErrorFromPhaser("Failed to initialize game display area.");
    return;
  }

  const mergedConfig = {
    ...phaserBaseConfig,
    parent: 'phaser-blackjack',
    callbacks: {
      preBoot: (gameInstance) => {
        gameInstance.registry.set('eventBus', EventBus);
        gameInstance.registry.set('tableAPIData', tableApiData); // Table config from API
        // Assuming phaserBaseConfig.gameConfig is your specific Blackjack game rules/assets
        gameInstance.registry.set('gameDefinition', phaserBaseConfig.gameConfig || {});
      },
      postBoot: (gameInstance) => {
        gameInstance.registry.set('userBalance', store.state.user?.balance || 0);
        gameInstance.registry.set('soundEnabled', store.state.soundSettings?.enabled ?? true);
        isLoading.value = false;
        loadingMessage.value = 'Game ready. Place your bet.';
        console.log('Phaser game postBoot complete.');
      },
      ...(phaserBaseConfig.callbacks || {}) // Merge any other callbacks from base config
    },
  };

  try {
    game.value = new Phaser.Game(mergedConfig);
    game.value.events.on('error', (err) => {
      console.error('Phaser runtime error in game instance:', err);
      handleErrorFromPhaser('A Phaser runtime error occurred.');
    });
  } catch (error) {
    console.error('Failed to create Phaser game instance:', error);
    handleErrorFromPhaser('Could not start the game engine.');
  }
};

// --- Event Handlers for Phaser Events via EventBus ---
const handleDealRequest = async (payload) => {
  if (!tableInfo.value || !tableInfo.value.id) {
    errorObject.value = { status_message: 'Table information is not loaded.' };
    return;
  }
  loadingMessage.value = 'Dealing cards...';
  isLoading.value = true;
  errorObject.value = null;

  try {
    const response = await store.dispatch('joinBlackjack', {
      table_id: tableInfo.value.id,
      bet_amount: payload.betAmount,
    });

    if (response && response.status && response.hand) {
      gameSessionId.value = response.hand.session_id; // Assuming session_id is part of hand response
      currentHandId.value = response.hand.id;
      EventBus.emit('initialDeal', response.hand); // Emit to Phaser scene
      loadingMessage.value = 'Waiting for player action...';
    } else {
      errorObject.value = { status_message: response.status_message || 'Failed to deal cards. Please try again.' };
      EventBus.emit('dealFailed', errorObject.value); // Inform Phaser scene if needed
    }
  } catch (err) {
    console.error('Error during deal request:', err);
    errorObject.value = { status_message: err.message || 'An unexpected error occurred while dealing.' };
    EventBus.emit('dealFailed', errorObject.value);
  } finally {
    isLoading.value = false;
  }
};

const handlePlayerActionRequest = async (payload) => {
  if (!currentHandId.value) {
    errorObject.value = { status_message: 'No active hand ID. Cannot perform action.' };
    return;
  }
  loadingMessage.value = `Processing ${payload.action}...`;
  isLoading.value = true;
  errorObject.value = null;

  try {
    const response = await store.dispatch('blackjackAction', {
      hand_id: currentHandId.value,
      action_type: payload.action,
      hand_index: payload.hand_index, // Optional, for split hands
    });

    if (response && response.status && response.action_result) {
      currentHandId.value = response.action_result.id; // Update currentHandId if it changes (e.g. after split, though usually same)
      EventBus.emit('actionResult', response.action_result); // Emit to Phaser scene

      if (response.action_result.status === 'completed') {
        loadingMessage.value = 'Round ended. Place your bet for the next round.';
      } else {
        loadingMessage.value = 'Waiting for player action...';
      }
    } else {
      errorObject.value = { status_message: response.status_message || 'Action failed. Please try again.' };
      EventBus.emit('actionFailed', errorObject.value); // Inform Phaser scene
    }
  } catch (err) {
    console.error(`Error during ${payload.action} request:`, err);
    errorObject.value = { status_message: err.message || `An unexpected error occurred during ${payload.action}.` };
    EventBus.emit('actionFailed', errorObject.value);
  } finally {
    isLoading.value = false;
  }
};

const handleErrorFromPhaser = (message) => {
  errorObject.value = { status_message: message || 'An error occurred in the game.' };
  isLoading.value = false; // Stop loading if game error occurs
};

// --- Session Management ---
const endGameSession = async () => {
  if (gameSessionId.value) {
    try {
      await store.dispatch('endSession'); // This action should handle its own errors
      console.log('Blackjack game session ended:', gameSessionId.value);
    } catch (error) {
      console.error('Failed to end game session:', error);
      // Optionally inform user, though usually silent on unmount
    } finally {
      gameSessionId.value = null;
      currentHandId.value = null;
    }
  }
};


// --- Lifecycle Hooks ---
onMounted(async () => {
  if (!isAuthenticated.value) {
    router.push({ name: 'Login', query: { redirect: route.fullPath } });
    return;
  }

  const tableIdNum = Number(route.params.id);
  if (isNaN(tableIdNum)) {
    errorObject.value = { status_message: 'Invalid Table ID.' };
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  errorObject.value = null;
  loadingMessage.value = 'Fetching user profile...';
  await store.dispatch('fetchUserProfile'); // Ensure user balance is fresh

  loadingMessage.value = 'Fetching table configuration...';
  const fetchedTableInfo = await store.dispatch('fetchTableConfig', tableIdNum);

  if (fetchedTableInfo && typeof fetchedTableInfo === 'object' && !fetchedTableInfo.status_message) {
    tableInfo.value = fetchedTableInfo;
    // Setup EventBus listeners
    EventBus.on('blackjackDealRequest', handleDealRequest);
    EventBus.on('blackjackActionRequest', handlePlayerActionRequest);
    EventBus.on('phaserBlackjackError', handleErrorFromPhaser);

    initPhaserGame(tableInfo.value, blackjackGameConfig);
  } else {
    console.error(`Table with ID ${tableIdNum} not found or fetch failed.`);
    errorObject.value = fetchedTableInfo || { status_message: 'Could not load table configuration.' };
    isLoading.value = false;
  }
  // isLoading state is managed by initPhaserGame or error condition above
});

onBeforeUnmount(async () => {
  await endGameSession();

  // Remove EventBus listeners
  EventBus.off('blackjackDealRequest', handleDealRequest);
  EventBus.off('blackjackActionRequest', handlePlayerActionRequest);
  EventBus.off('phaserBlackjackError', handleErrorFromPhaser);

  if (game.value) {
    console.log('Destroying Phaser game instance.');
    game.value.destroy(true);
    game.value = null;
  }
});

// Helper for template if needed, though formatSatsToBtc is already imported
// const formatCurrency = (value) => formatSatsToBtc(value) + ' BTC';
</script>

<style scoped>
.blackjack-page {
  /* Provides a background for the entire view */
}

.blackjack-container {
  /* Styles for the container holding the Phaser canvas */
  width: 100%;
  aspect-ratio: 4 / 3; /* Maintain aspect ratio, adjust as needed */
  max-height: calc(100vh - 250px); /* Limit height on tall screens */
  position: relative; /* Needed for absolute positioning of overlay */
}

#phaser-blackjack {
  /* Phaser canvas itself */
  width: 100%;
  height: 100%;
  display: block; /* Remove extra space below canvas */
  border-radius: inherit; /* Inherit parent's rounded corners */
}

/* Loading Overlay Styles */
.loading-overlay {
  /* Styles already defined inline via Tailwind */
}

.loading-spinner {
  border-radius: 50%;
  border: 4px solid rgba(255, 215, 0, 0.3); /* Gold transparent */
  border-top-color: #FFD700; /* Gold */
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-message {
  /* Styles defined inline */
}
</style>