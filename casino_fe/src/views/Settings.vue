<template>
  <div class="container mx-auto mt-10 max-w-lg px-4">
    <h2 class="text-3xl font-bold text-center mb-8 text-gray-800 dark:text-gray-100">Account Settings</h2>

     <div v-if="!user" class="text-center p-6 bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-100 rounded-md shadow">
      Please log in to access your settings.
    </div>

    <form v-else @submit.prevent="submitUpdate" class="bg-white dark:bg-dark-card p-6 md:p-8 rounded-lg shadow-lg space-y-6">
       <!-- Success/Error Messages -->
      <div v-if="successMessage" class="mb-4 p-4 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 border border-green-300 dark:border-green-600 rounded-md">
        {{ successMessage }}
      </div>
      <div v-if="errorMessage" class="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 border border-red-300 dark:border-red-600 rounded-md">
        {{ errorMessage }}
      </div>

      <div>
        <label for="username" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
        <input
          id="username"
          type="text"
          :value="user.username"
          class="mt-1 block w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm bg-gray-100 dark:bg-gray-700 dark:text-gray-400 cursor-not-allowed"
          disabled
        />
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Username cannot be changed.</p>
      </div>

      <div>
        <label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email Address</label>
        <input
          v-model="form.email"
          id="email"
          type="email"
          class="mt-1 block w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white"
          placeholder="your.email@example.com"
          required
        />
         <p v-if="formErrors.email" class="text-xs text-red-500 mt-1">{{ formErrors.email }}</p>
      </div>

      <div>
        <label for="newPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">New Password (Optional)</label>
        <input
          v-model="form.password"
          id="newPassword"
          type="password"
          class="mt-1 block w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white"
          placeholder="Leave blank to keep current password"
        />
         <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char.</p>
         <p v-if="formErrors.password" class="text-xs text-red-500 mt-1">{{ formErrors.password }}</p>
      </div>

       <div>
        <label for="confirmPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Confirm New Password</label>
        <input
          v-model="form.confirmPassword"
          id="confirmPassword"
          type="password"
          class="mt-1 block w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white"
          placeholder="Confirm new password if changing"
          :required="!!form.password"
        />
         <p v-if="formErrors.confirmPassword" class="text-xs text-red-500 mt-1">{{ formErrors.confirmPassword }}</p>
      </div>


      <div class="text-center pt-4">
         <button
            type="submit"
            :disabled="isLoading || !isFormChanged || !isValidForm"
            class="w-full md:w-auto inline-flex justify-center items-center px-8 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-royal-blue hover:bg-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-royal-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg v-if="isLoading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isLoading ? 'Saving...' : 'Save Changes' }}
          </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { useStore } from 'vuex';
import { validate as validateEmail } from 'email-validator'; // Use a library for email validation

const store = useStore();
const user = computed(() => store.state.user);

const form = reactive({
  email: user.value?.email || '',
  password: '',
  confirmPassword: '',
});

const formErrors = ref({});
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

// Track if form has changed from initial state
const isFormChanged = computed(() => {
    if (!user.value) return false;
    return form.email !== user.value.email || form.password !== '';
});

// Watch user state to update form if user logs in/out while on page
watch(user, (newUser) => {
    if (newUser) {
        form.email = newUser.email;
        form.password = '';
        form.confirmPassword = '';
        formErrors.value = {}; // Clear errors on user change
    }
});

const validatePasswordStrength = (password) => {
    if (!password) return true; // Optional field if empty
    const errors = [];
    if (password.length < 8) errors.push("Password must be at least 8 characters.");
    if (!/[A-Z]/.test(password)) errors.push("Must contain an uppercase letter.");
    if (!/[a-z]/.test(password)) errors.push("Must contain a lowercase letter.");
    if (!/[0-9]/.test(password)) errors.push("Must contain a number.");
    if (!/[!@#$%^&*()_+=\-[\]{};':"\\|,.<>/?~`]/.test(password)) errors.push("Must contain a special character.");
    return errors.length === 0 ? true : errors.join(' ');
};


const validateForm = () => {
    formErrors.value = {};
    let isValid = true;

    if (!form.email || !validateEmail(form.email)) {
        formErrors.value.email = 'Please enter a valid email address.';
        isValid = false;
    }

    const passwordValidation = validatePasswordStrength(form.password);
    if (passwordValidation !== true) {
        formErrors.value.password = passwordValidation;
        isValid = false;
    }

    if (form.password && form.password !== form.confirmPassword) {
         formErrors.value.confirmPassword = 'Passwords do not match.';
         isValid = false;
    } else if (!form.password && form.confirmPassword) {
        // Clear confirm password if password is removed
        form.confirmPassword = '';
    } else if (form.password && !form.confirmPassword) {
         formErrors.value.confirmPassword = 'Please confirm your new password.';
         isValid = false;
    }


    return isValid;
}

// Computed property to check overall form validity for button state
const isValidForm = computed(() => {
    // This re-runs validation on any form change, can be optimized
    // but fine for simple forms.
    const currentErrors = {};
    let valid = true;
     if (!form.email || !validateEmail(form.email)) {
        currentErrors.email = 'Invalid email.'; valid = false;
    }
     const passValidation = validatePasswordStrength(form.password);
     if (passValidation !== true) {
        currentErrors.password = 'Invalid password.'; valid = false;
     }
     if (form.password && form.password !== form.confirmPassword) {
        currentErrors.confirmPassword = 'Passwords mismatch.'; valid = false;
     } else if (form.password && !form.confirmPassword) {
         currentErrors.confirmPassword = 'Confirmation needed.'; valid = false;
     }
     // Only set formErrors if validation is actively triggered by submit,
     // but use the logic here to determine validity for the button state.
     return valid;
});


const submitUpdate = async () => {
  errorMessage.value = '';
  successMessage.value = '';

  if (!validateForm()) {
      return; // Stop if validation fails
  }

  isLoading.value = true;

  // Prepare payload, only include changed fields
  const payload = {};
  if (form.email !== user.value.email) {
      payload.email = form.email;
  }
  if (form.password) {
      payload.password = form.password;
      // No need to send confirmPassword to backend
  }

  if (Object.keys(payload).length === 0) {
      successMessage.value = "No changes detected.";
      isLoading.value = false;
      return;
  }


  try {
    const response = await store.dispatch('updateSettings', payload);

    if (response.status) {
      successMessage.value = 'Settings updated successfully!';
      // Clear password fields after successful update
      form.password = '';
      form.confirmPassword = '';
      formErrors.value = {}; // Clear errors
      // User data in store is updated by the action
    } else {
      errorMessage.value = response.status_message || 'Failed to update settings.';
    }
  } catch (error) {
    console.error('Settings update error:', error);
    errorMessage.value = 'An unexpected error occurred. Please try again later.';
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Add specific styles if needed */
input:disabled {
  opacity: 0.7;
}
</style>


