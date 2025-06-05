<template>
  <div class="container mx-auto py-8 px-4">
    <h2 class="text-center mb-8">Promotions</h2>
    <div class="card max-w-2xl mx-auto">
      <h3 class="mb-4">Latest Promotions</h3>
      <p class="text-text-secondary mb-6">
        Discover our latest promotions and special events here. We regularly update this section with new
        opportunities to enhance your gaming experience. Check back often!
      </p>
      <div class="mt-6 p-6 border border-dashed border-border rounded-md text-center text-text-secondary">
        <i class="fas fa-bullhorn text-4xl text-highlight mb-3"></i> <!-- Example Icon -->
        <p class="font-semibold text-lg">Promotion Details Placeholder</p>
        <p class="text-sm">Details of current promotions will appear here.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'PromotionsPage',
});
</script>

<style scoped>
/* Add specific styles if needed */
</style>
