<template>
  <div class="game-hud p-3 bg-gray-900 bg-opacity-60 rounded-lg shadow-xl text-white fixed top-4 right-4 min-w-[250px] backdrop-blur-sm">
    <!-- Expedition Timer -->
    <div v.if="isExpeditionActive" class="mb-3">
      <p class="text-sm text-yellow-400 flex justify-between items-center">
        <span>Expedition Time:</span>
        <span class="font-mono text-lg text-yellow-300">{{ formattedTimeLeft }}</span>
      </p>
    </div>

    <!-- Current Haul Value -->
    <div class="mb-3">
      <p class="text-sm text-green-400 flex justify-between items-center">
        <span>Current Haul:</span>
        <span class="font-mono text-lg text-green-300">{{ formattedHaulValue }} sats</span>
      </p>
    </div>

    <!-- Game Messages/Alerts -->
    <div v-if="gameMessages && gameMessages.length > 0" class="mt-2 pt-2 border-t border-gray-700">
      <h4 class="text-xs text-gray-400 uppercase mb-1">Alerts:</h4>
      <ul class="space-y-1 text-xs max-h-24 overflow-y-auto custom-scrollbar-hud">
        <li
          v-for="(message, index) in gameMessages"
          :key="index"
          :class="getMessageClass(message)"
          class="p-1 rounded text-opacity-90"
        >
          {{ message.text || message }}
        </li>
      </ul>
    </div>

     <!-- Placeholder for Expedition Status -->
    <div class="mt-2" v-if="!isExpeditionActive && expeditionStatus">
        <p class="text-sm text-gray-400">Status: <span :class="statusClass">{{ expeditionStatus }}</span></p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GameHUD',
  props: {
    timeLeft: { // in seconds
      type: Number,
      default: 0,
    },
    currentHaulValue: {
      type: Number,
      default: 0,
    },
    gameMessages: { // Array of strings or objects like { text: 'Msg', type: 'warning' }
      type: Array,
      default: () => [],
    },
    isExpeditionActive: {
        type: Boolean,
        default: false,
    },
    expeditionStatus: { // e.g., "Active", "Completed", "Aborted"
        type: String,
        default: ''
    }
  },
  computed: {
    formattedTimeLeft() {
      if (this.timeLeft <= 0) return '00:00';
      const minutes = Math.floor(this.timeLeft / 60);
      const seconds = this.timeLeft % 60;
      return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    },
    formattedHaulValue() {
      return this.currentHaulValue.toLocaleString();
    },
    statusClass() {
        if (this.expeditionStatus === 'Completed') return 'text-green-400 font-semibold';
        if (this.expeditionStatus === 'Aborted') return 'text-red-400 font-semibold';
        return 'text-yellow-400 font-semibold'; // For active or other statuses
    }
  },
  methods: {
    getMessageClass(message) {
      if (typeof message === 'object' && message.type) {
        switch (message.type) {
          case 'error': return 'bg-red-700 bg-opacity-50 text-red-200';
          case 'warning': return 'bg-yellow-600 bg-opacity-50 text-yellow-100';
          case 'info': return 'bg-blue-600 bg-opacity-50 text-blue-100';
          case 'success': return 'bg-green-600 bg-opacity-50 text-green-100';
          default: return 'bg-gray-700 bg-opacity-50 text-gray-300';
        }
      }
      return 'bg-gray-700 bg-opacity-50 text-gray-300'; // Default for string messages
    }
  }
};
</script>

<style scoped>
.game-hud {
  /* Main HUD styling */
}
.custom-scrollbar-hud::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar-hud::-webkit-scrollbar-track {
  background: #4b5563; /* bg-gray-600 */
  border-radius: 8px;
}
.custom-scrollbar-hud::-webkit-scrollbar-thumb {
  background: #fcd34d; /* bg-yellow-300 */
  border-radius: 8px;
}
.custom-scrollbar-hud::-webkit-scrollbar-thumb:hover {
  background: #f59e0b; /* bg-yellow-500 */
}
</style>
