<template>
  <div class="container mx-auto p-4 text-center flex flex-col items-center justify-center min-h-[calc(100vh-200px)]">
    <!-- Adjusted min-height to account for header/footer roughly -->
    <div class="card p-8">
      <h1 class="text-6xl font-bold mb-6">404</h1>
      <p class="text-xl md:text-2xl text-text-secondary mb-8">Oops! Page Not Found.</p>
      <p class="text-text-secondary mb-8">The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.</p>
      <router-link
        to="/"
        class="btn-secondary"
      >
        Go Back to Home
      </router-link>
    </div>
  </div>
</template>
<script>
export default {
  name: 'NotFoundPage',
};
</script>
<style scoped>
/* Minimal height to help center content on potentially empty pages, adjust as needed based on header/footer height */
.min-h-\[calc\(100vh-200px\)\] {
  min-height: calc(100vh - 200px); /* Example: 100px for header, 100px for footer */
}
</style>
