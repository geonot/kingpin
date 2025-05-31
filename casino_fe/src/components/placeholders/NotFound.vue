<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-200px)] text-center px-4">
    <div>
       <h1 class="text-9xl font-extrabold text-royal-purple dark:text-light-purple tracking-widest">404</h1>
       <div class="bg-gold dark:bg-dark-gold px-2 text-sm rounded rotate-12 absolute mt-[-40px] ml-[80px]">
            Page Not Found
       </div>
      <p class="mt-4 text-lg text-gray-600 dark:text-gray-400">Oops! The page you're looking for doesn't exist.</p>
      <p class="text-gray-500 dark:text-gray-500">It might have been moved or deleted.</p>
      <div class="mt-8">
        <router-link to="/" class="btn-primary text-lg px-8 py-3 shadow-lg transform hover:scale-105 transition-transform duration-200">
          Go Back Home
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
// No specific script logic needed for 404 page
</script>

<style scoped>
/* Add specific styles if needed */
.absolute {
    /* Adjust positioning of the "Page Not Found" label if needed */
}
</style>


