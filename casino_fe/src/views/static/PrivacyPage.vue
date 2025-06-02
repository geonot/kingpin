<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6 text-gray-800 dark:text-white">Privacy Policy</h1>

    <div class="prose dark:prose-invert max-w-none bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
      <p class="mb-4">
        Your privacy is important to us. It is Kingpin Casino's policy to respect your privacy regarding any information we may collect from you across our website.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">1. Information We Collect</h2>
      <p class="mb-4">
        We only ask for personal information when we truly need it to provide a service to you. We collect it by fair and lawful means, with your knowledge and consent. We also let you know why we’re collecting it and how it will be used.
      </p>
      <p class="mb-4">
        Information we may collect includes:
      </p>
      <ul class="list-disc list-inside mb-4">
        <li>Log data (e.g., IP address, browser type, ISP, referring/exit pages, date/time stamp)</li>
        <li>Information you provide upon registration (e.g., username, email address)</li>
        <li>Information related to your transactions and gaming activity</li>
        <li>Cookies and similar tracking technologies</li>
      </ul>

      <h2 class="text-2xl font-semibold mt-6 mb-3">2. How We Use Your Information</h2>
      <p class="mb-4">
        We use the information we collect in various ways, including to:
      </p>
      <ul class="list-disc list-inside mb-4">
        <li>Provide, operate, and maintain our website</li>
        <li>Improve, personalize, and expand our website</li>
        <li>Understand and analyze how you use our website</li>
        <li>Develop new products, services, features, and functionality</li>
        <li>Communicate with you, either directly or through one of our partners, including for customer service, to provide you with updates and other information relating to the website, and for marketing and promotional purposes</li>
        <li>Process your transactions and prevent fraud</li>
        <li>Comply with legal obligations</li>
      </ul>

      <h2 class="text-2xl font-semibold mt-6 mb-3">3. Log Files</h2>
      <p class="mb-4">
        Kingpin Casino follows a standard procedure of using log files. These files log visitors when they visit websites. All hosting companies do this and a part of hosting services' analytics. The information collected by log files include internet protocol (IP) addresses, browser type, Internet Service Provider (ISP), date and time stamp, referring/exit pages, and possibly the number of clicks. These are not linked to any information that is personally identifiable.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">4. Cookies and Web Beacons</h2>
      <p class="mb-4">
        Like any other website, Kingpin Casino uses 'cookies'. These cookies are used to store information including visitors' preferences, and the pages on the website that the visitor accessed or visited. The information is used to optimize the users' experience by customizing our web page content based on visitors' browser type and/or other information.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">5. Security of Your Information</h2>
      <p class="mb-4">
        We take reasonable precautions to protect your information. However, no method of transmission over the Internet, or method of electronic storage, is 100% secure. While we strive to use commercially acceptable means to protect your Personal Information, we cannot guarantee its absolute security.
      </p>

      <h2 class="text-2xl font-semibold mt-6 mb-3">6. Changes to This Privacy Policy</h2>
      <p class="mb-4">
        We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page. You are advised to review this Privacy Policy periodically for any changes.
      </p>

      <p class="mt-6 font-semibold">
        This is a placeholder privacy policy and should be replaced with a comprehensive, legally compliant document before production launch.
      </p>
    </div>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'PrivacyPage',
  setup() {
    return {};
  },
});
</script>

<style scoped>
/* Using Tailwind's prose class for typography styling. */
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
