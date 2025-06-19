<template>
  <div class="betting-controls p-4 bg-gray-800 rounded-lg shadow-md">
    <h3 class="text-lg font-semibold text-yellow-400 mb-3">Expedition Setup</h3>

    <div class="mb-4">
      <p class="text-sm text-gray-400">Your Balance: <span class="font-bold text-green-400">{{ formattedBalance }} sats</span></p>
    </div>

    <div class="mb-4">
      <label for="betAmount" class="block text-sm font-medium text-gray-300 mb-1">Bet Amount (sats)</label>
      <div class="flex items-center">
        <button
          @click="decreaseBet"
          :disabled="isExpeditionActive || localBetAmount <= minBet"
          class="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-l disabled:opacity-50 disabled:cursor-not-allowed">
          -
        </button>
        <input
          type="number"
          id="betAmount"
          v-model.number="localBetAmount"
          :disabled="isExpeditionActive"
          @change="validateBetAmount"
          class="w-full px-3 py-2 text-center bg-gray-700 text-white border-gray-600 focus:ring-yellow-500 focus:border-yellow-500 disabled:opacity-70"
          :min="minBet"
          :max="maxBet"
          step="10"
        />
        <button
          @click="increaseBet"
          :disabled="isExpeditionActive || localBetAmount >= maxBet"
          class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-r disabled:opacity-50 disabled:cursor-not-allowed">
          +
        </button>
      </div>
      <p v-if="betError" class="text-red-400 text-xs mt-1">{{ betError }}</p>
    </div>

    <button
      @click="handleLaunch"
      :disabled="isExpeditionActive || localBetAmount <= 0 || localBetAmount > currentBalance || !!betError"
      class="w-full bg-yellow-500 hover:bg-yellow-600 text-gray-900 font-bold py-3 px-4 rounded-lg transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed">
      {{ isExpeditionActive ? 'Expedition Underway' : 'Launch Expedition' }}
    </button>
  </div>
</template>

<script>
export default {
  name: 'BettingControls',
  props: {
    currentBalance: {
      type: Number,
      required: true,
      default: 0,
    },
    isExpeditionActive: {
      type: Boolean,
      required: true,
      default: false,
    },
    minBet: {
      type: Number,
      default: 10,
    },
    maxBet: {
      type: Number,
      default: 10000,
    },
    defaultBet: {
        type: Number,
        default: 100,
    }
  },
  data() {
    return {
      localBetAmount: this.defaultBet,
      betStep: 10,
      betError: '',
    };
  },
  computed: {
    formattedBalance() {
      return this.currentBalance.toLocaleString();
    }
  },
  watch: {
    defaultBet(newVal) {
        this.localBetAmount = newVal;
        this.validateBetAmount();
    }
  },
  methods: {
    validateBetAmount() {
      this.betError = '';
      if (this.localBetAmount < this.minBet) {
        this.betError = `Bet cannot be less than ${this.minBet}.`;
        // this.localBetAmount = this.minBet; // Optionally clamp
      } else if (this.localBetAmount > this.maxBet) {
         this.betError = `Bet cannot exceed ${this.maxBet}.`;
        // this.localBetAmount = this.maxBet; // Optionally clamp
      } else if (this.localBetAmount > this.currentBalance) {
        this.betError = 'Bet amount exceeds your current balance.';
      }
    },
    increaseBet() {
      if (this.localBetAmount + this.betStep <= this.maxBet) {
        this.localBetAmount += this.betStep;
      } else {
        this.localBetAmount = this.maxBet;
      }
      this.validateBetAmount();
    },
    decreaseBet() {
      if (this.localBetAmount - this.betStep >= this.minBet) {
        this.localBetAmount -= this.betStep;
      } else {
        this.localBetAmount = this.minBet;
      }
      this.validateBetAmount();
    },
    handleLaunch() {
      this.validateBetAmount();
      if (this.betError) {
        // Optionally, alert the user or rely on disabled state
        console.warn("Bet validation failed:", this.betError);
        return;
      }
      if (!this.isExpeditionActive && this.localBetAmount > 0 && this.localBetAmount <= this.currentBalance) {
        this.$emit('launch-expedition', this.localBetAmount);
      }
    },
  },
  mounted() {
    this.localBetAmount = this.defaultBet;
    this.validateBetAmount();
  }
};
</script>

<style scoped>
/* Basic styling, assuming Tailwind is used for most things */
.betting-controls {
  /* Add any specific styles if needed */
}
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type="number"] {
  -moz-appearance: textfield; /* Firefox */
}
</style>
