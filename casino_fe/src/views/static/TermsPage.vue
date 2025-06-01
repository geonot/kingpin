<template>
  <div class="container mx-auto py-8 px-4">
    <div class="bg-white dark:bg-gray-800 shadow-xl rounded-lg p-6 md:p-10">
      <h1 class="text-3xl font-bold mb-6 text-gray-900 dark:text-gray-100">Terms and Conditions</h1>
      <div class="prose dark:prose-invert max-w-none"> <!-- Using prose for better text styling -->
        <p>Our terms and conditions are currently being updated. Please check back later.</p>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>
        <p>Suspendisse potenti. Cras consequat, quam nec sollicitudin pulvinar, sem lacus sagittis enim, ac tempor sapien ligula et dui. Nulla facilisi. Vivamus et fringilla nisi. Integer nec risus nec est interdum sollicitudin vitae at nulla. Phasellus eget sapien eget justo imperdiet varius.</p>
        <h2 class="text-2xl font-semibold mt-6 mb-3 text-gray-800 dark:text-gray-200">Section 1: Introduction</h2>
        <p>Further details will be provided here. We aim to be transparent and fair in all our dealings. Please read these terms carefully before using our services.</p>
        <h2 class="text-2xl font-semibold mt-6 mb-3 text-gray-800 dark:text-gray-200">Section 2: Your Obligations</h2>
        <ul class="list-disc pl-5 space-y-1">
            <li>You must be of legal age to gamble in your jurisdiction.</li>
            <li>You are responsible for any activity conducted under your account.</li>
            <li>You must not use our services for any unlawful purpose.</li>
        </ul>
      </div>
    </div>
  </div>
</template>
<script>
export default {
  name: 'TermsPage',
};
</script>
<style scoped>
/* Add Tailwind's typography plugin styles if not globally configured,
   or define specific prose styles here.
   Assuming @tailwindcss/typography is installed and configured in tailwind.config.js for dark:prose-invert */
</style>
