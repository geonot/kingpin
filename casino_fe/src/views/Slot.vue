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
<error-message v-if="isErrorVisible" :message="errorMessage" @dismiss="clearErrorMessage" class="mb-4" />

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
const errorMessage = ref(null);
const isErrorVisible = ref(false);
const slotInfo = ref(null); // To store details about the current slot
const isSpinning = ref(false); // Prevent concurrent spins

// Constants for localStorage keys
const SESSION_STORAGE_KEY = 'slotGameSessionId';
const SLOT_ID_STORAGE_KEY = 'currentSlotId';

const user = computed(() => store.state.user);
const userBalance = computed(() => store.state.user?.balance ?? 0);
const isAuthenticated = computed(() => store.getters.isAuthenticated);

const clearErrorMessage = () => {
errorMessage.value = null;
isErrorVisible.value = false;
};

const fetchSlotDetails = async (slotId) => {
// Check if slots are loaded, if not fetch them
if (!store.state.slotsLoaded) {
try {
await store.dispatch('fetchSlots');
} catch (err) {
console.error("Failed to fetch slot list:", err);
// Handle error appropriately, maybe redirect or show static error
}
}
// Find the specific slot from the store
slotInfo.value = store.getters.getSlotById(slotId);
if (!slotInfo.value) {
console.error(`Slot with ID ${slotId} not found in store.`);
errorMessage.value = 'Could not load slot information. Please try again.';
isErrorVisible.value = true;
// Optionally redirect back
// router.push('/slots');
}
};

const joinGame = async (slotId) => {
    isLoading.value = true;
    loadingMessage.value = 'Joining game session...';
    clearErrorMessage();
    
    // Store the current slot ID in localStorage
    localStorage.setItem(SLOT_ID_STORAGE_KEY, slotId.toString());
    
    // Check if we have an existing session ID in localStorage
    const existingSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    
    if (existingSessionId && isAuthenticated.value) {
        // Instead of verifying with a separate API call, we'll just try to use the existing session
        // If any API calls fail with a session error, we'll create a new session then
        gameSessionId.value = existingSessionId;
        console.log('Attempting to reuse existing game session:', gameSessionId.value);
        isLoading.value = false;
        return;
    }
    
    // Create a new session
    try {
        const response = await store.dispatch('joinGame', {
            slot_id: slotId,
            game_type: 'slot' // Explicitly set game_type
        });
        
        if (response.status && response.session_id) {
            gameSessionId.value = response.session_id;
            // Store the session ID in localStorage
            localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
            console.log('Joined new game session:', gameSessionId.value);
        } else {
            throw new Error(response.status_message || 'Failed to join game session.');
        }
    } catch (error) {
        console.error('Error joining game:', error);
        errorMessage.value = `Failed to join game: ${error.message}. Please ensure you are logged in and try again.`;
        isErrorVisible.value = true;
        isLoading.value = false; // Stop loading on error
        // Potentially redirect if join fails critically
        // router.push('/slots');
        throw error; // Re-throw to prevent Phaser initialization
    }
};

const startPhaserGame = (slotId) => {
if (game.value) {
console.warn("Phaser game already exists. Destroying previous instance.");
game.value.destroy(true);
game.value = null;
}

loadingMessage.value = 'Loading game assets...';

// Ensure the parent element exists
const parentElement = document.getElementById('phaser-slot-machine');
if (!parentElement) {
console.error("Phaser parent element 'phaser-slot-machine' not found.");
errorMessage.value = "Internal error: Could not initialize game display.";
isErrorVisible.value = true;
isLoading.value = false;
return;
}

// Merge Phaser config with dynamic data
const mergedConfig = {
  ...phaserConfig,
  parent: 'phaser-slot-machine', // Explicitly set parent container ID
  callbacks: {
    preBoot: (bootingGame) => {
      // Set the slotId in the registry before any scenes start
      bootingGame.registry.set('slotId', slotId);
      console.log(`Pre-boot: Setting slotId ${slotId} in registry`);
    },
    postBoot: (bootedGame) => {
      // Pass additional data to Phaser scenes via game registry or globals
      bootedGame.registry.set('userBalance', userBalance.value);
      bootedGame.registry.set('slotConfig', slotInfo.value); // Pass fetched slot info
      bootedGame.registry.set('initialBet', slotInfo.value?.bets?.[0]?.bet_amount || 10); // Example: default to first bet option
      console.log('Phaser game booted. Initial data set.');
      isLoading.value = false; // Hide loading overlay once Phaser is ready
    }
  }
};


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

const handleSpinRequest = async ({ bet }) => {
if (isSpinning.value) {
console.warn('Spin request ignored, already spinning.');
return;
}
if (!isAuthenticated.value) {
errorMessage.value = "Please log in to play.";
isErrorVisible.value = true;
return;
}
isSpinning.value = true;
clearErrorMessage();
// Optionally show a subtle loading state on the spin button in UIScene via EventBus?
// EventBus.$emit('spinStateChanged', { spinning: true });

console.log(`Handling spin request. Bet: ${bet} Sats`);

try {
await spin(bet);
} catch(error) {
// Error already handled within spin() or by global error handler
console.error("Spin request failed:", error);
} finally {
isSpinning.value = false;
// EventBus.$emit('spinStateChanged', { spinning: false });
}
};

const spin = async (betAmountSats) => {
if (!gameSessionId.value) {
errorMessage.value = 'No active game session. Please rejoin the game.';
isErrorVisible.value = true;
throw new Error('No game session ID for spin');
}
if (betAmountSats <= 0) {
errorMessage.value = 'Invalid bet amount.';
isErrorVisible.value = true;
throw new Error('Invalid bet amount');
}
if (userBalance.value < betAmountSats) {
errorMessage.value = 'Insufficient balance for this bet.';
isErrorVisible.value = true;
// Send event to Phaser UI to potentially disable spin button
EventBus.$emit('uiUpdate', { balanceInsufficient: true });
throw new Error('Insufficient balance');
}

try {
const payload = {
bet_amount: betAmountSats,
// game_session_id is derived on backend from JWT/user
};
console.log('Dispatching spin action with payload:', payload);

        // IMPORTANT: We're NOT updating the store balance here anymore
        // The balance deduction happens in handleBalanceDeduction
        // The win amount addition happens in handleSpinAnimationComplete
        
        // Make the API call but don't update the balance yet
        const response = await axios.post('/api/spin', payload, {
            headers: {
                'Authorization': `Bearer ${store.state.userSession}`,
                'Content-Type': 'application/json'
            }
        });
        
        const data = response.data;
        console.log('Received spin response:', data);

        if (data.status) {
            // Send result to Phaser GameScene to animate reels
            // Ensure GameScene exists and is ready
            const gameScene = game.value?.scene.getScene('GameScene');
            if (gameScene && gameScene.scene.isActive()) {
                 gameScene.handleSpinResult(data); // Call method in GameScene
            } else {
                 console.error('GameScene not found or inactive, cannot display spin result.');
                 errorMessage.value = 'Game error: Could not display spin result.';
                 isErrorVisible.value = true;
                 
                 // If we can't display the animation, update the balance immediately with full amount
                 store.commit('updateUserBalance', data.user.balance);
                 EventBus.$emit('uiUpdate', {
                    balance: data.user.balance
                 });
            }
            
            return data;

        } else {
            errorMessage.value = data.status_message || 'Spin request failed. Please try again.';
            isErrorVisible.value = true;
            // Potentially update UI state in Phaser
            EventBus.$emit('spinError', { message: errorMessage.value });
            throw new Error(errorMessage.value);
        }
    } catch (error) {
        console.error('Error during spin dispatch:', error);
        
        // Check if the error is related to an invalid session
        if (error.response?.status === 404 &&
            (error.response?.data?.status_message?.includes('No active game session') ||
             error.response?.data?.status_message?.includes('session'))) {
            
            console.log('Session error detected, attempting to create a new session');
            
            try {
                // Get the slot ID from localStorage or route params
                const slotId = Number(localStorage.getItem(SLOT_ID_STORAGE_KEY) || route.params.id);
                
                // Create a new session
                await joinGame(slotId);
                
                // Retry the spin with the new session
                console.log('New session created, retrying spin');
                return await spin(betAmountSats);
            } catch (sessionError) {
                console.error('Failed to create new session:', sessionError);
                errorMessage.value = 'Session expired. Failed to create a new session.';
                isErrorVisible.value = true;
                EventBus.$emit('spinError', { message: errorMessage.value });
                throw sessionError;
            }
        }
        
        // For other errors
        if (!errorMessage.value) {
            errorMessage.value = 'Spin failed due to a network or server error.';
        }
        isErrorVisible.value = true;
        EventBus.$emit('spinError', { message: errorMessage.value });
        throw error; // Re-throw for handleSpinRequest's finally block
    }
};

// Handle balance deduction when spin button is clicked
const handleBalanceDeduction = (betAmount) => {
    if (userBalance.value >= betAmount) {
        // Calculate new balance after deduction
        const newBalance = userBalance.value - betAmount;
        
        // Update store with deducted balance
        store.commit('updateUserBalance', newBalance);
        
        // Update UI with deducted balance
        EventBus.$emit('uiUpdate', {
            balance: newBalance
        });
        
        console.log(`Deducted ${betAmount} from balance, new balance: ${newBalance}`);
    }
};

// Handle spin animation completion - add win amount to balance
const handleSpinAnimationComplete = (response) => {
    if (response && response.status) {
        // Only add the win amount to the current balance
        const winAmount = response.win_amount || 0;
        
        if (winAmount > 0) {
            // Get current balance and add win amount
            const currentBalance = store.state.user?.balance || 0;
            const newBalance = currentBalance + winAmount;
            
            // Update store with new balance including win
            store.commit('updateUserBalance', newBalance);
            
            // Update UI with new balance and win amount
            EventBus.$emit('uiUpdate', {
                balance: newBalance,
                winAmount: winAmount
            });
            
            console.log(`Added win amount ${winAmount} to balance, new balance: ${newBalance}`);
        } else {
            console.log('No win amount to add to balance');
        }
    }
};
// Fetch the user's current profile from the backend
const fetchUserData = async () => {
    try {
        // Fetch the user's profile to get the current balance
        await store.dispatch('fetchUserProfile');
        console.log('User profile fetched, balance:', userBalance.value);
        return true;
    } catch (error) {
        console.error('Error fetching user profile:', error);
        errorMessage.value = 'Failed to fetch user profile. Please refresh the page.';
        isErrorVisible.value = true;
        return false;
    }
};

// --- Lifecycle Hooks ---
onMounted(async () => {
    if (!isAuthenticated.value) {
        // Redirect to login if not authenticated
        router.push({ name: 'Login', query: { redirect: route.fullPath } });
        return;
    }

    const slotId = Number(route.params.id);
    if (isNaN(slotId)) {
        errorMessage.value = 'Invalid Slot ID.';
        isErrorVisible.value = true;
        isLoading.value = false;
        return;
    }

    try {
        // First fetch the user's profile to get the current balance
        const profileFetched = await fetchUserData();
        if (!profileFetched) {
            isLoading.value = false;
            return;
        }

        await fetchSlotDetails(slotId); // Fetch details first
        if (slotInfo.value) { // Proceed only if slot info loaded
            await joinGame(slotId); // Then join the game session
            startPhaserGame(slotId); // Finally start Phaser
            // Register event listener for spin requests from Phaser UI
            EventBus.$on('spinRequest', handleSpinRequest);
            // Register event listener for spin requests from Phaser UI
            EventBus.$on('spinRequest', handleSpinRequest);
            // Register event listener for spin animation completion
            EventBus.$on('spinAnimationComplete', handleSpinAnimationComplete);
            // Register event listener for balance deduction request
            EventBus.$on('getBalanceForDeduction', handleBalanceDeduction);
        } else {
             // Error handled within fetchSlotDetails
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
            
            // Clear the session ID from localStorage
            localStorage.removeItem(SESSION_STORAGE_KEY);
        } catch (error) {
            console.error("Failed to end game session:", error);
            // Don't block unmounting even if this fails
            
            // Still clear the session ID from localStorage to prevent issues
            localStorage.removeItem(SESSION_STORAGE_KEY);
        }
    }
};

onBeforeUnmount(async () => {
    console.log("Destroying Phaser game instance and cleaning up event listeners.");
    // Remove event listeners
    EventBus.$off('spinRequest', handleSpinRequest);
    EventBus.$off('spinAnimationComplete', handleSpinAnimationComplete);
    EventBus.$off('getBalanceForDeduction', handleBalanceDeduction);

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

