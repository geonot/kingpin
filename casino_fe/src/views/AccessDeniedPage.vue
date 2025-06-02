<template>
  <div class="flex flex-col items-center justify-center min-h-[calc(100vh-200px)] text-center px-4">
    <div class="bg-white dark:bg-dark-card p-8 md:p-12 rounded-xl shadow-lg">
      <h1 class="text-4xl font-bold text-red-600 dark:text-red-400 mb-4">Access Denied</h1>
      <img src="@/assets/logo.png" alt="Access Denied" class="mx-auto h-24 w-auto mb-6 opacity-50">
      <p class="text-lg text-gray-700 dark:text-gray-300 mb-6">
        You do not have the necessary permissions to access this page.
      </p>
      <router-link
        to="/"
        class="px-6 py-3 bg-royal-blue text-white font-semibold rounded-lg hover:bg-dark-blue transition-colors focus:outline-none focus:ring-2 focus:ring-royal-blue focus:ring-offset-2"
      >
        Go to Homepage
      </router-link>
    </div>
  </div>
</template>

<script setup>
// No specific script logic needed for this simple static page.
// Name can be inferred by filename or explicitly set if using defineComponent
// import { defineComponent } from 'vue';
// export default defineComponent({
//   name: 'AccessDeniedPage',
// });
</script>

<style scoped>
/* Add specific styles if needed */
</style>
