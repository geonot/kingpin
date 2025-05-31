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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'; // Removed shallowRef, Phaser
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
// import EventBus from '@/event-bus'; // Not needed for placeholder
import ErrorMessage from '@components/ErrorMessage.vue';
import { formatSatsToBtc } from '@utils/currencyFormatter';

const store = useStore();
const route = useRoute();
const router = useRouter();

const isLoading = ref(true);
const loadingMessage = ref('Loading table information...');
const errorObject = ref(null); // For ErrorMessage.vue component
const tableInfo = ref(null);

const isAuthenticated = computed(() => store.getters.isAuthenticated);

const clearErrorObject = () => {
  errorObject.value = null;
};

const fetchTableDetailsAndConfig = async (tableId) => {
  loadingMessage.value = 'Fetching table details...';
  clearErrorObject();
  const fetchedTableInfo = await store.dispatch('fetchTableConfig', tableId);

  if (fetchedTableInfo && typeof fetchedTableInfo === 'object' && !fetchedTableInfo.status_message) {
    tableInfo.value = fetchedTableInfo;
  } else {
    console.error(`Table with ID ${tableId} not found or fetch failed.`);
    errorObject.value = fetchedTableInfo || { status_message: 'Could not load table configuration.' };
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
  await store.dispatch('fetchUserProfile'); // Ensure user balance is fresh for future use
  await fetchTableDetailsAndConfig(tableIdNum);

  if (tableInfo.value && !errorObject.value) {
    console.log(`Phaser Blackjack game instance for table ${tableIdNum} would be created here.`);
    // In a real scenario, you might still join a game session on the backend here
    // await store.dispatch('joinGame', { table_id: tableIdNum, game_type: 'blackjack' });
    // This would return a gameSessionId if needed.
    loadingMessage.value = 'Table ready (Phaser game would load here).';
    // No actual Phaser game instance for this placeholder
  }
  isLoading.value = false;
});

onBeforeUnmount(async () => {
  if (tableInfo.value) {
    console.log(`Phaser Blackjack game instance for table ${tableInfo.value.id} would be destroyed here.`);
  }
  // If a game session was started, it should be ended.
  // Example: if (gameSessionId.value) await store.dispatch('endSession');
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