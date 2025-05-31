<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-200px)] py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white dark:bg-dark-card p-8 md:p-10 rounded-xl shadow-lg">
      <div>
        <img class="mx-auto h-16 w-auto" src="@/assets/logo.png" alt="Kingpin Casino Logo">
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
          Sign in to your account
        </h2>
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <input type="hidden" name="remember" value="true">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="username" class="sr-only">Username</label>
            <input
              v-model="username"
              id="username"
              name="username"
              type="text"
              autocomplete="username"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-3 border border-gray-300 dark:border-gray-600 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white bg-white dark:bg-gray-700 rounded-t-md focus:outline-none focus:ring-royal-blue focus:border-royal-blue focus:z-10 sm:text-sm"
              placeholder="Username">
          </div>
          <div>
            <label for="password" class="sr-only">Password</label>
            <input
              v-model="password"
              id="password"
              name="password"
              type="password"
              autocomplete="current-password"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-3 border border-gray-300 dark:border-gray-600 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white bg-white dark:bg-gray-700 rounded-b-md focus:outline-none focus:ring-royal-blue focus:border-royal-blue focus:z-10 sm:text-sm"
              placeholder="Password">
          </div>
        </div>

        <!-- Error Message -->
         <!-- Error Message Component -->
         <error-message :error="error" @dismiss="error = null" class="mb-4" />

        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <!-- Add remember me if needed -->
            <!-- <input id="remember-me" name="remember-me" type="checkbox" class="h-4 w-4 text-royal-blue focus:ring-royal-blue border-gray-300 rounded">
            <label for="remember-me" class="ml-2 block text-sm text-gray-900 dark:text-gray-300"> Remember me </label> -->
          </div>

          <div class="text-sm">
            <a href="#" class="font-medium text-royal-blue hover:text-dark-blue dark:text-light-purple dark:hover:text-purple-300">
              Forgot your password?
            </a>
          </div>
        </div>

        <div>
          <button
            type="submit"
            :disabled="isLoading"
            class="group relative w-full flex justify-center items-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-royal-blue hover:bg-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-royal-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
             <svg v-if="isLoading" class="animate-spin mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
               <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
               <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
             </svg>
            <span class="absolute left-0 inset-y-0 flex items-center pl-3" v-if="!isLoading">
              <!-- Heroicon name: solid/lock-closed -->
              <svg class="h-5 w-5 text-indigo-300 group-hover:text-indigo-200" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd" />
              </svg>
            </span>
            {{ isLoading ? 'Signing in...' : 'Sign in' }}
          </button>
        </div>
         <div class="text-sm text-center">
            <span class="text-gray-600 dark:text-gray-400">Don't have an account?</span>
            <router-link to="/register" class="font-medium text-royal-blue hover:text-dark-blue dark:text-light-purple dark:hover:text-purple-300 ml-1">
              Register here
            </router-link>
          </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useStore } from 'vuex';
import { useRouter, useRoute } from 'vue-router'; // Import useRoute
import ErrorMessage from '@components/ErrorMessage.vue'; // Import ErrorMessage component

const store = useStore();
const router = useRouter();
const route = useRoute(); // Get current route instance

const username = ref('');
const password = ref('');
const error = ref(null); // Will hold error object { status_message: '...' } or null
const isLoading = ref(false);

const handleLogin = async () => {
  error.value = null; // Clear previous errors
  isLoading.value = true;

  try {
    const response = await store.dispatch('login', {
      username: username.value,
      password: password.value,
    });

    if (response.status && response.access_token) { // Check for status true and presence of token
      const redirectPath = route.query.redirect || '/slots'; // Get redirect path or default
      router.push(redirectPath);
    } else {
      error.value = response; // Store the whole error response object
      if (!error.value?.status_message) { // Fallback message
        error.value = { status_message: 'Login failed. Please check your credentials.'};
      }
    }
  } catch (err) {
    console.error('Login system error:', err);
    error.value = { status_message: 'An unexpected error occurred. Please try again later.' };
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Add specific styles if needed */
</style>


