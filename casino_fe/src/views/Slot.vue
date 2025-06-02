<template>
<div class="slot-page bg-gray-200 dark:bg-neutral-900 min-h-[calc(100vh-150px)] flex flex-col items-center justify-center p-2 md:p-4">
<div class="w-full max-w-4xl">
<!-- Back Button -->
<div class="mb-4 text-left">
<router-link to="/slots" class="text-royal-blue dark:text-light-purple hover:underline">
    <i class="fas fa-arrow-left mr-2"></i>Back to Slots
</router-link>
</div>

<!-- Error Message Display -->
<error-message :error="errorObject" @dismiss="clearErrorObject" class="mb-4" />

<!-- Game Container -->
<div class="slot-container relative bg-gradient-to-b from-gray-800 to-black dark:from-neutral-800 dark:to-black rounded-lg shadow-2xl p-1 md:p-2">
<div id="phaser-slot-machine" class="w-full aspect-video md:aspect-[4/3] max-h-[600px] mx-auto">
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
    <h2 class="text-xl font-bold dark:text-white">{{ slotInfo?.name || 'Loading Slot...' }}</h2>
    <p class="text-sm text-gray-600 dark:text-gray-400">{{ slotInfo?.description }}</p>
    <!-- Display balance or other info if needed outside Phaser UI -->
    <!-- <p class="mt-2 dark:text-gray-300">Balance: {{ formatSatsToBtc(userBalance) 
Btc </p> -->
</div>
</div>
</div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, shallowRef } from 'vue';
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
import Phaser from 'phaser';
import axios from 'axios';
import EventBus from '@/event-bus';
import phaserConfig from '@phaser/main.js'; // Use alias
import ErrorMessage from '@components/ErrorMessage.vue'; // Use alias
import { formatSatsToBtc } from '@utils/currencyFormatter'; // Assuming this utility exists

const store = useStore();
const route = useRoute();
const router = useRouter();

// Use shallowRef for Phaser game instance to avoid deep reactivity issues
const game = shallowRef(null);
const gameSessionId = ref(null);
const isLoading = ref(true);
const loadingMessage = ref('Joining game...');
const errorObject = ref(null); // For ErrorMessage.vue component
const slotInfo = ref(null); // To store details about the current slot (from API)
const slotGameJsonConfigContent = ref(null); // To store content of gameConfig.json
const isSpinning = ref(false); // Prevent concurrent spins

// Constants for localStorage keys
const SESSION_STORAGE_KEY = 'slotGameSessionId';
const SLOT_ID_STORAGE_KEY = 'currentSlotId';

const user = computed(() => store.state.user);
const userBalance = computed(() => store.state.user?.balance ?? 0); // Used for registry
const isAuthenticated = computed(() => store.getters.isAuthenticated);
// Assuming sound/turbo settings are in Vuex state, e.g., store.state.settings.soundEnabled
const soundEnabled = computed(() => store.state.soundSettings?.enabled ?? true);
const turboEnabled = computed(() => store.state.turboSettings?.enabled ?? false);


const clearErrorObject = () => {
  errorObject.value = null;
};

const fetchSlotDetailsAndConfig = async (slotId) => {
  loadingMessage.value = 'Fetching slot details...';
  errorObject.value = null; // Clear previous errors
  slotInfo.value = null; // Reset
  slotGameJsonConfigContent.value = null; // Reset

  const fetchedSlotInfo = await store.dispatch('fetchSlotConfig', slotId);
  if (fetchedSlotInfo && typeof fetchedSlotInfo === 'object' && !fetchedSlotInfo.status_message) {
    slotInfo.value = fetchedSlotInfo;

    // Now fetch the gameConfig.json for this specific slot
    if (slotInfo.value.short_name) {
      loadingMessage.value = `Loading game configuration for ${slotInfo.value.name}...`;
      try {
        const gameConfigPath = `public/slots/${slotInfo.value.short_name}/gameConfig.json`;
        const response = await axios.get(gameConfigPath);
        slotGameJsonConfigContent.value = response.data;
        console.log(`Successfully loaded gameConfig.json for ${slotInfo.value.short_name}`);
      } catch (err) {
        console.error(`Failed to load gameConfig.json for ${slotInfo.value.short_name}:`, err);
        errorObject.value = { status_message: `Could not load detailed game configuration for ${slotInfo.value.name}. Some features might be unavailable or use defaults.` };
        // Depending on how critical gameConfig.json is, you might stop here or allow Phaser to start with partial data.
        // For now, we'll let it proceed and PreloadScene can handle missing parts.
      }
    } else {
      console.error('Slot short_name is missing, cannot load gameConfig.json.');
      errorObject.value = { status_message: 'Critical slot identifier missing, cannot load game configuration.' };
    }
  } else {
    console.error(`Slot with ID ${slotId} not found or API fetch failed.`);
    errorObject.value = fetchedSlotInfo || { status_message: 'Could not load slot information from API.'};
  }
};


const joinGameAndInitPhaser = async (slotId) => {
    isLoading.value = true;
    loadingMessage.value = 'Joining game session...';
    clearErrorObject(); // Clear previous errors
    
    // Ensure slotInfo and potentially slotGameJsonConfigContent are loaded before joining
    if (!slotInfo.value || !slotInfo.value.short_name) {
        await fetchSlotDetailsAndConfig(slotId); // This will also attempt to load gameConfig.json
        if (!slotInfo.value || errorObject.value) { // If still not loaded or error occurred
            isLoading.value = false;
            // errorObject is already set by fetchSlotDetailsAndConfig
            return; // Stop if essential slot info is missing
        }
    }
    // If slotGameJsonConfigContent is strictly required before this point, add check here.
    // For now, PreloadScene might have fallbacks.

    localStorage.setItem(SLOT_ID_STORAGE_KEY, slotId.toString());
    const existingSessionId = localStorage.getItem(SESSION_STORAGE_KEY);

    if (existingSessionId && isAuthenticated.value) {
        gameSessionId.value = existingSessionId;
        console.log('Attempting to reuse existing game session:', gameSessionId.value);
    } else if (isAuthenticated.value) { // Only try to join if authenticated
        try {
            const response = await store.dispatch('joinGame', { slot_id: slotId, game_type: 'slot' });
            if (response.status && response.session_id) {
                gameSessionId.value = response.session_id;
                localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
            } else {
                throw new Error(response.status_message || 'Failed to join game session.');
            }
        } catch (err) {
            console.error('Error joining game:', err);
            errorObject.value = { status_message: `Failed to join game: ${err.message}.` };
            isLoading.value = false;
            return; // Stop if cannot join game
        }
    } else {
        // Not authenticated, and no existing session. Game can be played without session (demo mode).
        console.log('User not authenticated, proceeding without game session.');
        gameSessionId.value = null; // Ensure no old session ID is used
        localStorage.removeItem(SESSION_STORAGE_KEY); // Clear any stale session ID
    }

    // Proceed to start Phaser
    startPhaserGame(slotId);
};

const startPhaserGame = (slotId) => { // slotId is passed for preBoot, though short_name is primary now
  if (game.value) {
    console.warn("Phaser game already exists. Destroying previous instance.");
    game.value.destroy(true); game.value = null;
  }
  loadingMessage.value = 'Initializing game engine...'; // Changed from "Loading game assets" as PreloadScene handles that
  const parentElement = document.getElementById('phaser-slot-machine');
  if (!parentElement) {
    console.error("Phaser parent element 'phaser-slot-machine' not found.");
    errorObject.value = { status_message: "Internal error: Could not initialize game display." };
    isLoading.value = false; return;
  }

  const mergedConfig = {
    ...phaserConfig, // Base Phaser config (scenes, physics, etc.)
    parent: 'phaser-slot-machine',
    callbacks: {
      preBoot: (bootingGame) => {
        // slotId might be useful for some initial setup if needed before full config is parsed
        bootingGame.registry.set('slotIdFromVue', slotId);
      },
      postBoot: (bootedGame) => {
        bootedGame.registry.set('userBalance', userBalance.value);
        // API Data (from /api/slots/:id) - contains short_name, symbol list with img_link etc.
        bootedGame.registry.set('slotApiData', slotInfo.value);
        // Game JSON Config (from public/slots/{short_name}/gameConfig.json) - contains layout, paylines, assets paths etc.
        bootedGame.registry.set('slotGameJsonConfig', slotGameJsonConfigContent.value);

        bootedGame.registry.set('soundEnabled', soundEnabled.value);
        bootedGame.registry.set('turboEnabled', turboEnabled.value);
        bootedGame.registry.set('eventBus', EventBus);
        console.log('Phaser game booted. Initial data (API, JSON config, settings) set in registry.');
        // isLoading is now set by Phaser's PreloadScene on its 'complete' event,
        // or by GameScene once it's fully ready if PreloadScene is quick.
        // For now, we can set it to false here, assuming PreloadScene will show its own progress.
        isLoading.value = false;
      }
    }
  };
  game.value = new Phaser.Game(mergedConfig);
  game.value.events.on('error', (err) => {
    console.error('Phaser Error:', err);
    errorObject.value = { status_message: "A game error occurred." };
  });
};

// Phaser to Vue Event Handlers
const handlePhaserSpinResult = (result) => {
    console.log("Vue: PhaserSpinResult received", result);
    if (result.user) {
        store.commit('updateUserBalance', result.user.balance);
    }
    // Potentially update other UI elements based on win, lines etc.
};
const handlePhaserBalanceInsufficient = () => {
    console.log("Vue: PhaserBalanceInsufficient received");
    errorObject.value = { status_message: "Insufficient balance for the bet." };
};
const handlePhaserError = (message) => {
    console.log("Vue: PhaserError received", message);
    errorObject.value = { status_message: message || "An error occurred in the game." };
};
const handlePhaserRequestBalanceUpdate = async () => {
    console.log("Vue: PhaserRequestBalanceUpdate received");
    try {
        await store.dispatch('fetchUserProfile'); // Fetches and commits new balance
        // Phaser UIScene should listen for 'vueBalanceUpdated' or directly read from registry if updated there.
        EventBus.emit('vueBalanceUpdated', { balance: store.getters.currentUser?.balance });
    } catch (err) {
        console.error("Vue: Error fetching user profile for balance update:", err);
    }
};

// Vue to Phaser Command Emitter (example, if Vue UI triggers spin)
// const triggerPhaserSpin = (betAmount) => {
//   if (game.value) {
//     EventBus.emit('vueSpinCommand', { betAmount });
//   }
// };

// --- Lifecycle Hooks ---
onMounted(async () => {
  if (!isAuthenticated.value) {
    router.push({ name: 'Login', query: { redirect: route.fullPath } });
    return;
  }
  const slotIdNum = Number(route.params.id);
  if (isNaN(slotIdNum)) {
    errorObject.value = { status_message: 'Invalid Slot ID.' };
    isLoading.value = false; return;
  }

  clearErrorObject();
  isLoading.value = true;
  loadingMessage.value = 'Loading slot configuration...';

  try {
    await store.dispatch('fetchUserProfile'); // Ensure user balance is fresh
    await fetchSlotDetailsAndConfig(slotIdNum); // Fetches config and stores in slotInfo

    if (slotInfo.value && !errorObject.value) { // If config loaded successfully
      await joinGameAndInitPhaser(slotIdNum); // Joins game, then starts Phaser
    } else {
      isLoading.value = false; // Config loading failed
    }
  } catch (err) {
    console.error("Slot page initialization failed:", err);
    if (!errorObject.value) { // Ensure some error is shown
        errorObject.value = { status_message: 'Failed to initialize slot game.' };
    }
    isLoading.value = false;
  }

  // Register Event Bus Listeners (Phaser to Vue)
  EventBus.on('phaserSpinResult', handlePhaserSpinResult);
  EventBus.on('phaserBalanceInsufficient', handlePhaserBalanceInsufficient);
  EventBus.on('phaserError', handlePhaserError);
  EventBus.on('requestBalanceUpdate', handlePhaserRequestBalanceUpdate);
  // Listener for spin command from Phaser UI
  EventBus.on('spinCommand', handlePhaserSpinCommand);
});

// This function is called when Phaser's UI requests a spin
const handlePhaserSpinCommand = async (payload) => {
    if (isSpinning.value) {
        console.warn("Vue: Spin command ignored, already spinning.");
        EventBus.emit('spinReject', { message: 'Already spinning.' }); // Inform Phaser
        return;
    }
    if (!isAuthenticated.value) {
        errorObject.value = { status_message: "Please log in to play." };
        EventBus.emit('spinError', { message: 'User not authenticated.' }); // Inform Phaser
        return;
    }

    const betAmount = payload.betAmount; // Assuming payload from Phaser is { betAmount: XXX }
    if (userBalance.value < betAmount) {
        errorObject.value = { status_message: 'Insufficient balance.' };
        EventBus.emit('phaserBalanceInsufficient'); // Inform Phaser specifically
        return;
    }

    isSpinning.value = true;
    clearErrorObject();
    // Inform Phaser that spin is starting (e.g., for UI updates in Phaser)
    EventBus.emit('vueSpinInitiated', { betAmount });

    console.log(`Vue: Dispatching spin action with bet: ${betAmount}`);
    try {
        // The Vuex 'spin' action makes the API call and updates user balance in store on success.
        const response = await store.dispatch('spin', { bet_amount: betAmount });

        if (response.status) {
            // The Vuex action should have updated the user's balance.
            // The API response (containing spin_result, win_amount etc.) is passed to Phaser.
            // Phaser's GameScene should listen for an event like 'vueSpinResult' to start animations.
            EventBus.emit('vueSpinResult', response);
        } else {
            // Error from Vuex action (e.g., API error)
            errorObject.value = response;
            EventBus.emit('spinError', { message: response.status_message || "Spin failed." }); // Inform Phaser
        }
    } catch (err) {
        console.error("Vue: Error during spin action dispatch:", err);
        const message = err.status_message || "An unexpected error occurred during spin.";
        errorObject.value = { status_message: message };
        EventBus.emit('spinError', { message }); // Inform Phaser
    } finally {
        isSpinning.value = false;
        // Inform Phaser spin has concluded (either success or fail)
        EventBus.emit('vueSpinConcluded');
    }
};


const endGameSession = async () => {
  if (gameSessionId.value) {
    try {
      console.log("Ending game session:", gameSessionId.value);
      await store.dispatch('endSession');
      gameSessionId.value = null;
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch (err) {
      console.error("Failed to end game session:", err);
      localStorage.removeItem(SESSION_STORAGE_KEY); // Still clear if API fails
    }
  }
};

onBeforeUnmount(async () => {
  console.log("Slot.vue: Cleaning up Phaser game instance and event listeners.");

  // Remove Event Bus Listeners
  EventBus.off('phaserSpinResult', handlePhaserSpinResult);
  EventBus.off('phaserBalanceInsufficient', handlePhaserBalanceInsufficient);
  EventBus.off('phaserError', handlePhaserError);
  EventBus.off('requestBalanceUpdate', handlePhaserRequestBalanceUpdate);
  EventBus.off('spinCommand', handlePhaserSpinCommand);

  await endGameSession();

  if (game.value) {
    game.value.destroy(true);
    game.value = null;
  }
});

</script>

<style scoped>
.slot-page {
  /* Provides a background for the entire view */
}

.slot-container {
  /* Styles for the container holding the Phaser canvas */
  width: 100%;
  /* max-width: 820px; */ /* Let max-w-4xl handle width */
  aspect-ratio: 4 / 3; /* Maintain aspect ratio, adjust as needed */
  max-height: calc(100vh - 250px); /* Limit height on tall screens */
  position: relative; /* Needed for absolute positioning of overlay */
}

#phaser-slot-machine {
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

