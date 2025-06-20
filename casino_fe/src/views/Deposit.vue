<template>
  <div class="container mx-auto mt-10 max-w-lg px-4">
    <h2 class="text-center mb-8">Deposit Funds</h2>

     <div v-if="!currentUser" class="card text-center">
      Please log in to view your deposit address.
    </div>

    <div v-else class="card text-center">
      <p class="text-lg text-text-primary mb-2">Please deposit Bitcoin (BTC) to your unique address below:</p>

      <div class="my-4 p-4 bg-bg-primary rounded-md inline-block">
        <p class="font-mono text-lg md:text-xl break-all text-accent font-semibold">
          {{ currentUser.deposit_wallet_address }}
        </p>
      </div>

       <button @click="copyAddress" class="ml-2 p-2 rounded-md text-text-secondary hover:text-accent hover:bg-highlight focus:outline-none focus:ring-2 focus:ring-highlight transition-colors" title="Copy Address">
           <i :class="copyIcon" class="fas fa-lg"></i>
      </button>

      <!-- Error Message Display -->
      <error-message :error="errorObject" @dismiss="errorObject = null" class="mt-4 text-left" />
      <!-- Success Message Display -->
      <div v-if="successMessage" class="alert-success mt-3 text-sm text-left">
        {{ successMessage }}
      </div>

      <!-- Placeholder for QR Code - Generate dynamically or fetch if available -->
      <div class="mt-6 mb-8 flex justify-center">
        <div v-if="currentUser && currentUser.deposit_wallet_address" class="p-2 bg-white rounded-md inline-block">
          <qrcode-vue :value="currentUser.deposit_wallet_address" :size="192" level="H" />
        </div>
         <div v-else class="w-48 h-48 bg-bg-primary border border-border flex items-center justify-center rounded-md text-text-secondary">
             <i class="fas fa-qrcode text-6xl opacity-50"></i>
             <span class="absolute text-xs mt-20 text-center">Address not available<br/>or loading...</span>
         </div>
      </div>

      <p class="text-sm text-text-secondary mb-6">
        Deposits are typically credited after 1-3 network confirmations.
      </p>

      <div class="mt-8 pt-6 border-t border-border">
        <label for="bonusCode" class="mb-2">Have a Bonus Code?</label>
        <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
          <input
            v-model="bonusCode"
            id="bonusCode"
            type="text"
            class="form-input flex-grow uppercase"
            placeholder="Enter Bonus Code"
          />
          <button
             @click="handleApplyBonusCode"
            :disabled="!bonusCode.trim() || isLoadingBonus"
             class="btn-primary w-full sm:w-auto inline-flex justify-center items-center"
             >
             <svg v-if="isLoadingBonus" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isLoadingBonus ? 'Applying...' : 'Apply Code' }}
          </button>
        </div>
        <!-- Error/Success moved above QR code -->
      </div>

      <p class="text-lg text-text-primary mt-10">
        Your current balance:
        <strong class="text-accent">{{ formatSatsToBtc(balance) }} BTC</strong>
        ({{ balance.toLocaleString() }} Sats)
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useStore } from 'vuex';
import { formatSatsToBtc } from '@utils/currencyFormatter';
import ErrorMessage from '@components/ErrorMessage.vue';
import QrcodeVue from 'qrcode.vue';

const store = useStore();
const currentUser = computed(() => store.getters.currentUser);
const balance = computed(() => currentUser.value?.balance ?? 0); // Use currentUser for balance

const bonusCode = ref('');
const isLoadingBonus = ref(false);
const errorObject = ref(null); // For ErrorMessage component
const successMessage = ref('');
const copyIcon = ref('fa-copy');

const copyAddress = async () => {
    if (!currentUser.value?.deposit_wallet_address) return;
    try {
        await navigator.clipboard.writeText(currentUser.value.deposit_wallet_address);
        copyIcon.value = 'fa-check';
        setTimeout(() => {
             copyIcon.value = 'fa-copy';
        }, 2000);
    } catch (err) {
        console.error('Failed to copy address: ', err);
        errorObject.value = { status_message: "Failed to copy address. Your browser might not support this feature or permissions are denied." };
    }
};

const handleApplyBonusCode = async () => {
  if (!bonusCode.value.trim() || isLoadingBonus.value) return;

  isLoadingBonus.value = true;
  errorObject.value = null;
  successMessage.value = '';

  try {
    const response = await store.dispatch('applyBonusCode', {
      bonus_code: bonusCode.value.trim().toUpperCase(), // Trim and uppercase bonus code
    });

    if (response.status) {
      successMessage.value = response.status_message || 'Bonus code applied successfully!';
      bonusCode.value = ''; // Clear input on success
      // Balance is updated by the Vuex action via mutation if backend confirms it
    } else {
      errorObject.value = response; // Expects { status_message: '...' }
      if (!errorObject.value?.status_message) {
         errorObject.value = { status_message: 'Failed to apply bonus code.' };
      }
    }
  } catch (err) {
    console.error('Bonus code application system error:', err);
    errorObject.value = { status_message: 'An unexpected error occurred while applying the bonus code.' };
  } finally {
    isLoadingBonus.value = false;
  }
};
</script>

<style scoped>
/* Add specific styles if needed */
input::placeholder {
    @apply text-gray-400 dark:text-gray-500;
}
input:focus::placeholder {
    @apply text-gray-300 dark:text-gray-600;
}
input[type="text"] {
    text-transform: uppercase; /* Ensure bonus code is uppercase */
}
</style>


