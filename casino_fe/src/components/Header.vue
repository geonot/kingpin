<template>
  <header class="bg-gradient-to-r from-gray-800 via-gray-900 to-black dark:from-neutral-800 dark:via-black dark:to-black text-white shadow-lg sticky top-0 z-50">
    <nav class="container mx-auto px-4 py-3 flex justify-between items-center">
      <!-- Logo -->
      <router-link :to="isAuthenticated ? '/slots' : '/'" class="flex items-center flex-shrink-0">
        <img src="@/assets/logo.png" alt="Kingpin Casino" class="h-10 md:h-12 mr-2 transition-transform duration-300 hover:scale-110" />
        <span class="font-bold text-lg md:text-xl tracking-tight hidden sm:inline">Kingpin Casino</span>
      </router-link>

      <!-- Navigation Links -->
      <div class="flex items-center space-x-4 md:space-x-6">
        <!-- Unauthenticated Links -->
        <template v-if="!isAuthenticated">
          <router-link to="/login" class="nav-link">Login</router-link>
          <router-link to="/register" class="btn-outline-gold hidden sm:inline-block">Register</router-link>
        </template>

        <!-- Authenticated Links -->
        <template v-if="isAuthenticated">
          <router-link to="/slots" class="nav-link">Slots</router-link>
          <router-link to="/tables" class="nav-link">Tables</router-link>
          <router-link to="/deposit" class="nav-link">Deposit</router-link>
          <!-- Profile Dropdown -->
          <div class="relative" ref="dropdownContainer">
            <button @click="toggleDropdown" class="flex items-center focus:outline-none nav-link">
               <i class="fas fa-user-circle mr-1 md:mr-2 text-xl"></i> <!-- User Icon -->
              <span class="hidden md:inline">{{ user?.username || 'Profile' }}</span>
              <i class="fas fa-chevron-down ml-1 text-xs transition-transform duration-200" :class="{ 'rotate-180': dropdownOpen }"></i>
            </button>
            <!-- Dropdown Menu -->
            <transition name="dropdown-fade">
              <ul
                v-if="dropdownOpen"
                class="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg overflow-hidden z-60"
                >
                <li><router-link to="/settings" class="dropdown-item">
                    <i class="fas fa-cog mr-2 w-4 text-center"></i>Settings
                </router-link></li>
                <li><router-link to="/withdraw" class="dropdown-item">
                     <i class="fas fa-wallet mr-2 w-4 text-center"></i>Withdraw
                </router-link></li>
                 <!-- Add Admin link if user is admin -->
                 <li v-if="isAdmin"><router-link to="/admin" class="dropdown-item">
                     <i class="fas fa-user-shield mr-2 w-4 text-center"></i>Admin Panel
                 </router-link></li>
                <li><hr class="border-gray-200 dark:border-gray-700 my-1"/></li>
                <li><a href="#" @click.prevent="handleLogout" class="dropdown-item text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900">
                     <i class="fas fa-sign-out-alt mr-2 w-4 text-center"></i>Logout
                </a></li>
              </ul>
            </transition>
          </div>
        </template>

         <!-- Dark Mode Toggle Button -->
         <button @click="toggleDarkMode" class="p-2 rounded-full hover:bg-gray-700 dark:hover:bg-gray-600 focus:outline-none" :title="isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'">
             <i :class="isDarkMode ? 'fas fa-sun' : 'fas fa-moon'" class="text-lg text-yellow-400 dark:text-yellow-300"></i>
         </button>
      </div>
    </nav>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, defineProps, defineEmits } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';

const props = defineProps({
    isDarkMode: Boolean
});
const emit = defineEmits(['toggle-dark-mode']);

const store = useStore();
const router = useRouter();
const dropdownOpen = ref(false);
const dropdownContainer = ref(null); // Ref for the dropdown container element

// Computed properties from Vuex store
const user = computed(() => store.state.user);
const isAuthenticated = computed(() => store.getters.isAuthenticated);
const isAdmin = computed(() => store.getters.isAdmin);

const toggleDropdown = () => {
  dropdownOpen.value = !dropdownOpen.value;
};

const closeDropdown = (event) => {
    // Close if clicked outside the dropdown container
    if (dropdownContainer.value && !dropdownContainer.value.contains(event.target)) {
        dropdownOpen.value = false;
    }
};

const handleLogout = async () => {
  dropdownOpen.value = false; // Close dropdown first
  await store.dispatch('logout');
  // Redirect to home page after logout
  router.push('/');
};

const toggleDarkMode = () => {
    emit('toggle-dark-mode');
};

// Add/remove click-outside listener for dropdown
onMounted(() => {
    document.addEventListener('click', closeDropdown);
});
onBeforeUnmount(() => {
     document.removeEventListener('click', closeDropdown);
});

</script>

<style scoped>
.nav-link {
  @apply px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-colors;
}

.router-link-exact-active.nav-link {
    /* Highlight active link */
   @apply bg-gray-900 text-white;
}

.btn-outline-gold {
    @apply px-3 py-1.5 border border-gold text-gold rounded-md text-sm font-medium hover:bg-gold hover:text-gray-900 transition-colors duration-200;
}

.dropdown-item {
    @apply block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center transition-colors;
}

/* Dropdown transition */
.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>

