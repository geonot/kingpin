<template>
  <router-link
    :to="{ name: 'Slot', params: { id: slotData.id } }"
    class="slot-card block bg-white dark:bg-dark-card rounded-lg shadow-md hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-light-purple/20 overflow-hidden transform transition-all duration-300 hover:-translate-y-1 group"
  >
    <div class="h-48 bg-gradient-to-br from-gray-300 to-gray-400 dark:from-gray-700 dark:to-gray-800 flex items-center justify-center text-gray-500 dark:text-gray-400">
       <img v-if="imageUrl" :src="imageUrl" :alt="slotData.name" class="w-full h-full object-cover">
       <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-300 to-gray-400 dark:from-gray-700 dark:to-gray-800">
        <i class="fas fa-image text-6xl opacity-50 text-gray-500 dark:text-gray-400"></i>
       </div>
    </div>
    <div class="p-5">
      <h3 class="text-xl font-semibold text-gray-800 dark:text-white mb-2 truncate group-hover:text-royal-blue dark:group-hover:text-light-purple transition-colors">
        {{ slotData.name }}
      </h3>
      <p class="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-2">
        {{ slotData.description || 'No description available.' }}
      </p>
      <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
        <span class="flex items-center">
          <i class="fas fa-th-large mr-1"></i> <!-- Icon -->
          {{ slotData.num_rows }}x{{ slotData.num_columns }} Grid
        </span>
        <span class="flex items-center">
           <i class="fas fa-atom mr-1"></i> <!-- Icon -->
          {{ slotData.num_symbols }} Symbols
        </span>
        <span v-if="slotData.rtp" class="flex items-center font-medium text-green-600 dark:text-green-400">
           <i class="fas fa-percent mr-1"></i> <!-- Icon -->
          {{ slotData.rtp.toFixed(2) }}% RTP
        </span>
      </div>
    </div>
    <!-- Play Button Overlay (Optional) -->
    <div class="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <span class="text-white text-lg font-semibold border-2 border-white rounded-full px-6 py-2">Play Now</span>
    </div>
  </router-link>
</template>

/* eslint-disable no-undef */
<script setup>
import { computed } from 'vue';

// eslint-disable-next-line no-undef
const props = defineProps({
  slotData: {
    type: Object,
    required: true,
  },
});

const getSlotImageUrl = (slotItem) => {
  // Prioritize thumbnail_url if it exists in slot data from API
  if (slotItem.thumbnail_url) return slotItem.thumbnail_url;
  // Fallback to constructing path from short_name
  if (slotItem.short_name) {
    // In Vite, public assets are served from the root.
    // If assets are in public/slot1/background.png, then path is /slot1/background.png
    // This assumes a consistent naming convention.
    return `/${slotItem.short_name}/background.png`; // Corrected path
  }
  // Further fallback or generic placeholder handled in template
  return null;
};

const imageUrl = computed(() => getSlotImageUrl(props.slotData));
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
