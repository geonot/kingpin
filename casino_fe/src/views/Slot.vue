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
<div class="mt-4 p-4 bg-white dark:bg-dark-card rounded-lg shadow-md text-center">
    <h2 class="text-xl font-bold dark:text-white">{{ slotInfo?.name || 'Loading Slot...' }}</h2>
    <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">{{ slotInfo?.description }}</p>
    <div v-if="currentMultiplierDisplay > 1"
         class="text-lg font-bold text-yellow-400 dark:text-yellow-300 animate-pulse">
      Multiplier: x{{ currentMultiplierDisplay }}
    </div>
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
const currentMultiplierDisplay = ref(1); // For cascading win multiplier

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
    if (slotInfo.value.asset_directory) {
      loadingMessage.value = `Loading game configuration for ${slotInfo.value.name}...`;
      try {
        // Serve gameConfig.json directly from Vue.js frontend public directory
        // asset_directory is like '/slot1/', so we remove the leading slash to get 'slot1/'
        const gameConfigPath = `/${slotInfo.value.asset_directory.replace(/^\//, '')}gameConfig.json`;
        const response = await axios.get(gameConfigPath);
        slotGameJsonConfigContent.value = response.data;
        console.log(`Successfully loaded gameConfig.json from ${gameConfigPath}`);
      } catch (err) {
        console.error(`Failed to load gameConfig.json from ${slotInfo.value.asset_directory}:`, err);
        errorObject.value = { status_message: `Could not load detailed game configuration for ${slotInfo.value.name}. Some features might be unavailable or use defaults.` };
      }
    } else {
      console.error('Slot asset_directory is missing, cannot load gameConfig.json.');
      errorObject.value = { status_message: 'Critical slot asset directory missing, cannot load game configuration.' };
    }
  } else {
    console.error(`Slot with ID ${slotId} not found or API fetch failed.`);
    errorObject.value = fetchedSlotInfo || { status_message: 'Could not load slot information from API.'};
  }
};


const joinGameAndInitPhaser = async (slotId) => {
    isLoading.value = true;
    loadingMessage.value = 'Joining game session...';
    clearErrorObject();
    
    if (!slotInfo.value || !slotInfo.value.short_name) {
        await fetchSlotDetailsAndConfig(slotId);
        if (!slotInfo.value || errorObject.value) {
            isLoading.value = false;
            return;
        }
    }

    localStorage.setItem(SLOT_ID_STORAGE_KEY, slotId.toString());
    const existingSessionId = localStorage.getItem(SESSION_STORAGE_KEY);

    if (existingSessionId && isAuthenticated.value) {
        gameSessionId.value = existingSessionId;
        console.log('Attempting to reuse existing game session:', gameSessionId.value);
    } else if (isAuthenticated.value) {
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
            return;
        }
    } else {
        console.log('User not authenticated, proceeding without game session.');
        gameSessionId.value = null;
        localStorage.removeItem(SESSION_STORAGE_KEY);
    }

    startPhaserGame(slotId);
};

const startPhaserGame = (slotId) => {
  if (game.value) {
    console.warn("Phaser game already exists. Destroying previous instance.");
    game.value.destroy(true); game.value = null;
  }
  loadingMessage.value = 'Initializing game engine...';
  const parentElement = document.getElementById('phaser-slot-machine');
  if (!parentElement) {
    console.error("Phaser parent element 'phaser-slot-machine' not found.");
    errorObject.value = { status_message: "Internal error: Could not initialize game display." };
    isLoading.value = false; return;
  }

  const mergedConfig = {
    ...phaserConfig,
    parent: 'phaser-slot-machine',
    callbacks: {
      preBoot: (bootingGame) => {
        bootingGame.registry.set('slotIdFromVue', slotId);
      },
      postBoot: (bootedGame) => {
        bootedGame.registry.set('userBalance', userBalance.value);
        bootedGame.registry.set('slotApiData', slotInfo.value);
        bootedGame.registry.set('slotGameJsonConfig', slotGameJsonConfigContent.value);
        bootedGame.registry.set('soundEnabled', soundEnabled.value);
        bootedGame.registry.set('turboEnabled', turboEnabled.value);
        bootedGame.registry.set('eventBus', EventBus);
        console.log('Phaser game booted. Initial data (API, JSON config, settings) set in registry.');
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
    // Update multiplier display based on backend response (passed from GameScene via EventBus)
    if (result.current_multiplier_level && slotGameJsonConfigContent.value?.game?.win_multipliers) {
        const level = result.current_multiplier_level;
        const multipliers = slotGameJsonConfigContent.value.game.win_multipliers;
        if (level > 0 && multipliers && multipliers.length > 0) {
            // Assuming level is 1-based for display (e.g. level 1 is index 0 of multipliers array)
            currentMultiplierDisplay.value = multipliers[Math.min(level - 1, multipliers.length - 1)];
        } else {
            currentMultiplierDisplay.value = 1; // Default to 1x if no level or no multipliers defined
        }
    } else if (Object.prototype.hasOwnProperty.call(result, 'current_multiplier_level')) {
        // If current_multiplier_level is explicitly 0 or multipliers are missing, reset to 1.
        currentMultiplierDisplay.value = 1;
    }
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
        await store.dispatch('fetchUserProfile');
        EventBus.$emit('vueBalanceUpdated', { balance: store.getters.currentUser?.balance });
    } catch (err) {
        console.error("Vue: Error fetching user profile for balance update:", err);
    }
};

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
    await store.dispatch('fetchUserProfile');
    await fetchSlotDetailsAndConfig(slotIdNum);

    if (slotInfo.value && !errorObject.value) {
      await joinGameAndInitPhaser(slotIdNum);
    } else {
      isLoading.value = false;
    }
  } catch (err) {
    console.error("Slot page initialization failed:", err);
    if (!errorObject.value) {
        errorObject.value = { status_message: 'Failed to initialize slot game.' };
    }
    isLoading.value = false;
  }

  EventBus.$on('phaserSpinResult', handlePhaserSpinResult);
  EventBus.$on('phaserBalanceInsufficient', handlePhaserBalanceInsufficient);
  EventBus.$on('phaserError', handlePhaserError);
  EventBus.$on('requestBalanceUpdate', handlePhaserRequestBalanceUpdate);
  EventBus.$on('spinRequest', handlePhaserSpinCommand); // Changed from 'spinCommand' to 'spinRequest'
});

const handlePhaserSpinCommand = async (payload) => {
    if (isSpinning.value) {
        console.warn("Vue: Spin command ignored, already spinning.");
        EventBus.$emit('spinReject', { message: 'Already spinning.' });
        return;
    }
    if (!isAuthenticated.value) {
        errorObject.value = { status_message: "Please log in to play." };
        EventBus.$emit('spinError', { message: 'User not authenticated.' });
        return;
    }

    const betAmount = payload.betAmount;
    
    // Better error handling for insufficient balance
    if (userBalance.value <= 0) {
        errorObject.value = { 
            status_message: 'You have no balance. Please deposit funds to start playing.',
            actionButton: {
                text: 'Deposit Funds',
                action: () => router.push('/deposit')
            }
        };
        EventBus.$emit('phaserBalanceInsufficient');
        return;
    } else if (userBalance.value < betAmount) {
        errorObject.value = { 
            status_message: `Insufficient balance. You need ${formatSatsToBtc(betAmount)} BTC but only have ${formatSatsToBtc(userBalance.value)} BTC.`,
            actionButton: {
                text: 'Deposit More',
                action: () => router.push('/deposit')
            }
        };
        EventBus.$emit('phaserBalanceInsufficient');
        return;
    }

    isSpinning.value = true;
    clearErrorObject();
    EventBus.$emit('vueSpinInitiated', { betAmount });

    console.log(`Vue: Dispatching spin action with bet: ${betAmount}`);
    try {
        const response = await store.dispatch('spin', { bet_amount: betAmount });

        if (response.status) {
            EventBus.$emit('vueSpinResult', response);

            if (response.current_multiplier_level && slotGameJsonConfigContent.value?.game?.win_multipliers) {
                const level = response.current_multiplier_level;
                const multipliers = slotGameJsonConfigContent.value.game.win_multipliers;
                if (level > 0 && multipliers && multipliers.length > 0) {
                    currentMultiplierDisplay.value = multipliers[Math.min(level - 1, multipliers.length - 1)];
                } else {
                    currentMultiplierDisplay.value = 1;
                }
            } else {
                currentMultiplierDisplay.value = 1;
            }
        } else {
            // Enhanced error handling for backend responses
            if (response.status_message && response.status_message.includes('Insufficient balance')) {
                if (userBalance.value <= 0) {
                    errorObject.value = { 
                        status_message: 'You have no balance. Please deposit funds to start playing.',
                        actionButton: {
                            text: 'Deposit Funds',
                            action: () => router.push('/deposit')
                        }
                    };
                } else {
                    errorObject.value = { 
                        status_message: `Insufficient balance. You need ${formatSatsToBtc(betAmount)} BTC but only have ${formatSatsToBtc(userBalance.value)} BTC.`,
                        actionButton: {
                            text: 'Deposit More',
                            action: () => router.push('/deposit')
                        }
                    };
                }
            } else {
                errorObject.value = response;
            }
            EventBus.$emit('spinError', { message: response.status_message || "Spin failed." });
            currentMultiplierDisplay.value = 1;
        }
    } catch (err) {
        console.error("Vue: Error during spin action dispatch:", err);
        const message = err.status_message || "An unexpected error occurred during spin.";
        errorObject.value = { status_message: message };
        EventBus.$emit('spinError', { message });
        currentMultiplierDisplay.value = 1;
    } finally {
        isSpinning.value = false;
        EventBus.$emit('vueSpinConcluded');
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
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }
};

onBeforeUnmount(async () => {
  console.log("Slot.vue: Cleaning up Phaser game instance and event listeners.");

  EventBus.$off('phaserSpinResult', handlePhaserSpinResult);
  EventBus.$off('phaserBalanceInsufficient', handlePhaserBalanceInsufficient);
  EventBus.$off('phaserError', handlePhaserError);
  EventBus.$off('requestBalanceUpdate', handlePhaserRequestBalanceUpdate);
  EventBus.$off('spinRequest', handlePhaserSpinCommand); // Changed from 'spinCommand' to 'spinRequest'

  currentMultiplierDisplay.value = 1; // Reset multiplier on unmount

  await endGameSession();

  if (game.value) {
    game.value.destroy(true);
    game.value = null;
  }
});

</script>

<style scoped>
.slot-page {
}

.slot-container {
  width: 100%;
  aspect-ratio: 4 / 3;
  max-height: calc(100vh - 250px);
  position: relative;
}

#phaser-slot-machine {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: inherit;
}

.loading-overlay {
}

.loading-spinner {
  border-radius: 50%;
  border: 4px solid rgba(255, 215, 0, 0.3);
  border-top-color: #FFD700;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-message {
}
</style>
