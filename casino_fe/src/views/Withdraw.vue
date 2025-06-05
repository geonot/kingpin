<template>
  <div class="container mx-auto mt-10 max-w-lg px-4">
    <h2 class="text-center mb-8">Withdraw Funds</h2>

    <div v-if="!user" class="card text-center">
      Please log in to access the withdrawal page.
    </div>

    <div v-else class="card">
      <div class="mb-6 pb-4 border-b border-border">
        <p class="text-lg text-text-primary">Your current balance:</p>
        <p class="text-3xl font-semibold text-accent mt-1">
          {{ formatSatsToBtc(user.balance) }} BTC
          <span class="text-sm text-text-secondary"> ({{ user.balance.toLocaleString() }} Sats)</span>
        </p>
      </div>

      <!-- Success/Error Messages -->
      <!-- Error/Success Message Display -->
      <error-message :error="errorObject" @dismiss="errorObject = null" class="mb-4" />
      <div v-if="successMessage" class="alert-success mb-4">
        {{ successMessage }}
      </div>

      <form @submit.prevent="handleWithdraw" class="space-y-6">
        <div>
          <label for="withdrawAmountBtc" class="mb-1">Amount to Withdraw (BTC)</label>
          <input
            v-model="withdrawAmountBtc"
            @input="updateSatsAmount"
            id="withdrawAmountBtc"
            type="number"
            step="0.00000001"
            min="0.0001"
            class="form-input mt-1"
            placeholder="e.g., 0.005"
            required
          />
          <p v-if="withdrawAmountSats > 0" class="text-xs text-text-secondary mt-1">
            Equivalent to: {{ withdrawAmountSats.toLocaleString() }} Satoshis
          </p>
           <p v-if="formErrors.amount" class="text-xs text-brand-warning mt-1">{{ formErrors.amount }}</p>
        </div>

        <div>
          <label for="withdrawAddress" class="mb-1">Withdrawal Bitcoin Address</label>
          <input
            v-model="withdrawAddress"
            id="withdrawAddress"
            type="text"
            class="form-input mt-1"
            placeholder="Enter your Bitcoin wallet address"
            required
          />
           <p v-if="formErrors.address" class="text-xs text-brand-warning mt-1">{{ formErrors.address }}</p>
        </div>

        <div class="text-center pt-4">
          <button
            type="submit"
            :disabled="isLoading || !isValidForm"
            class="btn-secondary w-full md:w-auto inline-flex justify-center items-center"
          >
            <svg v-if="isLoading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isLoading ? 'Processing...' : 'Request Withdrawal' }}
          </button>
        </div>
      </form>
       <p class="text-xs text-text-secondary mt-6 text-center">
         Note: Withdrawals are processed manually and may take some time. Ensure the address is correct. Network fees may apply. Minimum withdrawal amount is 0.0001 BTC.
       </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useStore } from 'vuex';
import { formatSatsToBtc, formatBtcToSats } from '@utils/currencyFormatter';
import ErrorMessage from '@components/ErrorMessage.vue'; // Import ErrorMessage

const store = useStore();
const currentUser = computed(() => store.getters.currentUser); // Use getter
const balance = computed(() => currentUser.value?.balance ?? 0); // Use getter for balance display

const withdrawAmountBtc = ref('');
const withdrawAmountSats = ref(0);
const withdrawAddress = ref('');
const isLoading = ref(false);
const errorObject = ref(null); // For ErrorMessage component
const successMessage = ref('');
const formErrors = ref({});

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
    return withdrawAmountSats.value > 0 && withdrawAddress.value.length > 0 && Object.keys(formErrors.value).length === 0;
});


const handleWithdraw = async () => {
  errorObject.value = null;
  successMessage.value = '';

  if (!validateForm()) {
      // Optionally set a general error if specific field errors aren't enough
      if (Object.keys(formErrors.value).length > 0) {
          const firstErrorKey = Object.keys(formErrors.value)[0];
           errorObject.value = { status_message: `Please correct the highlighted fields. Error with: ${formErrors.value[firstErrorKey]}` };
       } else {
           errorObject.value = { status_message: "Please ensure all fields are correctly filled." };
       }
      return;
  }

  isLoading.value = true;
  try {
    const response = await store.dispatch('withdraw', {
      amount_sats: withdrawAmountSats.value,
      withdraw_wallet_address: withdrawAddress.value,
    });

    if (response.status) {
      successMessage.value = response.status_message || 'Withdrawal request successful! It will be processed shortly.';
      withdrawAmountBtc.value = '';
      withdrawAmountSats.value = 0;
      withdrawAddress.value = '';
      // Balance is updated by the Vuex action.
    } else {
      errorObject.value = response; // Expects { status_message: '...' }
      if (!errorObject.value?.status_message) {
         errorObject.value = { status_message: 'Withdrawal failed. Please try again.' };
      }
    }
  } catch (err) {
    console.error('Withdrawal system error:', err);
    errorObject.value = { status_message: 'An unexpected error occurred during withdrawal. Please try again later.' };
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


