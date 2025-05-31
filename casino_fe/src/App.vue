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
/* Global styles and transitions */
body {
  margin: 0;
  font-family: 'Poppins', sans-serif; /* Use Poppins as primary */
}

/* Router transition styles */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Improved Scrollbar (Optional) */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: #555;
}
.dark ::-webkit-scrollbar-track {
  background: #2d2d44; /* Darker track for dark mode */
}
.dark ::-webkit-scrollbar-thumb {
  background: #555; /* Slightly lighter thumb */
}
.dark ::-webkit-scrollbar-thumb:hover {
  background: #777;
}
</style>


