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
<error-message v-if="isErrorVisible" :message="errorMessage" @dismiss="clearErrorMessage" class="mb-4" />

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
import { ref, computed, onMounted, onBeforeUnmount, shallowRef } from 'vue';
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
import Phaser from 'phaser';
import EventBus from '@/event-bus';
import phaserConfig from '@/blackjack/main.js'; // Use alias
import ErrorMessage from '@components/ErrorMessage.vue'; // Use alias
import { formatSatsToBtc } from '@utils/currencyFormatter'; // Assuming this utility exists

const store = useStore();
const route = useRoute();
const router = useRouter();

// Use shallowRef for Phaser game instance to avoid deep reactivity issues
const game = shallowRef(null);
const gameSessionId = ref(null);
const handId = ref(null);
const isLoading = ref(true);
const loadingMessage = ref('Joining game...');
const errorMessage = ref(null);
const isErrorVisible = ref(false);
const tableInfo = ref(null); // To store details about the current table
const isPlaying = ref(false); // Prevent concurrent actions

const user = computed(() => store.state.user);
const userBalance = computed(() => store.state.user?.balance ?? 0);
const isAuthenticated = computed(() => store.getters.isAuthenticated);

const clearErrorMessage = () => {
  errorMessage.value = null;
  isErrorVisible.value = false;
};

const fetchTableDetails = async (tableId) => {
  // Check if tables are loaded, if not fetch them
  if (!store.state.tablesLoaded) {
    try {
      await store.dispatch('fetchTables');
    } catch (err) {
      console.error("Failed to fetch table list:", err);
      // Handle error appropriately, maybe redirect or show static error
    }
  }
  // Find the specific table from the store
  tableInfo.value = store.getters.getTableById(tableId);
  if (!tableInfo.value) {
    console.error(`Table with ID ${tableId} not found in store.`);
    errorMessage.value = 'Could not load table information. Please try again.';
    isErrorVisible.value = true;
    // Optionally redirect back
    // router.push('/tables');
  }
};

const joinGame = async (tableId) => {
  isLoading.value = true;
  loadingMessage.value = 'Joining game session...';
  clearErrorMessage();
  try {
    // First join the game session
    const joinResponse = await store.dispatch('joinGame', {
      table_id: tableId,
      game_type: 'blackjack'
    });
    
    if (joinResponse.status && joinResponse.session_id) {
      gameSessionId.value = joinResponse.session_id;
      console.log('Joined game session:', gameSessionId.value);
      return true;
    } else {
      throw new Error(joinResponse.status_message || 'Failed to join game session.');
    }
  } catch (error) {
    console.error('Error joining game:', error);
    errorMessage.value = `Failed to join game: ${error.message}. Please ensure you are logged in and try again.`;
    isErrorVisible.value = true;
    isLoading.value = false; // Stop loading on error
    // Potentially redirect if join fails critically
    // router.push('/tables');
    throw error; // Re-throw to prevent Phaser initialization
  }
};
const startPhaserGame = (tableId) => {
  if (game.value) {
    console.warn("Phaser game already exists. Destroying previous instance.");
    game.value.destroy(true);
    game.value = null;
  }

  loadingMessage.value = 'Loading game assets...';

  // Ensure the parent element exists
  const parentElement = document.getElementById('phaser-blackjack');
  if (!parentElement) {
    console.error("Phaser parent element 'phaser-blackjack' not found.");
    errorMessage.value = "Internal error: Could not initialize game display.";
    isErrorVisible.value = true;
    isLoading.value = false;
    return;
  }

  // Ensure phaserConfig has gameConfig property
  if (!phaserConfig.gameConfig) {
    console.warn('Blackjack.vue: gameConfig property not found in phaserConfig, this may cause issues');
  }

  // Merge Phaser config with dynamic data
  const mergedConfig = {
    ...phaserConfig,
    parent: 'phaser-blackjack', // Explicitly set parent container ID
    callbacks: {
      preBoot: (bootingGame) => {
        // Set the gameId in the registry before any scenes start
        bootingGame.registry.set('gameId', 'blackjack');
        bootingGame.registry.set('tableId', tableId);
        console.log(`Pre-boot: Setting tableId ${tableId} in registry`);
      },
      postBoot: (bootedGame) => {
        // Pass additional data to Phaser scenes via game registry or globals
        bootedGame.registry.set('userBalance', userBalance.value);
        bootedGame.registry.set('tableConfig', tableInfo.value); // Pass fetched table info
        bootedGame.registry.set('initialBet', tableInfo.value?.min_bet || 10); // Default to min bet
        // Don't pass initialHand - wait for user to click deal
        console.log('Phaser game booted. Initial data set.');
        isLoading.value = false; // Hide loading overlay once Phaser is ready
      }
    }
  };

  // Ensure gameConfig is properly passed to the Phaser game
  if (phaserConfig.gameConfig) {
    mergedConfig.gameConfig = { ...phaserConfig.gameConfig };
    console.log('Blackjack.vue: Explicitly setting gameConfig in mergedConfig');
  }

  console.log("Initializing Phaser game...");
  // Assign to shallowRef's value property
  game.value = new Phaser.Game(mergedConfig);

  // Optional: Listen for Phaser errors
  game.value.events.on('error', (error) => {
    console.error('Phaser Error:', error);
    errorMessage.value = "An error occurred within the game.";
    isErrorVisible.value = true;
    // Handle Phaser error, maybe destroy game or show overlay
  });
};

const handleDealRequest = async ({ bet }) => {
  if (isPlaying.value) {
    console.warn('Deal request ignored, already playing.');
    return;
  }
  if (!isAuthenticated.value) {
    errorMessage.value = "Please log in to play.";
    isErrorVisible.value = true;
    return;
  }
  isPlaying.value = true;
  clearErrorMessage();

  console.log(`Handling deal request. Bet: ${bet} Sats`);

  try {
    // Join a new blackjack game
    const response = await store.dispatch('joinBlackjack', {
      table_id: Number(route.params.id),
      bet_amount: bet
    });
    
    if (response.status && response.hand) {
      handId.value = response.hand.hand_id;
      
      // Send the hand data to the GameScene
      const gameScene = game.value?.scene.getScene('GameScene');
      if (gameScene && gameScene.scene.isActive()) {
        gameScene.handleInitialDeal(response.hand);
      } else {
        console.error('GameScene not found or inactive, cannot display initial deal.');
        errorMessage.value = 'Game error: Could not display initial deal.';
        isErrorVisible.value = true;
      }
      
      // Update balance in UI
      EventBus.$emit('uiUpdate', {
        balance: response.user.balance
      });
    } else {
      errorMessage.value = response.status_message || 'Deal request failed. Please try again.';
      isErrorVisible.value = true;
      EventBus.$emit('dealError', { message: errorMessage.value });
    }
  } catch (error) {
    console.error('Error during deal:', error);
    errorMessage.value = error.message || 'Deal failed due to a network or server error.';
    isErrorVisible.value = true;
    EventBus.$emit('dealError', { message: errorMessage.value });
  } finally {
    isPlaying.value = false;
  }
};

const handleActionRequest = async ({ action, handIndex = 0 }) => {
  if (isPlaying.value) {
    console.warn('Action request ignored, already processing an action.');
    return;
  }
  if (!isAuthenticated.value) {
    errorMessage.value = "Please log in to play.";
    isErrorVisible.value = true;
    return;
  }
  if (!handId.value) {
    errorMessage.value = "No active hand. Please deal first.";
    isErrorVisible.value = true;
    return;
  }
  
  isPlaying.value = true;
  clearErrorMessage();

  console.log(`Handling ${action} request for hand ${handId.value}, index ${handIndex}`);

  try {
    const response = await store.dispatch('blackjackAction', {
      hand_id: handId.value,
      action_type: action,
      hand_index: handIndex
    });
    
    if (response.status && response.action_result) {
      // Send the action result to the GameScene
      const gameScene = game.value?.scene.getScene('GameScene');
      if (gameScene && gameScene.scene.isActive()) {
        gameScene.handleActionResult(response.action_result);
      } else {
        console.error('GameScene not found or inactive, cannot display action result.');
        errorMessage.value = 'Game error: Could not display action result.';
        isErrorVisible.value = true;
      }
      
      // Update balance in UI
      EventBus.$emit('uiUpdate', {
        balance: response.user.balance
      });
      
      // If the hand is completed, reset the handId
      if (response.action_result.status === 'completed') {
        handId.value = null;
      }
    } else {
      errorMessage.value = response.status_message || 'Action request failed. Please try again.';
      isErrorVisible.value = true;
      EventBus.$emit('actionError', { message: errorMessage.value });
    }
  } catch (error) {
    console.error('Error during action:', error);
    errorMessage.value = error.message || 'Action failed due to a network or server error.';
    isErrorVisible.value = true;
    EventBus.$emit('actionError', { message: errorMessage.value });
  } finally {
    isPlaying.value = false;
  }
};

// --- Lifecycle Hooks ---
onMounted(async () => {
  if (!isAuthenticated.value) {
    // Redirect to login if not authenticated
    router.push({ name: 'Login', query: { redirect: route.fullPath } });
    return;
  }

  const tableId = Number(route.params.id);
  if (isNaN(tableId)) {
    errorMessage.value = 'Invalid Table ID.';
    isErrorVisible.value = true;
    isLoading.value = false;
    return;
  }

  try {
    await fetchTableDetails(tableId); // Fetch details first
    if (tableInfo.value) { // Proceed only if table info loaded
      await joinGame(tableId); // Join the game session but don't deal cards yet
      startPhaserGame(tableId); // Start Phaser without initial hand
      // Register event listeners for game actions
      EventBus.$on('dealRequest', handleDealRequest);
      EventBus.$on('actionRequest', handleActionRequest);
    } else {
      // Error handled within fetchTableDetails
      isLoading.value = false;
    }
  } catch (error) {
    // Errors during fetch/join are already handled and displayed
    console.error("Initialization failed:", error);
    isLoading.value = false; // Ensure loading stops on failure
  }
});

const endGameSession = async () => {
  if (gameSessionId.value) {
    try {
      console.log("Ending game session:", gameSessionId.value);
      await store.dispatch('endSession');
      gameSessionId.value = null;
      handId.value = null;
    } catch (error) {
      console.error("Failed to end game session:", error);
      // Don't block unmounting even if this fails
    }
  }
};

onBeforeUnmount(async () => {
  console.log("Destroying Phaser game instance and cleaning up event listeners.");
  // Remove event listeners
  EventBus.$off('dealRequest', handleDealRequest);
  EventBus.$off('actionRequest', handleActionRequest);

  // End the game session
  await endGameSession();

  // Destroy Phaser game instance
  if (game.value) {
    game.value.destroy(true);
    game.value = null; // Clear the ref
  }
  // Clean up potentially other listeners or timers
});
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