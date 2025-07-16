<template>
  <div class="bet-slip bg-bg-secondary p-4 rounded-lg shadow-lg">
    <h2 class="text-xl font-bold text-text-primary mb-4 border-b border-gray-700 pb-2">Bet Slip</h2>
    <div v-if="!selection">
      <p class="text-text-secondary">Click on an odd to add it to your slip.</p>
    </div>
    <div v-else class="space-y-4">
      <div>
        <p class="text-sm text-text-secondary">{{ selection.details.market_type }}</p>
        <p class="text-lg font-semibold text-accent">{{ selection.details.display_name }}</p>
        <p class="text-sm text-text-secondary">{{ selection.details.event_name }}</p>
        <div class="flex justify-between items-center mt-1">
          <span class="text-text-primary">Odds:</span>
          <span class="font-bold text-lg text-white">{{ selection.details.decimal_value }}</span>
        </div>
      </div>

      <div class="space-y-2">
        <label for="stake" class="block text-sm font-medium text-text-secondary">Stake (satoshis)</label>
        <input
          type="number"
          id="stake"
          v-model.number="stake"
          class="w-full bg-bg-tertiary text-white border border-gray-600 rounded-md p-2 focus:ring-accent focus:border-accent"
          placeholder="0"
        />
      </div>

      <div class="flex justify-between items-center text-text-primary">
        <span>Potential Payout:</span>
        <span class="font-bold text-lg text-green-400">{{ potentialPayout }} satoshis</span>
      </div>

      <button
        @click="placeBet"
        :disabled="isSubmitting || stake <= 0"
        class="w-full bg-accent hover:bg-accent-dark text-white font-bold py-2 px-4 rounded-md transition-colors duration-200 disabled:bg-gray-600 disabled:cursor-not-allowed">
        <span v-if="isSubmitting">Placing Bet...</span>
        <span v-else>Place Bet</span>
      </button>

      <button
        @click="clearSelection"
        class="w-full bg-gray-700 hover:bg-gray-600 text-text-secondary font-bold py-2 px-4 rounded-md transition-colors duration-200 mt-2">
        Clear
      </button>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue';

export default {
  name: 'BetSlip',
  props: {
    selection: {
      type: Object,
      default: null,
    },
  },
  emits: ['clear-selection', 'place-bet'],
  setup(props, { emit }) {
    const stake = ref(0);
    const isSubmitting = ref(false);

    const potentialPayout = computed(() => {
      if (!props.selection || !stake.value || stake.value <= 0) {
        return 0;
      }
      return Math.floor(stake.value * props.selection.details.decimal_value);
    });

    const clearSelection = () => {
      stake.value = 0;
      emit('clear-selection');
    };

    const placeBet = () => {
        if (stake.value > 0 && props.selection) {
            isSubmitting.value = true;
            emit('place-bet', {
                odds_id: props.selection.id,
                stake_satoshis: stake.value,
                onSuccess: () => {
                    isSubmitting.value = false;
                    clearSelection();
                },
                onError: () => {
                    isSubmitting.value = false;
                }
            });
        }
    };

    return {
      stake,
      isSubmitting,
      potentialPayout,
      clearSelection,
      placeBet,
    };
  },
};
</script>

<style scoped>
.bet-slip {
  position: sticky;
  top: 6rem; /* Adjust based on header height */
}
</style>
```
