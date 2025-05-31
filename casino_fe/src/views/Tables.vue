<template>
  <div class="container mx-auto mt-10 px-4">
    <div class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
      <h2 class="text-3xl md:text-4xl font-bold text-gray-800 dark:text-gray-100">Table Games</h2>
      <div class="relative w-full md:w-1/3">
        <input
          type="text"
          v-model="search"
          placeholder="Search tables..."
          class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white"
        />
        <span class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400">
          <i class="fas fa-search"></i> <!-- Assuming FontAwesome -->
        </span>
      </div>
    </div>

    <!-- Loading indicator -->
    <div v-if="loading" class="flex justify-center items-center my-20">
      <div class="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-royal-blue dark:border-light-purple"></div>
      <span class="ml-4 text-xl text-gray-600 dark:text-gray-300">Loading Tables...</span>
    </div>

    <!-- Error message -->
    <error-message :error="errorObject" @dismiss="errorObject = null" class="my-8" />

    <!-- Empty state -->
    <div v-if="!loading && !errorObject && filteredTables.length === 0" class="text-center my-20 py-10 bg-gray-50 dark:bg-gray-800 rounded-lg shadow">
      <i class="fas fa-ghost text-5xl text-gray-400 dark:text-gray-500 mb-4"></i>
      <p v-if="search" class="text-xl text-gray-600 dark:text-gray-300">
        No tables found matching "<strong>{{ search }}</strong>".
      </p>
      <p v-else class="text-xl text-gray-600 dark:text-gray-300">
        No tables available at the moment. Check back soon!
      </p>
    </div>

    <!-- Tables grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
      <router-link
        v-for="table in filteredTables"
        :key="table.id"
        :to="{ name: 'Blackjack', params: { id: table.id } }"
        class="table-card block bg-white dark:bg-dark-card rounded-lg shadow-md hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-light-purple/20 overflow-hidden transform transition-all duration-300 hover:-translate-y-1 group"
      >
        <!-- Placeholder for Table Image -->
        <div class="h-48 bg-gradient-to-br from-green-800 to-green-900 dark:from-green-900 dark:to-black flex items-center justify-center text-white">
          <i class="fas fa-cards text-6xl opacity-50"></i>
          <span class="ml-2 text-2xl font-bold">{{ table.name }}</span>
        </div>
        <div class="p-5">
          <h3 class="text-xl font-semibold text-gray-800 dark:text-white mb-2 truncate group-hover:text-royal-blue dark:group-hover:text-light-purple transition-colors">
            {{ table.name }}
          </h3>
          <p class="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-2">
            {{ table.description || 'No description available.' }}
          </p>
          <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
            <span class="flex items-center">
              <i class="fas fa-coins mr-1"></i> <!-- Icon -->
              Min Bet: {{ formatSatsToBtc(table.min_bet) }} BTC
            </span>
            <span class="flex items-center">
              <i class="fas fa-coins mr-1"></i> <!-- Icon -->
              Max Bet: {{ formatSatsToBtc(table.max_bet) }} BTC
            </span>
            <span class="flex items-center font-medium text-green-600 dark:text-green-400">
              <i class="fas fa-dice mr-1"></i> <!-- Icon -->
              {{ table.deck_count }} Decks
            </span>
          </div>
        </div>
        <!-- Play Button Overlay (Optional) -->
        <div class="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <span class="text-white text-lg font-semibold border-2 border-white rounded-full px-6 py-2">Play Now</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useStore } from 'vuex';
import { formatSatsToBtc } from '@utils/currencyFormatter';
import ErrorMessage from '@components/ErrorMessage.vue'; // Import ErrorMessage

const store = useStore();
const search = ref('');
const loading = ref(true);
const errorObject = ref(null); // Changed from error to errorObject

// Access state using computed
const tables = computed(() => store.getters.getTables); // Use getter

// Filtered tables based on search input
const filteredTables = computed(() => {
  if (!tables.value) return [];
  const searchTerm = search.value.toLowerCase().trim();
  if (!searchTerm) {
    return tables.value.filter(table => table.is_active); // Only show active tables
  }
  return tables.value.filter(table =>
    table.is_active && // Only search active tables
    (table.name.toLowerCase().includes(searchTerm) ||
     (table.description && table.description.toLowerCase().includes(searchTerm)))
  );
});

// Fetch tables when component is mounted
onMounted(async () => {
  loading.value = true;
  errorObject.value = null;
  try {
    // fetchTables action now returns an object like { status, tables, status_message }
    const response = await store.dispatch('fetchTables');
    if (!response.status) {
      errorObject.value = response; // Store the error object { status, status_message }
    }
    // Tables are committed to store by the action itself if successful
  } catch (err) { // Catch unexpected errors during dispatch
    console.error('System error loading tables:', err);
    errorObject.value = { status_message: 'Failed to load table games due to a system error.' };
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
/* Custom styles for table cards or specific elements */
.table-card {
  text-decoration: none; /* Remove underline from router-link */
}

/* Improve line clamping for description */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>