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
    <error-message :error="errorObject" @dismiss="errorObject = null" class="my-8" />

    <!-- Empty state -->
    <div v-if="!loading && !errorObject && filteredSlots.length === 0" class="text-center my-20 py-10 bg-gray-50 dark:bg-gray-800 rounded-lg shadow">
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
      <slot-card
        v-for="slot in filteredSlots"
        :key="slot.id"
        :slot="slot"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useStore } from 'vuex';
import ErrorMessage from '@components/ErrorMessage.vue'; // Import ErrorMessage
import SlotCard from '@components/SlotCard.vue'; // Import SlotCard

// Ensure FontAwesome is loaded (e.g., via main.js or index.html)

const store = useStore();
const search = ref('');
const loading = ref(true);
const errorObject = ref(null); // Changed from error to errorObject

// Access state using computed
const slots = computed(() => store.getters.getSlots); // Use getter

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
  loading.value = true;
  errorObject.value = null;
  try {
    // fetchSlots action now returns an object like { status, slots, status_message }
    const response = await store.dispatch('fetchSlots');
    if (!response.status) {
      errorObject.value = response; // Store the error object { status, status_message }
    }
    // Slots are committed to store by the action itself if successful
  } catch (err) { // Catch unexpected errors during dispatch
    console.error('System error loading slots:', err);
    errorObject.value = { status_message: 'Failed to load slot games due to a system error.' };
  } finally {
    loading.value = false;
  }
});

// getSlotImageUrl is now handled within SlotCard.vue
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


