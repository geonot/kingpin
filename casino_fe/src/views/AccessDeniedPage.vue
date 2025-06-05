<template>
  <div class="flex flex-col items-center justify-center min-h-[calc(100vh-200px)] text-center px-4">
    <div class="card p-8 md:p-12">
      <h1 class="text-4xl font-bold text-brand-warning mb-4">Access Denied</h1>
      <img src="@/assets/logo.png" alt="Access Denied" class="mx-auto h-24 w-auto mb-6 opacity-50">
      <p class="text-lg text-text-secondary mb-6">
        You do not have the necessary permissions to access this page.
      </p>
      <router-link
        to="/"
        class="btn-secondary"
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
