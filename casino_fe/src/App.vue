<template>
  <!-- Apply dark mode class if enabled -->
  <div id="app" :class="{ 'dark': isDarkMode }" class="flex flex-col min-h-screen bg-gray-100 dark:bg-dark-bg text-gray-900 dark:text-dark-text transition-colors duration-300">
    <Header @toggle-dark-mode="toggleDarkMode" :is-dark-mode="isDarkMode" />
    <main class="flex-grow container mx-auto px-4 py-8">
      <!-- Add transitions to router view -->
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <Footer />
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue';
import { useStore } from 'vuex';
import Header from '@components/Header.vue';
import Footer from '@components/Footer.vue';

export default {
  components: {
    Header,
    Footer,
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
      store.dispatch('loadSession');
    });

    const toggleDarkMode = () => {
      isDarkMode.value = !isDarkMode.value;
      localStorage.setItem('darkMode', isDarkMode.value);
    };

     // Example: Check if user is admin for conditional rendering elsewhere
     const isAdmin = computed(() => store.getters.isAdmin);


    return {
      isDarkMode,
      toggleDarkMode,
      isAdmin,
    };
  },
};
</script>

<style>
/* Styles specific to App.vue root element can remain if necessary, */
/* but global styles like body, scrollbar, transitions were moved to assets/styles.css */
/* Example: might have some padding/margin adjustments for #app itself if not covered by Tailwind classes */
</style>


