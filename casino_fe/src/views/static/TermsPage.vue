<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6 text-gray-800 dark:text-white">Terms and Conditions</h1>

    <div class="prose dark:prose-invert max-w-none bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
      <p class="mb-4">
        Welcome to Kingpin Casino! These terms and conditions outline the rules and regulations for the use of Kingpin Casino's Website.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">1. Acceptance of Terms</h2>
      <p class="mb-4">
        By accessing this website we assume you accept these terms and conditions. Do not continue to use Kingpin Casino if you do not agree to take all of the terms and conditions stated on this page.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">2. Cookies</h2>
      <p class="mb-4">
        We employ the use of cookies. By accessing Kingpin Casino, you agreed to use cookies in agreement with the Kingpin Casino's Privacy Policy. Most interactive websites use cookies to let us retrieve the user’s details for each visit.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">3. License</h2>
      <p class="mb-4">
        Unless otherwise stated, Kingpin Casino and/or its licensors own the intellectual property rights for all material on Kingpin Casino. All intellectual property rights are reserved. You may access this from Kingpin Casino for your own personal use subjected to restrictions set in these terms and conditions.
      </p>
      <p class="mb-4">You must not:</p>
      <ul class="list-disc list-inside mb-4">
        <li>Republish material from Kingpin Casino</li>
        <li>Sell, rent or sub-license material from Kingpin Casino</li>
        <li>Reproduce, duplicate or copy material from Kingpin Casino</li>
        <li>Redistribute content from Kingpin Casino</li>
      </ul>

      <h2 class="text-2xl font-semibold mt-6 mb-3">4. User Comments</h2>
      <p class="mb-4">
        Parts of this website offer an opportunity for users to post and exchange opinions and information in certain areas of the website. Kingpin Casino does not filter, edit, publish or review Comments prior to their presence on the website. Comments do not reflect the views and opinions of Kingpin Casino, its agents and/or affiliates.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">5. Governing Law</h2>
      <p class="mb-4">
        These terms and conditions will be governed by and interpreted in accordance with the laws of the jurisdiction in which Kingpin Casino operates, and you submit to the non-exclusive jurisdiction of the state and federal courts located in that jurisdiction for the resolution of any disputes.
      </p>

      <p class="mt-6 font-semibold">
        Please read these terms and conditions carefully. This is a placeholder document and should be replaced with actual, legally sound terms and conditions before any production launch.
      </p>
    </div>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'TermsPage',
  setup() {
    // No specific setup logic needed for this static page yet
    return {};
  },
});
</script>

<style scoped>
/* If you need specific styles for this page, add them here.
   Using Tailwind's prose class for typography styling. */
.prose h1, .prose-invert h1 {
  font-size: 1.875rem; /* 30px */
  margin-bottom: 1.5rem;
}
.prose h2, .prose-invert h2 {
  font-size: 1.5rem; /* 24px */
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}
</style>
