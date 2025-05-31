<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-200px)] py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white dark:bg-dark-card p-8 md:p-10 rounded-xl shadow-lg">
      <div>
         <img class="mx-auto h-16 w-auto" src="@/assets/logo.png" alt="Kingpin Casino Logo">
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
          Create your account
        </h2>
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="handleRegister">

        <!-- General API Error Message -->
        <error-message :error="apiError" @dismiss="apiError = null" class="mb-4" />

        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="username" class="sr-only">Username</label>
            <input
              v-model="form.username"
              id="username"
              name="username"
              type="text"
              autocomplete="username"
              required
              @input="validateField('username')"
              :class="fieldClasses('username')"
              placeholder="Username"
            >
             <p v-if="formErrors.username" class="text-xs text-red-500 mt-1 px-3">{{ formErrors.username }}</p>
          </div>
          <div>
            <label for="email-address" class="sr-only">Email address</label>
            <input
              v-model="form.email"
              id="email-address"
              name="email"
              type="email"
              autocomplete="email"
              required
               @input="validateField('email')"
              :class="fieldClasses('email')"
              placeholder="Email address"
             >
              <p v-if="formErrors.email" class="text-xs text-red-500 mt-1 px-3">{{ formErrors.email }}</p>
          </div>
          <div>
            <label for="password" class="sr-only">Password</label>
            <input
              v-model="form.password"
              id="password"
              name="password"
              type="password"
              autocomplete="new-password"
              required
               @input="validateField('password')"
               :class="fieldClasses('password')"
              placeholder="Password"
            >
             <p v-if="formErrors.password" class="text-xs text-red-500 mt-1 px-3">{{ formErrors.password }}</p>
             <ul v-if="form.password && passwordHints.length > 0" class="text-xs text-gray-500 dark:text-gray-400 mt-1 px-3 list-disc list-inside">
                <li v-for="(hint, index) in passwordHints" :key="index">{{ hint }}</li>
            </ul>
          </div>
          <div>
            <label for="confirm-password" class="sr-only">Confirm Password</label>
            <input
              v-model="form.confirmPassword"
              id="confirm-password"
              name="confirmPassword"
              type="password"
              autocomplete="new-password"
              required
               @input="validateField('confirmPassword')"
              :class="fieldClasses('confirmPassword', true)"
              placeholder="Confirm Password"
            >
              <p v-if="formErrors.confirmPassword" class="text-xs text-red-500 mt-1 px-3">{{ formErrors.confirmPassword }}</p>
          </div>
        </div>

        <div>
          <button
            type="submit"
            :disabled="isLoading || !isFormValid"
            class="group relative w-full flex justify-center items-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-royal-blue hover:bg-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-royal-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
             <svg v-if="isLoading" class="animate-spin mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
               <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
               <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
             </svg>
            {{ isLoading ? 'Registering...' : 'Register' }}
          </button>
        </div>
        <div class="text-sm text-center">
          <span class="text-gray-600 dark:text-gray-400">Already have an account?</span>
          <router-link to="/login" class="font-medium text-royal-blue hover:text-dark-blue dark:text-light-purple dark:hover:text-purple-300 ml-1">
            Sign in here
          </router-link>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import { validate as validateEmail } from 'email-validator';
import ErrorMessage from '@components/ErrorMessage.vue'; // Import ErrorMessage component

const store = useStore();
const router = useRouter();

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
});
const formErrors = reactive({}); // For field-specific client-side validation errors
const apiError = ref(null); // For general errors from the API, expects an object
const isLoading = ref(false);
const passwordHints = ref([]);

// --- Validation Logic ---
const validateUsername = () => {
    delete formErrors.username;
    const username = form.username.trim();
    if (!username) {
        formErrors.username = 'Username is required.';
    } else if (username.length < 3) {
        formErrors.username = 'Username must be at least 3 characters long.';
    } else if (username.length > 50) {
        formErrors.username = 'Username cannot exceed 50 characters.';
    } else if (!/^[a-zA-Z0-9_]+$/.test(username)) {
        formErrors.username = 'Username must contain only letters, numbers, and underscores.';
    }
    return !formErrors.username;
};

const validateUserEmail = () => {
     delete formErrors.email;
     const email = form.email.trim();
     if (!email) {
         formErrors.email = 'Email is required.';
     } else if (!validateEmail(email)) {
         formErrors.email = 'Please enter a valid email address.';
     } else if (email.length > 120) {
         formErrors.email = 'Email cannot exceed 120 characters.';
     }
     return !formErrors.email;
};

const validateUserPassword = () => {
    delete formErrors.password;
    passwordHints.value = [];
    const password = form.password; // No trim for password
    let isValid = true;

    if (!password) {
        formErrors.password = 'Password is required.';
        isValid = false;
    } else {
        if (password.length < 8) { passwordHints.value.push("At least 8 characters"); isValid = false; }
        if (!/[A-Z]/.test(password)) { passwordHints.value.push("An uppercase letter"); isValid = false; }
        if (!/[a-z]/.test(password)) { passwordHints.value.push("A lowercase letter"); isValid = false; }
        if (!/[0-9]/.test(password)) { passwordHints.value.push("A number"); isValid = false; }
        if (!/[!@#$%^&*()_+=\-[\]{};':"\\|,.<>/?~`]/.test(password)) { passwordHints.value.push("A special character"); isValid = false; }

        if (!isValid) {
             formErrors.password = 'Password does not meet requirements:';
        }
    }

     // Re-validate confirm password whenever password changes
     if (form.confirmPassword) {
         validateConfirmPassword();
     }

    return isValid;
};

const validateConfirmPassword = () => {
    delete formErrors.confirmPassword;
    if (form.password && !form.confirmPassword) {
         formErrors.confirmPassword = 'Please confirm your password.';
    } else if (form.password && form.confirmPassword && form.password !== form.confirmPassword) {
        formErrors.confirmPassword = 'Passwords do not match.';
    }
    return !formErrors.confirmPassword;
};

const validateField = (field) => {
  switch (field) {
    case 'username': validateUsername(); break;
    case 'email': validateUserEmail(); break;
    case 'password': validateUserPassword(); break;
    case 'confirmPassword': validateConfirmPassword(); break;
  }
};

const validateAll = () => {
    // Run all validators and return overall validity
    const isUserValid = validateUsername();
    const isEmailValid = validateUserEmail();
    const isPassValid = validateUserPassword();
    const isConfirmValid = validateConfirmPassword();
    return isUserValid && isEmailValid && isPassValid && isConfirmValid;
};

// Computed property to check overall form validity for button disabling
const isFormValid = computed(() => {
    // Check if all fields are potentially valid (basic check, full validation on submit)
    return form.username && form.email && form.password && form.confirmPassword && Object.keys(formErrors).length === 0;
    // Or re-run full validation constantly (less performant but ensures button state is always accurate)
    // return validateAll();
});


// --- Form Submission ---
const handleRegister = async () => {
  apiError.value = null; // Clear previous general API errors
  // Clear field-specific errors that might have been set from a previous API attempt
  Object.keys(formErrors).forEach(key => delete formErrors[key]);

  if (!validateAll()) {
       console.log("Client-side form validation failed", formErrors);
       // Optionally set a general apiError if formErrors isn't enough feedback
       if (Object.keys(formErrors).length > 0) {
           const firstErrorKey = Object.keys(formErrors)[0];
           apiError.value = { status_message: `Please correct the highlighted fields. Error with: ${firstErrorKey}` };
       } else {
           apiError.value = { status_message: "Please ensure all fields are correctly filled." };
       }
       return;
  }

  isLoading.value = true;

  try {
    const response = await store.dispatch('register', {
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
    });

    if (response.status && response.access_token) { // Successful registration includes tokens
      // Login action (which includes fetchUserProfile) is typically called by store's register action on success.
      // Or, if register action only returns tokens, dispatch login/fetchUserProfile here.
      // Assuming store's register action handles setting tokens and fetching user.
      router.push('/slots'); // Or to a welcome/verify email page
    } else {
      // Display backend error message via ErrorMessage component
      apiError.value = response; // Store the whole response object
      if (!apiError.value?.status_message) {
         apiError.value = { status_message: 'Registration failed. Please try again.' };
      }
      // Optionally, try to map backend error to specific fields if backend provides structured errors
      // For example, if response.errors is an object like { username: ['Username taken'] }
      if (response.errors) {
        for (const field in response.errors) {
          if (formErrors.hasOwnProperty(field)) {
            formErrors[field] = response.errors[field].join ? response.errors[field].join(' ') : response.errors[field];
          }
        }
      } else if (apiError.value.status_message) { // If only a general message, check for keywords
          if (apiError.value.status_message.toLowerCase().includes('username')) {
              formErrors.username = apiError.value.status_message;
          } else if (apiError.value.status_message.toLowerCase().includes('email')) {
              formErrors.email = apiError.value.status_message;
          }
      }
    }
  } catch (err) {
    console.error('Registration system error:', err);
    apiError.value = { status_message: 'An unexpected error occurred during registration. Please try again later.' };
  } finally {
    isLoading.value = false;
  }
};

// --- Styling ---
const baseInputClass = "appearance-none rounded-none relative block w-full px-3 py-3 border placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white bg-white dark:bg-gray-700 focus:outline-none focus:ring-royal-blue focus:border-royal-blue focus:z-10 sm:text-sm";
const errorInputClass = "border-red-500 dark:border-red-600";
const normalInputClass = "border-gray-300 dark:border-gray-600";

const fieldClasses = (field, isLast = false) => {
    const classes = [baseInputClass];
    if (formErrors[field]) {
        classes.push(errorInputClass);
    } else {
        classes.push(normalInputClass);
    }
    // Adjust rounding based on position (only applies if using -space-y-px correctly)
    if (field === 'username') classes.push('rounded-t-md');
    if (isLast) classes.push('rounded-b-md');

    return classes.join(' ');
};

</script>

<style scoped>
/* Add specific styles if needed */
</style>

