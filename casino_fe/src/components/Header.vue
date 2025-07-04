<template>
  <header class="bg-bg-secondary text-text-primary shadow-lg sticky top-0 z-[70]">
    <nav class="px-2 py-3 flex justify-between items-center">
      <!-- Logo -->
      <router-link :to="isAuthenticated ? '/slots' : '/'" class="flex items-center flex-shrink-0">
        <img src="@/assets/logo.png" alt="Kingpin Casino" class="h-10 md:h-12 mr-2 transition-transform duration-300 hover:scale-110" />
        <span class="font-bold text-lg md:text-xl tracking-tight hidden sm:inline">Kingpin Casino</span>
      </router-link>

      <!-- Desktop Navigation Links -->
      <div class="hidden md:flex items-center space-x-4">
        <template v-if="isAuthenticated">
          <router-link to="/slots" class="nav-link">Slots</router-link>
          <router-link to="/tables" class="nav-link">Tables</router-link>
          <router-link to="/spacecrash" class="nav-link">Spacecrash</router-link>
          <router-link to="/plinko" class="nav-link">Plinko</router-link>
          <router-link to="/deposit" class="nav-link">Deposit</router-link>
          <div v-if="user && user.balance !== undefined" class="nav-link text-highlight">
             <i class="fas fa-coins mr-1"></i> {{ formatSatsToBtc(user.balance, true) }}
          </div>
        </template>
      </div>

      <!-- Right side items: Auth, Profile, Dark Mode Toggle, Mobile Menu Button -->
      <div class="flex items-center space-x-3">
        <!-- Login/Register (Not Authenticated) -->
        <template v-if="!isAuthenticated">
          <router-link to="/login" class="nav-link hidden md:inline-block">Login</router-link>
          <router-link to="/register" class="btn-outline-gold hidden md:inline-block">Register</router-link>
        </template>

        <!-- Profile Dropdown (Authenticated) -->
        <div v-if="isAuthenticated && user" class="relative hidden md:block" ref="dropdownContainer">
          <button @click="toggleDropdown" class="flex items-center focus:outline-none nav-link">
            <i class="fas fa-user-circle mr-1 md:mr-2 text-xl"></i>
            <span>{{ user.username }}</span>
            <i class="fas fa-chevron-down ml-1 text-xs transition-transform duration-200" :class="{ 'rotate-180': dropdownOpen }"></i>
          </button>
          <transition name="dropdown-fade">
            <ul
              v-if="dropdownOpen"
              class="absolute right-0 mt-2 w-48 bg-bg-secondary rounded-md shadow-lg overflow-hidden z-60"
            >
              <li><router-link to="/settings" @click="closeDropdownOnNav" class="dropdown-item"><i class="fas fa-cog mr-2 w-4 text-center"></i>Settings</router-link></li>
              <li><router-link to="/withdraw" @click="closeDropdownOnNav" class="dropdown-item"><i class="fas fa-wallet mr-2 w-4 text-center"></i>Withdraw</router-link></li>
              <li v-if="isAdmin"><router-link to="/admin" @click="closeDropdownOnNav" class="dropdown-item"><i class="fas fa-user-shield mr-2 w-4 text-center"></i>Admin</router-link></li>
              <li><hr class="dropdown-separator my-1"/></li>
              <li><a href="#" @click.prevent="handleLogout" class="dropdown-item-logout"><i class="fas fa-sign-out-alt mr-2 w-4 text-center"></i>Logout</a></li>
            </ul>
          </transition>
        </div>

        <!-- Dark Mode Toggle Button -->
        <button @click="toggleDarkMode" class="p-2 rounded-full hover:bg-black/10 dark:hover:bg-white/10 focus:outline-none" :title="isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'">
          <i :class="isDarkMode ? 'fas fa-sun' : 'fas fa-moon'" class="text-lg text-yellow-400 dark:text-yellow-300"></i>
        </button>

        <!-- Mobile Menu Button (Hamburger) -->
        <button @click="toggleMobileMenu" class="md:hidden p-2 rounded-md hover:bg-black/10 dark:hover:bg-white/10 focus:outline-none" aria-label="Open menu">
          <i :class="mobileMenuOpen ? 'fas fa-times' : 'fas fa-bars'" class="text-lg"></i>
        </button>
      </div>
    </nav>

    <!-- Mobile Menu -->
    <transition name="slide-fade">
      <div v-if="mobileMenuOpen" class="md:hidden absolute top-full left-0 right-0 bg-bg-secondary shadow-lg z-40 pb-4">
        <nav class="flex flex-col space-y-2 px-4 pt-2">
          <template v-if="isAuthenticated">
            <router-link to="/slots" @click="closeMobileMenu" class="mobile-nav-link">Slots</router-link>
            <router-link to="/tables" @click="closeMobileMenu" class="mobile-nav-link">Tables</router-link>
            <router-link to="/spacecrash" @click="closeMobileMenu" class="mobile-nav-link">Spacecrash</router-link>
            <router-link to="/plinko" @click="closeMobileMenu" class="mobile-nav-link">Plinko</router-link> <!-- Added Plinko Link -->
            <router-link to="/deposit" @click="closeMobileMenu" class="mobile-nav-link">Deposit</router-link>
            <div v-if="user && user.balance !== undefined" class="mobile-nav-link text-highlight">
                <i class="fas fa-coins mr-1"></i> {{ formatSatsToBtc(user.balance, true) }}
            </div>
            <hr class="border-border my-2"/> <!-- Use border-border -->
            <router-link to="/settings" @click="closeMobileMenu" class="mobile-nav-link"><i class="fas fa-cog mr-2"></i>Settings</router-link>
            <router-link to="/withdraw" @click="closeMobileMenu" class="mobile-nav-link"><i class="fas fa-wallet mr-2"></i>Withdraw</router-link>
            <router-link v-if="isAdmin" to="/admin" @click="closeMobileMenu" class="mobile-nav-link"><i class="fas fa-user-shield mr-2"></i>Admin</router-link>
            <a href="#" @click.prevent="handleLogoutMobile" class="mobile-nav-link text-red-400"><i class="fas fa-sign-out-alt mr-2"></i>Logout</a>
          </template>
          <template v-else>
            <router-link to="/login" @click="closeMobileMenu" class="mobile-nav-link">Login</router-link>
            <router-link to="/register" @click="closeMobileMenu" class="mobile-nav-link btn-outline-gold mt-2 inline-block text-center">Register</router-link>
          </template>
        </nav>
      </div>
    </transition>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, defineProps, defineEmits } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import { formatSatsToBtc } from '@/utils/currencyFormatter.js'; // Import the formatter

const props = defineProps({
    isDarkMode: Boolean
});
const emit = defineEmits(['toggle-dark-mode']);

const store = useStore();
const router = useRouter();

const dropdownOpen = ref(false);
const dropdownContainer = ref(null);
const mobileMenuOpen = ref(false);

// Computed properties from Vuex store
const user = computed(() => store.state.user);
const isAuthenticated = computed(() => store.getters.isAuthenticated);
const isAdmin = computed(() => store.getters.isAdmin);

const toggleDropdown = () => {
  dropdownOpen.value = !dropdownOpen.value;
  if (dropdownOpen.value) mobileMenuOpen.value = false; // Close mobile if profile opens
};

const closeDropdownOnNav = () => {
    dropdownOpen.value = false;
};

const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value;
  if (mobileMenuOpen.value) dropdownOpen.value = false; // Close profile if mobile opens
};

const closeMobileMenu = () => {
    mobileMenuOpen.value = false;
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

const handleClickOutside = (event) => {
    if (dropdownContainer.value && !dropdownContainer.value.contains(event.target)) {
        dropdownOpen.value = false;
    }
    // Mobile menu closing is handled by its own button or navigation.
};

const handleLogoutMobile = async () => {
  closeMobileMenu();
  await store.dispatch('logout');
  router.push('/');
};

onMounted(() => {
    document.addEventListener('click', handleClickOutside);
});
onBeforeUnmount(() => {
    document.removeEventListener('click', handleClickOutside);
});

</script>

<style scoped>
.nav-link { /* For desktop header links */
  @apply px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150;
  color: var(--color-text-secondary); /* Subtler than primary for nav links */
}
.nav-link:hover {
  color: var(--color-accent);
  background-color: var(--color-highlight);
}
/* Active state for desktop nav-link */
.router-link-exact-active.nav-link {
  color: var(--color-accent);
  background-color: var(--color-highlight);
  font-weight: 600; /* Or @apply font-semibold */
}

.mobile-nav-link {
  @apply block px-3 py-2 rounded-md text-base font-medium transition-colors duration-150;
  color: var(--color-text-primary);
}
.mobile-nav-link:hover {
  color: var(--color-accent);
  background-color: var(--color-highlight);
}
/* Active state for mobile-nav-link */
.router-link-exact-active.mobile-nav-link {
  color: var(--color-accent);
  background-color: var(--color-highlight);
  font-weight: 600; /* Or @apply font-semibold */
}

.text-gold { /* Custom utility if needed, or use Tailwind's text-yellow-500 etc. */
  color: #FFD700; /* This class is still used in the template for balance, but will be overridden by text-highlight. Or remove this if text-highlight is used directly. */
}

.btn-outline-gold {
    @apply px-3 py-1.5 border border-brand-gold text-brand-gold rounded-md text-sm font-medium hover:bg-brand-gold hover:text-gray-900 dark:hover:text-black transition-colors duration-200;
}

.dropdown-item {
    @apply block px-4 py-2 text-sm flex items-center transition-colors duration-150;
    color: var(--color-text-primary); /* Uses CSS var for text */
}
.dropdown-item:hover {
    background-color: var(--color-highlight);
    color: var(--color-accent);
}

/* Logout link specific styling */
.dropdown-item-logout {
    @apply block px-4 py-2 text-sm flex items-center transition-colors duration-150;
    color: var(--brand-warning); /* Default text color for logout */
}
.dropdown-item-logout:hover {
    background-color: var(--brand-warning);
    color: white; /* Ensure contrast on warning background */
}

.dropdown-separator {
    border-color: var(--color-border);
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

/* Mobile Menu Transition */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1);
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-20px);
  opacity: 0;
}
</style>

