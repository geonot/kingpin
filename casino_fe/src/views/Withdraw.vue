<template>
  <div class="container mx-auto mt-10 max-w-lg px-4">
    <h2 class="text-3xl font-bold text-center mb-8 text-gray-800 dark:text-gray-100">Withdraw Funds</h2>

    <div v-if="!user" class="text-center p-6 bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-100 rounded-md shadow">
      Please log in to access the withdrawal page.
    </div>

    <div v-else class="bg-white dark:bg-dark-card p-6 md:p-8 rounded-lg shadow-lg">
      <div class="mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
        <p class="text-lg text-gray-700 dark:text-gray-300">Your current balance:</p>
        <p class="text-3xl font-semibold text-royal-blue dark:text-light-purple mt-1">
          {{ formatSatsToBtc(user.balance) }} BTC
          <span class="text-sm text-gray-500 dark:text-gray-400"> ({{ user.balance.toLocaleString() }} Sats)</span>
        </p>
      </div>

      <!-- Success/Error Messages -->
      <div v-if="successMessage" class="mb-4 p-4 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 border border-green-300 dark:border-green-600 rounded-md">
        {{ successMessage }}
      </div>
      <div v-if="errorMessage" class="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 border border-red-300 dark:border-red-600 rounded-md">
        {{ errorMessage }}
      </div>

      <form @submit.prevent="submitWithdrawal" class="space-y-6">
        <div>
          <label for="withdrawAmountBtc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Amount to Withdraw (BTC)</label>
          <input
            v-model="withdrawAmountBtc"
            @input="updateSatsAmount"
            id="withdrawAmountBtc"
            type="number"
            step="0.00000001"
            min="0.0001"
            class="mt-1 block w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white"
            placeholder="e.g., 0.005"
            required
          />
          <p v-if="withdrawAmountSats > 0" class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Equivalent to: {{ withdrawAmountSats.toLocaleString() }} Satoshis
          </p>
           <p v-if="formErrors.amount" class="text-xs text-red-500 mt-1">{{ formErrors.amount }}</p>
        </div>

        <div>
          <label for="withdrawAddress" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Withdrawal Bitcoin Address</label>
          <input
            v-model="withdrawAddress"
            id="withdrawAddress"
            type="text"
            class="mt-1 block w-full p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white"
            placeholder="Enter your Bitcoin wallet address"
            required
          />
           <p v-if="formErrors.address" class="text-xs text-red-500 mt-1">{{ formErrors.address }}</p>
        </div>

        <div class="text-center pt-4">
          <button
            type="submit"
            :disabled="isLoading || !isValidForm"
            class="w-full md:w-auto inline-flex justify-center items-center px-8 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-royal-blue hover:bg-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-royal-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg v-if="isLoading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isLoading ? 'Processing...' : 'Request Withdrawal' }}
          </button>
        </div>
      </form>
       <p class="text-xs text-gray-500 dark:text-gray-400 mt-6 text-center">
         Note: Withdrawals are processed manually and may take some time. Ensure the address is correct. Network fees may apply. Minimum withdrawal amount is 0.0001 BTC.
       </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useStore } from 'vuex';
import { formatSatsToBtc, formatBtcToSats } from '@utils/currencyFormatter'; // Assuming utility function exists

const store = useStore();
const user = computed(() => store.state.user);

const withdrawAmountBtc = ref('');
const withdrawAmountSats = ref(0);
const withdrawAddress = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const formErrors = ref({}); // For field-specific errors

const updateSatsAmount = () => {
  formErrors.value.amount = ''; // Clear error on input
  const amount = parseFloat(withdrawAmountBtc.value);
  if (!isNaN(amount) && amount > 0) {
    withdrawAmountSats.value = formatBtcToSats(amount);
  } else {
    withdrawAmountSats.value = 0;
  }
};

const isValidBitcoinAddress = (address) => {
    // Basic validation (length, starts with 1, 3, or bc1) - refine as needed
    return /^(1|3|bc1)[a-zA-Z0-9]{25,61}$/.test(address);
}

const validateForm = () => {
    formErrors.value = {};
    let isValid = true;

    const minWithdrawalSats = formatBtcToSats(0.0001); // Minimum 0.0001 BTC

    if (withdrawAmountSats.value <= 0) {
        formErrors.value.amount = 'Please enter a valid withdrawal amount.';
        isValid = false;
    } else if (withdrawAmountSats.value < minWithdrawalSats) {
         formErrors.value.amount = `Minimum withdrawal amount is 0.0001 BTC (${minWithdrawalSats.toLocaleString()} Sats).`;
         isValid = false;
    } else if (user.value && withdrawAmountSats.value > user.value.balance) {
        formErrors.value.amount = 'Withdrawal amount cannot exceed your balance.';
         isValid = false;
    }

    if (!withdrawAddress.value) {
         formErrors.value.address = 'Please enter a Bitcoin withdrawal address.';
         isValid = false;
    } else if (!isValidBitcoinAddress(withdrawAddress.value)) {
         formErrors.value.address = 'Invalid Bitcoin address format.';
         isValid = false;
    }

    return isValid;
}

const isValidForm = computed(() => {
    // Check if fields are filled (basic check for button disabling)
    return withdrawAmountSats.value > 0 && withdrawAddress.value.length > 0;
});


const submitWithdrawal = async () => {
  errorMessage.value = '';
  successMessage.value = '';

  if (!validateForm()) {
      return; // Stop if validation fails
  }

  isLoading.value = true;
  try {
    const response = await store.dispatch('withdraw', {
      amount_sats: withdrawAmountSats.value, // Send amount in Satoshis
      withdraw_wallet_address: withdrawAddress.value,
    });

    if (response.status) {
      successMessage.value = response.status_message || 'Withdrawal request successful!';
      // Optionally clear form
      withdrawAmountBtc.value = '';
      withdrawAmountSats.value = 0;
      withdrawAddress.value = '';
      // Balance is updated via Vuex mutation triggered by the action
    } else {
      errorMessage.value = response.status_message || 'Withdrawal failed. Please try again.';
    }
  } catch (error) {
    console.error('Withdrawal error:', error);
    errorMessage.value = 'An unexpected error occurred. Please try again later.';
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Add specific styles if needed */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type="number"] {
  -moz-appearance: textfield; /* Firefox */
}
</style>


