<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-200px)] py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white dark:bg-gray-800 p-8 md:p-10 rounded-xl shadow-lg">
      <div>
        <img class="mx-auto h-16 w-auto" src="@/assets/logo.png" alt="Kingpin Casino Logo">
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
          Sign in to your account
        </h2>
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <input type="hidden" name="remember" value="true">

        <!-- General API Error Message -->
        <error-message :error="error" @dismiss="error = null" class="mb-4" />

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
              @input="validateUsernameField"
              :class="fieldClasses('username')"
              placeholder="Username">
            <p v-if="formErrors.username" class="text-xs text-red-500 mt-1 px-3">{{ formErrors.username }}</p>
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
              @input="validatePasswordField"
              :class="fieldClasses('password')"
              placeholder="Password">
            <p v-if="formErrors.password" class="text-xs text-red-500 mt-1 px-3">{{ formErrors.password }}</p>
          </div>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <!-- Add remember me if needed -->
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
            class="group relative w-full flex justify-center items-center py-3 px-4 border border-royal-blue text-sm font-medium rounded-md text-white bg-royal-blue hover:bg-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-royal-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors dark:bg-light-purple dark:hover:bg-purple-600 dark:focus:ring-light-purple dark:border-light-purple"
          >
             <svg v-if="isLoading" class="animate-spin mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
               <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
               <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
             </svg>
            <span class="absolute left-0 inset-y-0 flex items-center pl-3" v-if="!isLoading">
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
import { ref, reactive } from 'vue'; // Added reactive
import { useStore } from 'vuex';
import { useRouter, useRoute } from 'vue-router';
import ErrorMessage from '@components/ErrorMessage.vue';

const store = useStore();
const router = useRouter();
const route = useRoute();

const username = ref('');
const password = ref('');
const error = ref(null); // For general API errors
const isLoading = ref(false);
const formErrors = reactive({}); // For field-specific client-side validation errors

const validateUsernameField = () => {
    delete formErrors.username;
    if (!username.value.trim()) {
        formErrors.username = 'Username is required.';
        return false;
    }
    return true;
};

const validatePasswordField = () => {
    delete formErrors.password;
    if (!password.value) { // Password not trimmed as per original logic
        formErrors.password = 'Password is required.';
        return false;
    }
    return true;
};

const validateAllFields = () => {
    const isUsernameValid = validateUsernameField();
    const isPasswordValid = validatePasswordField();
    return isUsernameValid && isPasswordValid;
};

const handleLogin = async () => {
  error.value = null; // Clear previous API errors
  Object.keys(formErrors).forEach(key => delete formErrors[key]); // Clear previous client errors

  if (!validateAllFields()) {
    // Field-specific errors are already set by validateAllFields
    return;
  }

  isLoading.value = true;
  try {
    const response = await store.dispatch('login', {
      username: username.value.trim(), // Trim username for the API call
      password: password.value,
    });

    if (response.status && response.access_token) {
      const redirectPath = route.query.redirect || '/slots';
      router.push(redirectPath);
    } else {
      // Handle API error messages
      if (response && response.status_message) {
        const msgLower = response.status_message.toLowerCase();
        if (msgLower.includes('invalid username or password')) {
            formErrors.username = 'Invalid username or password.';
            formErrors.password = ' '; // To mark password field as error, but message is on username
        } else {
            error.value = { status_message: response.status_message };
        }
      } else {
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

const baseInputClass = "appearance-none rounded-none relative block w-full px-3 py-3 border placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white bg-white dark:bg-gray-700 focus:outline-none focus:ring-royal-blue focus:border-royal-blue focus:z-10 sm:text-sm";
const errorInputClass = "border-red-500 dark:border-red-600";
const normalInputClass = "border-gray-300 dark:border-gray-600";

const fieldClasses = (field) => {
    const classes = [baseInputClass];
    if (formErrors[field]) {
        classes.push(errorInputClass);
    } else {
        classes.push(normalInputClass);
    }
    // Specific rounding for login form (username top, password bottom)
    if (field === 'username') {
        classes.push('rounded-t-md');
    } else if (field === 'password') {
        classes.push('rounded-b-md');
    }
    return classes.join(' ');
};

</script>

<style scoped>
/* Add specific styles if needed */
</style>
