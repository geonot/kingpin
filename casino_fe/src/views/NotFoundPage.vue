<template>
  <div class="container mx-auto p-4 text-center flex flex-col items-center justify-center min-h-[calc(100vh-200px)]">
    <!-- Adjusted min-height to account for header/footer roughly -->
    <div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-xl">
      <h1 class="text-4xl md:text-6xl font-bold mb-6 text-gray-800 dark:text-gray-100">404</h1>
      <p class="text-xl md:text-2xl text-gray-600 dark:text-gray-300 mb-8">Oops! Page Not Found.</p>
      <p class="text-gray-500 dark:text-gray-400 mb-8">The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.</p>
      <router-link
        to="/"
        class="px-6 py-3 bg-royal-blue text-white font-semibold rounded-lg shadow-md hover:bg-dark-blue dark:bg-light-purple dark:hover:bg-purple-700 transition-colors duration-200"
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
