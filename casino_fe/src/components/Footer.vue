<template>
  <footer class="bg-gray-900 dark:bg-black text-gray-400 dark:text-gray-500 p-6 text-center text-sm mt-auto">
    <!-- Footer content -->
    <div class="container mx-auto">
        <p>&copy; {{ new Date().getFullYear() }} Kingpin Casino. All rights reserved.</p>
        <p class="mt-1">Please gamble responsibly. For help, visit BeGambleAware.org.</p>
        <!-- Optional: Links to Terms, Privacy Policy, etc. -->
        <nav class="mt-2 space-x-4">
            <router-link to="/terms" class="hover:text-gray-300">Terms</router-link>
            <router-link to="/privacy" class="hover:text-gray-300">Privacy Policy</router-link>
             <router-link to="/responsible-gaming" class="hover:text-gray-300">Responsible Gaming</router-link>
        </nav>
    </div>
  </footer>
</template>

<script setup>
// No script logic needed for simple footer
</script>

<style scoped>
/* Add specific footer styles if Tailwind isn't enough */
footer {
   /* Example: border-top: 1px solid #333; */
}
</style>


