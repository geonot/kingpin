<template>
  <div class="container mx-auto mt-10 px-4">
    <div class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
      <h2 class="text-3xl md:text-4xl font-bold text-gray-800 dark:text-gray-100">Available Slots</h2>
      <div class="relative w-full md:w-1/3">
        <input
          type="text"
          v-model="search"
          placeholder="Search slots..."
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
      <span class="ml-4 text-xl text-gray-600 dark:text-gray-300">Loading Games...</span>
    </div>

    <!-- Error message -->
    <div v-else-if="error" class="bg-red-100 dark:bg-red-900 border border-red-400 dark:border-red-700 text-red-700 dark:text-red-100 px-6 py-4 rounded-md my-8 shadow">
      <strong class="font-bold">Oops!</strong>
      <span class="block sm:inline ml-2">{{ error }}</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="filteredSlots.length === 0" class="text-center my-20 py-10 bg-gray-50 dark:bg-gray-800 rounded-lg shadow">
      <i class="fas fa-ghost text-5xl text-gray-400 dark:text-gray-500 mb-4"></i>
      <p v-if="search" class="text-xl text-gray-600 dark:text-gray-300">
        No slots found matching "<strong>{{ search }}</strong>".
      </p>
      <p v-else class="text-xl text-gray-600 dark:text-gray-300">
        No slots available at the moment. Check back soon!
      </p>
    </div>

    <!-- Slots grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
      <router-link
        v-for="slot in filteredSlots"
        :key="slot.id"
        :to="{ name: 'Slot', params: { id: slot.id } }"
        class="slot-card block bg-white dark:bg-dark-card rounded-lg shadow-md hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-light-purple/20 overflow-hidden transform transition-all duration-300 hover:-translate-y-1 group"
      >
        <!-- Placeholder for Slot Image -->
        <div class="h-48 bg-gradient-to-br from-gray-300 to-gray-400 dark:from-gray-700 dark:to-gray-800 flex items-center justify-center text-gray-500 dark:text-gray-400">
           <!-- Use actual image if available: <img :src="slot.thumbnail_url || defaultThumbnail" alt="" class="w-full h-full object-cover"> -->
           <i class="fas fa-image text-6xl opacity-50"></i>
           <span class="ml-2">Image for {{ slot.name }}</span>
        </div>
        <div class="p-5">
          <h3 class="text-xl font-semibold text-gray-800 dark:text-white mb-2 truncate group-hover:text-royal-blue dark:group-hover:text-light-purple transition-colors">
            {{ slot.name }}
          </h3>
          <p class="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-2">
            {{ slot.description || 'No description available.' }}
          </p>
          <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
            <span class="flex items-center">
              <i class="fas fa-th-large mr-1"></i> <!-- Icon -->
              {{ slot.num_rows }}x{{ slot.num_columns }} Grid
            </span>
            <span class="flex items-center">
               <i class="fas fa-atom mr-1"></i> <!-- Icon -->
              {{ slot.num_symbols }} Symbols
            </span>
            <span v-if="slot.rtp" class="flex items-center font-medium text-green-600 dark:text-green-400">
               <i class="fas fa-percent mr-1"></i> <!-- Icon -->
              {{ slot.rtp.toFixed(2) }}% RTP
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
// Ensure FontAwesome is loaded (e.g., via main.js or index.html)

const store = useStore();
const search = ref('');
const loading = ref(true);
const error = ref(null);

// Access state using computed
const slots = computed(() => store.state.slots);

// Filtered slots based on search input
const filteredSlots = computed(() => {
  if (!slots.value) return [];
  const searchTerm = search.value.toLowerCase().trim();
  if (!searchTerm) {
    return slots.value.filter(slot => slot.is_active); // Only show active slots
  }
  return slots.value.filter(slot =>
    slot.is_active && // Only search active slots
    (slot.name.toLowerCase().includes(searchTerm) ||
     (slot.description && slot.description.toLowerCase().includes(searchTerm)))
  );
});

// Fetch slots when component is mounted
onMounted(async () => {
  try {
    loading.value = true;
    error.value = null;
    // Only fetch if not already loaded, or implement cache expiry
    if (!store.state.slotsLoaded) {
        await store.dispatch('fetchSlots');
    }
  } catch (err) {
    error.value = 'Failed to load slot games. Please refresh the page or try again later.';
    console.error('Error loading slots:', err);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
/* Custom styles for slot cards or specific elements */
.slot-card {
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


