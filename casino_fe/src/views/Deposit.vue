<template>
  <div class="container mx-auto mt-10 max-w-lg px-4">
    <h2 class="text-3xl font-bold text-center mb-8 text-gray-800 dark:text-gray-100">Deposit Funds</h2>

     <div v-if="!user" class="text-center p-6 bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-100 rounded-md shadow">
      Please log in to view your deposit address.
    </div>

    <div v-else class="bg-white dark:bg-dark-card p-6 md:p-8 rounded-lg shadow-lg text-center">
      <p class="text-lg text-gray-700 dark:text-gray-300 mb-2">Please deposit Bitcoin (BTC) to your unique address below:</p>

      <div class="my-4 p-4 bg-gray-100 dark:bg-gray-700 rounded-md inline-block">
        <p class="font-mono text-lg md:text-xl break-all text-royal-blue dark:text-light-purple font-semibold">
          {{ user.deposit_wallet_address }}
        </p>
      </div>

       <button @click="copyAddress" class="ml-2 p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors" title="Copy Address">
           <i :class="copyIcon" class="fas fa-lg"></i>
      </button>

      <!-- Placeholder for QR Code - Generate dynamically or fetch if available -->
      <div class="mt-6 mb-8 flex justify-center">
        <!-- Example using a library like 'qrcode.vue' or generate on backend -->
         <div class="w-48 h-48 bg-gray-200 dark:bg-gray-600 flex items-center justify-center rounded-md text-gray-500 dark:text-gray-400">
             <i class="fas fa-qrcode text-6xl"></i>
             <span class="absolute text-xs mt-20">QR Code Placeholder</span>
             <!-- Replace with actual QR code component -->
             <!-- <qrcode-vue :value="user.deposit_wallet_address" :size="192" level="H" /> -->
         </div>
      </div>

      <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">
        Deposits are typically credited after 1-3 network confirmations.
      </p>

      <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <label for="bonusCode" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Have a Bonus Code?</label>
        <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
          <input
            v-model="bonusCode"
            id="bonusCode"
            type="text"
            class="flex-grow p-3 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-royal-blue focus:border-royal-blue dark:bg-gray-700 dark:text-white uppercase"
            placeholder="Enter Bonus Code"
          />
          <button
             @click="applyBonusCode"
            :disabled="!bonusCode || isLoadingBonus"
             class="w-full sm:w-auto inline-flex justify-center items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-gold hover:bg-dark-gold focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
             >
             <svg v-if="isLoadingBonus" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isLoadingBonus ? 'Applying...' : 'Apply Code' }}
          </button>
        </div>
         <p v-if="bonusMessage" :class="['mt-3 text-sm', isBonusError ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400']">
            {{ bonusMessage }}
         </p>
      </div>

      <p class="text-lg text-gray-700 dark:text-gray-300 mt-10">
        Your current balance:
        <strong class="text-royal-blue dark:text-light-purple">{{ formatSatsToBtc(user.balance) }} BTC</strong>
        ({{ user.balance.toLocaleString() }} Sats)
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useStore } from 'vuex';
import { formatSatsToBtc } from '@utils/currencyFormatter'; // Currency utility
// If using qrcode.vue: import QrcodeVue from 'qrcode.vue';

const store = useStore();
const user = computed(() => store.state.user);

const bonusCode = ref('');
const isLoadingBonus = ref(false);
const bonusMessage = ref('');
const isBonusError = ref(false);
const copyIcon = ref('fa-copy'); // FontAwesome copy icon

const copyAddress = async () => {
    if (!user.value?.deposit_wallet_address) return;
    try {
        await navigator.clipboard.writeText(user.value.deposit_wallet_address);
        copyIcon.value = 'fa-check'; // Change icon to checkmark
        setTimeout(() => {
             copyIcon.value = 'fa-copy'; // Revert icon after 2 seconds
        }, 2000);
    } catch (err) {
        console.error('Failed to copy address: ', err);
        // Optionally show an error message to the user
    }
};

const applyBonusCode = async () => {
  if (!bonusCode.value || isLoadingBonus.value) return;

  isLoadingBonus.value = true;
  bonusMessage.value = '';
  isBonusError.value = false;

  try {
    const response = await store.dispatch('applyBonusCode', {
      bonus_code: bonusCode.value,
    });

    if (response.status) {
      bonusMessage.value = response.status_message || 'Bonus code applied successfully!';
      isBonusError.value = false;
      bonusCode.value = ''; // Clear input on success
      // Balance update is handled by the store mutation
    } else {
      bonusMessage.value = response.status_message || 'Failed to apply bonus code.';
      isBonusError.value = true;
    }
  } catch (error) {
    console.error('Bonus code application error:', error);
    bonusMessage.value = 'An unexpected error occurred while applying the bonus code.';
    isBonusError.value = true;
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


