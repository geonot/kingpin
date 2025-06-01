<template>
  <div class="container mx-auto p-4">
    <h1 class="text-2xl font-bold mb-6 text-gray-900 dark:text-gray-100">Admin Dashboard</h1>
    <div v-if="loading" class="text-center py-10">
      <p class="text-gray-700 dark:text-gray-300">Loading dashboard data...</p>
      <!-- Optional: Add a spinner SVG or component: e.g., a Tailwind spinner -->
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-royal-blue dark:border-light-purple mt-4"></div>
    </div>
    <div v-else-if="error" class="text-red-500 dark:text-red-400 text-center p-4 bg-red-100 dark:bg-red-900 rounded-md">
      <p class="font-semibold">Error Loading Dashboard Data</p>
      <p>{{ error }}</p>
    </div>
    <div v-else-if="dashboardData" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Total Users</h2>
        <p class="text-3xl text-gray-900 dark:text-gray-100">{{ dashboardData.total_users }}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Total Game Sessions</h2>
        <p class="text-3xl text-gray-900 dark:text-gray-100">{{ dashboardData.total_sessions }}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Total Transactions</h2>
        <p class="text-3xl text-gray-900 dark:text-gray-100">{{ dashboardData.total_transactions }}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Pending Withdrawals</h2>
        <p class="text-3xl text-orange-500 dark:text-orange-400">{{ dashboardData.pending_withdrawals }}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Total Bonus Codes</h2>
        <p class="text-3xl text-gray-900 dark:text-gray-100">{{ dashboardData.total_bonus_codes }}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Active Bonus Codes</h2>
        <p class="text-3xl text-gray-900 dark:text-gray-100">{{ dashboardData.active_bonus_codes }}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 p-4 shadow rounded">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Total User Balance (Sats)</h2>
        <p class="text-3xl text-gray-900 dark:text-gray-100">{{ dashboardData.total_balance_sats }}</p>
      </div>
    </div>
    <div v-else class="text-center py-10">
      <p class="text-gray-700 dark:text-gray-300">No dashboard data available.</p>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import axios from 'axios';

export default {
  name: 'AdminDashboard',
  setup() {
    const dashboardData = ref(null);
    const loading = ref(true);
    const error = ref(null);

    const fetchDashboardData = async () => {
      loading.value = true;
      error.value = null;
      try {
        const token = localStorage.getItem('userSession');
        const response = await axios.get('/api/admin/dashboard', {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (response.data.status && response.data.dashboard_data) {
          dashboardData.value = response.data.dashboard_data;
        } else {
          throw new Error(response.data.status_message || 'Failed to fetch dashboard data.');
        }
      } catch (err) {
        console.error('Error fetching admin dashboard data:', err);
        error.value = err.response?.data?.status_message || err.message || 'An unknown error occurred.';
      } finally {
        loading.value = false;
      }
    };

    onMounted(fetchDashboardData);

    return {
      dashboardData,
      loading,
      error,
    };
  },
};
</script>
<style scoped>
/* Additional specific styles if needed */
.text-orange-500 { /* Ensure this is defined or use Tailwind's default if available */
  color: #F97316; /* Tailwind orange-500 */
}
.dark .text-orange-400 { /* Ensure this is defined or use Tailwind's default if available */
  color: #FB923C; /* Tailwind orange-400 */
}
</style>
