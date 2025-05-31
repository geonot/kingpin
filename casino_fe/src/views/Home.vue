<template>
  <div class="home-page">
    <!-- Hero Section -->
    <div class="hero relative bg-gradient-to-r from-royal-purple via-indigo-700 to-dark-blue text-white py-40 md:py-60 text-center overflow-hidden">
      <!-- Background Overlay -->
      <div class="absolute inset-0 bg-black opacity-60 z-0"></div>
      <!-- Optional: Subtle background pattern or elements -->
      <!-- <div class="absolute inset-0 bg-hero-pattern opacity-10 z-0"></div> -->

      <div class="relative z-10 container mx-auto px-4">
        <div class="bg-black bg-opacity-70 p-6 md:p-10 rounded-xl shadow-lg max-w-3xl mx-auto">
          <h1 class="text-4xl md:text-5xl font-bold mb-4 text-gold drop-shadow-md">Welcome to Kingpin Casino</h1>
          <p class="text-xl md:text-2xl mb-8 text-gray-200">Where Every Spin Could Be Legendary!</p>
          <router-link v-if="!isAuthenticated" to="/register" class="btn-primary text-lg px-8 py-3 shadow-lg transform hover:scale-105 transition-transform duration-200">
            Join the Action Now!
          </router-link>
           <router-link v-else to="/slots" class="btn-primary text-lg px-8 py-3 shadow-lg transform hover:scale-105 transition-transform duration-200">
            Play Now!
          </router-link>
        </div>
      </div>
    </div>

    <!-- Features Section -->
    <div class="container mx-auto mt-16 px-4">
      <h2 class="text-3xl md:text-4xl font-semibold text-center mb-10 dark:text-gray-100">Why Play at Kingpin?</h2>
      <p class="text-center text-lg text-gray-600 dark:text-gray-300 max-w-4xl mx-auto mb-12">
        Experience the pinnacle of online casino gaming. We offer unique, custom-built games with high RTP, ensuring fair play and thrilling wins. Enjoy VIP treatment, instant withdrawals, and top-tier security.
      </p>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <!-- Feature Card 1 -->
        <div class="feature-card bg-white dark:bg-dark-card p-6 rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300 text-center">
          <div class="text-royal-blue dark:text-light-purple text-5xl mb-4">
            <!-- Replace with actual icon component if available -->
            <i class="fas fa-dice-d20"></i> <!-- Example FontAwesome Icon -->
          </div>
          <h3 class="text-xl font-semibold mb-3 dark:text-white">Exclusive Games</h3>
          <p class="text-gray-600 dark:text-gray-400">Play innovative slots you won't find anywhere else, designed for maximum excitement.</p>
        </div>

        <!-- Feature Card 2 -->
        <div class="feature-card bg-white dark:bg-dark-card p-6 rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300 text-center">
           <div class="text-gold dark:text-gold text-5xl mb-4">
            <i class="fas fa-trophy"></i>
          </div>
          <h3 class="text-xl font-semibold mb-3 dark:text-white">High RTP & Big Wins</h3>
          <p class="text-gray-600 dark:text-gray-400">Benefit from industry-leading Return to Player rates and chase massive jackpots.</p>
        </div>

        <!-- Feature Card 3 -->
        <div class="feature-card bg-white dark:bg-dark-card p-6 rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300 text-center">
           <div class="text-success-green dark:text-green-400 text-5xl mb-4">
             <i class="fas fa-shield-alt"></i>
          </div>
          <h3 class="text-xl font-semibold mb-3 dark:text-white">Secure & Private</h3>
          <p class="text-gray-600 dark:text-gray-400">Enjoy peace of mind with robust security, complete privacy, and instant crypto transactions.</p>
        </div>
      </div>
    </div>

    <!-- Featured Games Section -->
    <div class="container mx-auto mt-16 px-4">
      <h2 class="text-3xl md:text-4xl font-semibold text-center mb-10 dark:text-gray-100">Featured Games</h2>
      <div v-if="isLoadingGames" class="text-center dark:text-gray-300">Loading exciting games...</div>
      <div v-if="gamesError" class="text-center text-red-500 dark:text-red-400">{{ gamesError }}</div>
      <div v-if="!isLoadingGames && !gamesError && featuredSlots.length === 0" class="text-center dark:text-gray-400">
        No featured games available at the moment. Check out all our <router-link to="/slots" class="text-royal-blue dark:text-light-purple hover:underline">slots</router-link>!
      </div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 md:gap-8">
        <router-link
          v-for="slot in featuredSlots"
          :key="slot.id"
          :to="{ name: 'Slot', params: { id: slot.id } }"
          class="featured-slot-card block bg-white dark:bg-dark-card rounded-lg shadow-md hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-light-purple/20 overflow-hidden transform transition-all duration-300 hover:-translate-y-1 group"
        >
          <div class="h-40 md:h-48 w-full overflow-hidden">
            <img v-if="getSlotImageUrl(slot)" :src="getSlotImageUrl(slot)" :alt="slot.name" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110">
            <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-300 to-gray-400 dark:from-gray-700 dark:to-gray-800">
              <i class="fas fa-image text-5xl opacity-50 text-gray-500 dark:text-gray-400"></i>
            </div>
          </div>
          <div class="p-4">
            <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-1 truncate group-hover:text-royal-blue dark:group-hover:text-light-purple transition-colors">
              {{ slot.name }}
            </h3>
            <!-- <p class="text-gray-600 dark:text-gray-400 text-xs line-clamp-2">{{ slot.description || 'Exciting slot adventure!' }}</p> -->
          </div>
        </router-link>
      </div>
    </div>

     <!-- Call to Action Section (Optional) -->
     <div class="mt-20 mb-10 text-center px-4">
       <h3 class="text-2xl md:text-3xl font-semibold mb-6 dark:text-gray-100">Ready to Spin and Win?</h3>
        <router-link v-if="!isAuthenticated" to="/register" class="btn-secondary text-lg px-8 py-3 shadow-lg transform hover:scale-105 transition-transform duration-200">
            Create Your Account
          </router-link>
           <router-link v-else to="/slots" class="btn-secondary text-lg px-8 py-3 shadow-lg transform hover:scale-105 transition-transform duration-200">
            Browse Games
          </router-link>
     </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useStore } from 'vuex';
// Assuming FontAwesome is globally available or imported in main.js
// For utility classes like btn-primary, btn-secondary, ensure they are defined globally (e.g. in styles.css or via Tailwind config)

const store = useStore();
const isAuthenticated = computed(() => store.getters.isAuthenticated);

const featuredSlots = ref([]);
const isLoadingGames = ref(false);
const gamesError = ref(null);

const getSlotImageUrl = (slot) => {
  if (slot.thumbnail_url) return slot.thumbnail_url;
  if (slot.short_name) {
    return `/public/${slot.short_name}/background.png`; // Adjust path if Vite serves public differently
  }
  return null; // Or a path to a generic placeholder image
};

onMounted(async () => {
  isLoadingGames.value = true;
  gamesError.value = null;
  try {
    // fetchSlots action returns { status, slots, status_message }
    const response = await store.dispatch('fetchSlots');
    if (response.status && response.slots) {
      // Filter for active slots and take the first 4 for example
      featuredSlots.value = response.slots.filter(slot => slot.is_active).slice(0, 4);
    } else if (!response.status) {
      // Do not display specific API error on homepage, just log it.
      console.warn('Failed to fetch slots for homepage:', response.status_message);
      // gamesError.value = response.status_message || "Could not load featured games.";
    }
  } catch (error) {
    console.error('Error fetching slots for homepage:', error);
    // gamesError.value = "An unexpected error occurred while loading games.";
  } finally {
    isLoadingGames.value = false;
  }
});
</script>

<style scoped>
.hero {
  /* Specific hero styles, e.g., background image if not using gradient classes */
  /* background-image: url('@/assets/hero-background.jpg');
  background-size: cover;
  background-position: center; */
}

.feature-card i { /* If using FontAwesome and want to ensure size/alignment */
  /* font-size: 3rem; */ /* Already handled by text-5xl */
}

.featured-slot-card {
  /* Add any specific styling for featured slot cards if needed */
}

/* Removed scoped .btn-primary and .btn-secondary as they should use global styles from assets/styles.css or Tailwind utility classes */
/* Ensure your global button styles or Tailwind classes provide the desired appearance for:
   - Hero CTA: uses .btn-primary
   - Secondary CTA: uses .btn-secondary
*/
</style>


