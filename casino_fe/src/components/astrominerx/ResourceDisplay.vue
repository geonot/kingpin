<template>
  <div class="resource-display p-4 bg-gray-800 bg-opacity-70 rounded-lg shadow-lg backdrop-blur-md">
    <h3 class="text-lg font-semibold text-yellow-400 mb-3 border-b border-gray-700 pb-2">Collected Resources</h3>

    <div v.if="collectedResources.length === 0" class="text-gray-400 italic">
      No resources collected yet.
    </div>

    <div v-else class="max-h-60 overflow-y-auto pr-2 custom-scrollbar">
      <ul class="space-y-2">
        <li
          v-for="(resource, index) in aggregatedResources"
          :key="index"
          class="flex justify-between items-center p-2 bg-gray-700 rounded hover:bg-gray-600 transition-colors"
        >
          <span class="text-gray-200 capitalize">{{ resource.name.replace('_', ' ') }} (x{{ resource.quantity }})</span>
          <span class="font-semibold text-green-400">{{ formatValue(resource.totalValue) }} sats</span>
        </li>
      </ul>
    </div>

    <div class="mt-4 pt-3 border-t border-gray-700">
      <p class="text-md font-bold text-gray-200">
        Total Haul Value:
        <span class="text-xl text-green-300">{{ formatValue(totalValue) }} sats</span>
      </p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ResourceDisplay',
  props: {
    collectedResources: {
      type: Array, // Expected: Array of { name: String, value: Number } from each asteroid scan
      required: true,
      default: () => [],
    },
    totalValue: { // This prop might be calculated in the parent based on expedition.total_value_collected
      type: Number,
      required: true,
      default: 0,
    },
  },
  computed: {
    aggregatedResources() {
      if (!this.collectedResources || this.collectedResources.length === 0) {
        return [];
      }
      const aggregation = this.collectedResources.reduce((acc, resource) => {
        if (resource.value > 0) { // Only include valuable resources
            const existing = acc.find(r => r.name === resource.name);
            if (existing) {
            existing.quantity += 1;
            existing.totalValue += resource.value;
            } else {
            acc.push({
                name: resource.name,
                quantity: 1,
                totalValue: resource.value,
                individualValue: resource.value // Store individual value if needed for display later
            });
            }
        }
        return acc;
      }, []);

      // Sort by total value or name
      return aggregation.sort((a, b) => b.totalValue - a.totalValue);
    }
  },
  methods: {
    formatValue(value) {
      return Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    }
  }
};
</script>

<style scoped>
.resource-display {
  /* Styles for the resource display panel */
}
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #374151; /* bg-gray-700 */
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #f59e0b; /* bg-yellow-500 */
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #d97706; /* bg-yellow-600 */
}
</style>
