<template>
  <div id="app" :class="{ 'dark': isDarkMode }" class="min-h-screen bg-bg-primary text-text-primary transition-colors duration-300">
    <!-- Global Loading Overlay -->
    <div v-if="isLoadingGlobal" class="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-[100]"> <!-- Ensure high z-index -->
      <div class="flex flex-col items-center p-6 rounded-lg">
        <!-- Simple Spinner -->
        <svg class="animate-spin h-12 w-12 text-white mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="text-white text-lg font-medium">Loading...</p>
      </div>
    </div>

    <Header @toggle-dark-mode="toggleDarkMode" :is-dark-mode="isDarkMode" class="fixed top-0 left-0 right-0 z-50" /> <!-- Fixed header -->

    <div class="flex pt-16"> <!-- Adjust pt-16 based on actual header height -->
      <LeftNavigation class="z-40 hidden md:flex" /> <!-- Show on md screens and up, hide on small -->

      <div class="flex-1 flex flex-col md:ml-64"> <!-- Add margin for desktop nav, remove for mobile -->
        <!-- Global Error Display -->
        <div v-if="globalError" class="container mx-auto px-4 py-2 mt-2"> <!-- Added mt-2 for spacing from header -->
          <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <strong class="font-bold">Error:</strong>
            <span class="block sm:inline">{{ globalError }}</span>
            <span class="absolute top-0 bottom-0 right-0 px-4 py-3" @click="clearError">
              <svg class="fill-current h-6 w-6 text-red-500" role="button" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><title>Close</title><path d="M14.348 14.849a1.2 1.2 0 0 1-1.697 0L10 11.819l-2.651 3.029a1.2 1.2 0 1 1-1.697-1.697l2.758-3.15-2.759-3.152a1.2 1.2 0 1 1 1.697-1.697L10 8.183l2.651-3.031a1.2 1.2 0 1 1 1.697 1.697l-2.758 3.152 2.758 3.15a1.2 1.2 0 0 1 0 1.698z"/></svg>
            </span>
          </div>
        </div>

        <main class="flex-grow container mx-auto px-4 py-8">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
        <Footer class="mt-auto" /> <!-- Ensure footer is at the bottom of this column -->
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue';
import { useStore } from 'vuex';
import Header from '@components/Header.vue';
import Footer from '@components/Footer.vue';
import LeftNavigation from '@components/LeftNavigation.vue';

export default {
  components: {
    Header,
    Footer,
    LeftNavigation, // Add this
  },
  setup() {
    const store = useStore();
    const isDarkMode = ref(false);

    // Check local storage or system preference for initial dark mode state
    onMounted(() => {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const storedPreference = localStorage.getItem('darkMode');

      if (storedPreference !== null) {
        isDarkMode.value = storedPreference === 'true';
      } else {
        isDarkMode.value = prefersDark;
      }
      // Attempt to load user session if tokens exist
      // store.dispatch('loadSession'); // This call is redundant, already in main.js
    });

    const toggleDarkMode = () => {
      isDarkMode.value = !isDarkMode.value;
      localStorage.setItem('darkMode', isDarkMode.value);
    };

     // Example: Check if user is admin for conditional rendering elsewhere
     const isAdmin = computed(() => store.getters.isAdmin);

    const globalError = computed(() => store.state.globalError);

    const clearError = () => {
      store.commit('clearGlobalError'); // Using commit for mutation
    };

    const isLoadingGlobal = computed(() => store.state.isLoadingGlobal);

    return {
      isDarkMode,
      toggleDarkMode,
      isAdmin,
      globalError, // Expose to template
      clearError,  // Expose to template
      isLoadingGlobal, // Expose to template
    };
  },
};
</script>

<style>
/* Styles specific to App.vue root element can remain if necessary, */
/* but global styles like body, scrollbar, transitions were moved to assets/styles.css */
/* Example: might have some padding/margin adjustments for #app itself if not covered by Tailwind classes */
</style>


