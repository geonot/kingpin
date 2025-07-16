<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <header class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary">My Sports Bets</h1>
      <p class="text-text-secondary mt-1">Your history of placed sports bets.</p>
    </header>

    <div v-if="loading" class="text-center text-text-secondary">
      <p>Loading your bets...</p>
    </div>
    <div v-else-if="error" class="text-center text-red-500">
      <p>Error loading bets: {{ error }}</p>
    </div>
    <div v-else-if="bets.length === 0" class="text-center text-text-secondary">
      <p>You haven't placed any sports bets yet.</p>
    </div>
    <div v-else class="space-y-4">
      <div v-for="bet in bets" :key="bet.id" class="bg-bg-secondary p-4 rounded-lg">
        <div class="flex justify-between items-start">
          <div>
            <p class="font-semibold text-lg text-accent">{{ bet.details.selection_name }}</p>
            <p class="text-sm text-text-secondary">{{ bet.details.event }}</p>
            <p class="text-xs text-gray-400">{{ bet.details.market_type }}</p>
          </div>
          <div class="text-right">
            <p :class="['font-bold text-xl', getStatusClass(bet.status)]">{{ bet.status }}</p>
            <p class="text-sm text-text-secondary">{{ formatDateTime(bet.placed_at) }}</p>
          </div>
        </div>
        <div class="mt-4 border-t border-gray-700 pt-4 flex justify-between items-center">
            <div>
                <p class="text-sm text-text-secondary">Stake</p>
                <p class="font-semibold text-text-primary">{{ bet.stake_satoshis.toLocaleString() }} sats</p>
            </div>
            <div>
                <p class="text-sm text-text-secondary">Odds</p>
                <p class="font-semibold text-text-primary">@{{ bet.details.decimal_odds }}</p>
            </div>
            <div class="text-right">
                <p class="text-sm text-text-secondary">{{ bet.status === 'Pending' ? 'Potential Payout' : 'Actual Payout' }}</p>
                <p class="font-semibold text-green-400">
                    {{ (bet.status === 'Won' ? bet.actual_winnings_satoshis : bet.potential_payout_satoshis).toLocaleString() }} sats
                </p>
            </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import api from '@/services/api';

export default {
  name: 'MySportsBets',
  setup() {
    const bets = ref([]);
    const loading = ref(true);
    const error = ref(null);

    const fetchMyBets = async () => {
      loading.value = true;
      error.value = null;
      try {
        const response = await api.getMySportsBets();
        bets.value = response.data;
      } catch (err) {
        console.error('Failed to fetch my bets:', err);
        error.value = err.message || 'An unknown error occurred.';
      } finally {
        loading.value = false;
      }
    };

    const formatDateTime = (isoString) => {
      if (!isoString) return '';
      const date = new Date(isoString);
      return date.toLocaleString();
    };

    const getStatusClass = (status) => {
      switch (status) {
        case 'Won':
          return 'text-green-500';
        case 'Lost':
          return 'text-red-500';
        case 'Pending':
          return 'text-yellow-500';
        case 'Void':
        case 'Refunded':
          return 'text-gray-500';
        default:
          return 'text-text-primary';
      }
    };

    onMounted(fetchMyBets);

    return {
      bets,
      loading,
      error,
      formatDateTime,
      getStatusClass,
    };
  },
};
</script>

<style scoped>
/* Scoped styles here */
</style>
```
