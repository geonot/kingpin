<template>
  <div class="container mx-auto px-4 py-10 text-center">
    <h1 class="text-3xl font-bold mb-4 text-gray-700 dark:text-gray-200">{{ title }}</h1>
    <p class="text-gray-600 dark:text-gray-400">
      This page is under construction or the content is not yet available. Please check back later.
    </p>
    <div class="mt-8">
        <router-link to="/" class="btn-secondary">Go Back Home</router-link>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

// Derive title from route name or meta, fallback to generic
const title = computed(() => {
    if (route.meta?.title) return route.meta.title;
    if (route.name) return route.name.replace(/([A-Z])/g, ' $1').trim(); // Convert CamelCase to Title Case
    return 'Content Placeholder';
});
</script>

<style scoped>
/* Add specific styles if needed */
</style>


