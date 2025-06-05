<template>
  <div class="container mx-auto mt-10 max-w-lg px-4">
    <h2 class="text-center mb-8">Account Settings</h2>

    <div v-if="!currentUser" class="card text-center">
      Please log in to access your settings.
    </div>

    <div v-else class="space-y-10">
      <!-- Update Email Section -->
      <form @submit.prevent="handleUpdateEmail" class="card space-y-6">
        <h3 class="border-b border-border pb-3">Update Email</h3>

        <error-message :error="emailApiError" @dismiss="emailApiError = null" />
        <div v-if="emailSuccessMessage" class="alert-success mb-4 text-sm">
          {{ emailSuccessMessage }}
        </div>

        <div>
          <label for="username_disabled" class="mb-1">Username</label>
          <input
            id="username_disabled"
            type="text"
            :value="currentUser.username"
            class="form-input mt-1 cursor-not-allowed"
            disabled
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Username cannot be changed.</p>
        </div>

        <div>
          <label for="email" class="mb-1">Email Address</label>
          <input
            v-model="emailForm.email"
            id="email"
            type="email"
            class="form-input mt-1"
            placeholder="your.email@example.com"
            required
          />
          <p v-if="formErrors.email" class="text-xs text-brand-warning mt-1">{{ formErrors.email }}</p>
        </div>
        <div class="text-right">
          <button
            type="submit"
            :disabled="isEmailLoading || !isEmailFormChanged || formErrors.email"
            class="btn-secondary inline-flex justify-center items-center"
          >
            <svg v-if="isEmailLoading" class="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isEmailLoading ? 'Saving...' : 'Update Email' }}
          </button>
        </div>
      </form>

      <!-- Change Password Section -->
      <form @submit.prevent="handleChangePassword" class="card space-y-6">
        <h3 class="border-b border-border pb-3">Change Password</h3>

        <error-message :error="passwordApiError" @dismiss="passwordApiError = null" />
         <div v-if="passwordSuccessMessage" class="alert-success mb-4 text-sm">
          {{ passwordSuccessMessage }}
        </div>

        <div>
          <label for="newPassword" class="mb-1">New Password</label>
          <input
            v-model="passwordForm.password"
            id="newPassword"
            type="password"
            class="form-input mt-1"
            placeholder="Enter new password"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char.</p>
          <p v-if="formErrors.password" class="text-xs text-brand-warning mt-1">{{ formErrors.password }}</p>
        </div>

        <div>
          <label for="confirmPassword" class="mb-1">Confirm New Password</label>
          <input
            v-model="passwordForm.confirmPassword"
            id="confirmPassword"
            type="password"
            class="form-input mt-1"
            placeholder="Confirm new password"
            :required="!!passwordForm.password"
          />
          <p v-if="formErrors.confirmPassword" class="text-xs text-brand-warning mt-1">{{ formErrors.confirmPassword }}</p>
        </div>
        <div class="text-right">
          <button
            type="submit"
            :disabled="isPasswordLoading || !passwordForm.password || formErrors.password || formErrors.confirmPassword"
            class="btn-secondary inline-flex justify-center items-center"
          >
            <svg v-if="isPasswordLoading" class="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isPasswordLoading ? 'Saving...' : 'Change Password' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue';
import { useStore } from 'vuex';
import { validate as validateEmailValidator } from 'email-validator';
import ErrorMessage from '@components/ErrorMessage.vue';

const store = useStore();
const currentUser = computed(() => store.getters.currentUser);

// Form state for email
const emailForm = reactive({
  email: '',
});
const emailApiError = ref(null);
const emailSuccessMessage = ref('');
const isEmailLoading = ref(false);

// Form state for password
const passwordForm = reactive({
  password: '',
  confirmPassword: '',
});
const passwordApiError = ref(null);
const passwordSuccessMessage = ref('');
const isPasswordLoading = ref(false);

const formErrors = reactive({ // Shared for client-side validation messages
  email: '',
  password: '',
  confirmPassword: '',
});

// Initialize form with current user data
onMounted(() => {
  if (currentUser.value) {
    emailForm.email = currentUser.value.email || '';
  }
});

watch(currentUser, (newVal) => {
  if (newVal) {
    emailForm.email = newVal.email || '';
  }
});

const isEmailFormChanged = computed(() => {
  if (!currentUser.value) return false;
  return emailForm.email !== currentUser.value.email;
});

// --- Email Update Logic ---
const validateEmailForm = () => {
  formErrors.email = '';
  if (!emailForm.email || !validateEmailValidator(emailForm.email)) {
    formErrors.email = 'Please enter a valid email address.';
    return false;
  }
  return true;
};

const handleUpdateEmail = async () => {
  emailApiError.value = null;
  emailSuccessMessage.value = '';
  if (!validateEmailForm()) return;

  isEmailLoading.value = true;
  try {
    const response = await store.dispatch('updateSettings', { email: emailForm.email });
    if (response.status) {
      emailSuccessMessage.value = response.status_message || 'Email updated successfully!';
      // User data in store is updated by the action, which will update currentUser computed prop
    } else {
      emailApiError.value = response; // { status_message: '...' }
       if (!emailApiError.value?.status_message) emailApiError.value = { status_message: 'Failed to update email.'};
    }
  } catch (err) {
    console.error('Email update system error:', err);
    emailApiError.value = { status_message: 'An unexpected error occurred.' };
  } finally {
    isEmailLoading.value = false;
  }
};

// --- Password Change Logic ---
const validatePasswordStrength = (password) => {
    if (!password) return ''; // Not an error if empty, just means no change
    const errors = [];
    if (password.length < 8) errors.push("At least 8 characters.");
    if (!/[A-Z]/.test(password)) errors.push("An uppercase letter.");
    if (!/[a-z]/.test(password)) errors.push("A lowercase letter.");
    if (!/[0-9]/.test(password)) errors.push("A number.");
    if (!/[!@#$%^&*()_+=\-[\]{};':"\\|,.<>/?~`]/.test(password)) errors.push("A special character.");
    return errors.length === 0 ? '' : errors.join(' ');
};

const validatePasswordForm = () => {
  formErrors.password = '';
  formErrors.confirmPassword = '';
  let isValid = true;

  if (!passwordForm.password) { // Password is required if attempting to change
    formErrors.password = 'New password cannot be empty if you intend to change it.';
    isValid = false;
    return isValid; // Early exit if no new password is provided
  }

  const passwordStrengthError = validatePasswordStrength(passwordForm.password);
  if (passwordStrengthError) {
    formErrors.password = passwordStrengthError;
    isValid = false;
  }

  if (passwordForm.password !== passwordForm.confirmPassword) {
    formErrors.confirmPassword = 'Passwords do not match.';
    isValid = false;
  }
  return isValid;
};

const handleChangePassword = async () => {
  passwordApiError.value = null;
  passwordSuccessMessage.value = '';

  if (!validatePasswordForm()) return;
  if (!passwordForm.password) { // Should be caught by validatePasswordForm, but double check
      passwordApiError.value = { status_message: "New password cannot be empty." };
      return;
  }

  isPasswordLoading.value = true;
  try {
    const response = await store.dispatch('updateSettings', { password: passwordForm.password });
    if (response.status) {
      passwordSuccessMessage.value = response.status_message || 'Password changed successfully!';
      passwordForm.password = '';
      passwordForm.confirmPassword = '';
      formErrors.password = ''; // Clear local validation error on success
      formErrors.confirmPassword = '';
    } else {
      passwordApiError.value = response;
      if (!passwordApiError.value?.status_message) passwordApiError.value = { status_message: 'Failed to change password.'};
    }
  } catch (err) {
    console.error('Password change system error:', err);
    passwordApiError.value = { status_message: 'An unexpected error occurred.' };
  } finally {
    isPasswordLoading.value = false;
  }
};

</script>

<style scoped>
/* Add specific styles if needed */
/* input:disabled {
  opacity: 0.7;
} */
</style>


