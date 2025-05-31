<template>
  <div class="admin-dashboard p-4 md:p-8">
    <h1 class="text-3xl font-bold mb-6 text-gray-800 dark:text-gray-100">Admin Dashboard</h1>

    <!-- Loading/Error State -->
    <div v-if="loading" class="text-center py-10">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-royal-blue dark:border-light-purple mx-auto"></div>
        <p class="mt-3 text-gray-600 dark:text-gray-300">Loading dashboard data...</p>
    </div>
    <div v-if="error" class="alert-error">
      {{ error }}
    </div>

    <!-- Dashboard Stats -->
    <div v-if="dashboardData" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div class="stat-card">
        <i class="fas fa-users text-3xl text-blue-500"></i>
        <div class="ml-4">
          <p class="text-sm text-gray-500 dark:text-gray-400">Total Users</p>
          <p class="text-2xl font-bold dark:text-white">{{ dashboardData.total_users?.toLocaleString() ?? 'N/A' }}</p>
        </div>
      </div>
      <div class="stat-card">
         <i class="fas fa-gamepad text-3xl text-green-500"></i>
         <div class="ml-4">
           <p class="text-sm text-gray-500 dark:text-gray-400">Total Sessions</p>
           <p class="text-2xl font-bold dark:text-white">{{ dashboardData.total_sessions?.toLocaleString() ?? 'N/A' }}</p>
         </div>
       </div>
       <div class="stat-card">
         <i class="fas fa-exchange-alt text-3xl text-yellow-500"></i>
         <div class="ml-4">
           <p class="text-sm text-gray-500 dark:text-gray-400">Total Transactions</p>
           <p class="text-2xl font-bold dark:text-white">{{ dashboardData.total_transactions?.toLocaleString() ?? 'N/A' }}</p>
         </div>
       </div>
       <div class="stat-card">
         <i class="fas fa-hourglass-half text-3xl text-red-500"></i>
         <div class="ml-4">
           <p class="text-sm text-gray-500 dark:text-gray-400">Pending Withdrawals</p>
           <p class="text-2xl font-bold dark:text-white">{{ dashboardData.pending_withdrawals?.toLocaleString() ?? 'N/A' }}</p>
         </div>
       </div>
        <div class="stat-card">
         <i class="fas fa-tags text-3xl text-purple-500"></i>
         <div class="ml-4">
           <p class="text-sm text-gray-500 dark:text-gray-400">Active Bonus Codes</p>
           <p class="text-2xl font-bold dark:text-white">{{ dashboardData.active_bonus_codes?.toLocaleString() ?? 'N/A' }} / {{ dashboardData.total_bonus_codes?.toLocaleString() ?? 'N/A' }}</p>
         </div>
       </div>
       <!-- Add more cards as needed -->
    </div>

    <!-- Admin Sections (Placeholders) -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
       <div class="admin-section card">
           <h2 class="text-xl font-semibold mb-4 dark:text-white">User Management</h2>
           <p class="text-gray-600 dark:text-gray-400 mb-4">View, search, and manage user accounts.</p>
           <button @click="navigateTo('/admin/users')" class="btn-secondary">Manage Users</button>
       </div>
        <div class="admin-section card">
           <h2 class="text-xl font-semibold mb-4 dark:text-white">Bonus Code Management</h2>
           <p class="text-gray-600 dark:text-gray-400 mb-4">Create, update, and manage promotional bonus codes.</p>
           <button @click="navigateTo('/admin/bonus-codes')" class="btn-secondary">Manage Bonus Codes</button>
       </div>
       <div class="admin-section card">
           <h2 class="text-xl font-semibold mb-4 dark:text-white">Transaction Management</h2>
           <p class="text-gray-600 dark:text-gray-400 mb-4">View transaction history and process pending withdrawals.</p>
           <button @click="navigateTo('/admin/transactions')" class="btn-secondary">Manage Transactions</button>
       </div>
        <div class="admin-section card">
           <h2 class="text-xl font-semibold mb-4 dark:text-white">Balance Transfers</h2>
           <p class="text-gray-600 dark:text-gray-400 mb-4">Manually adjust user balances or transfer funds.</p>
           <button @click="navigateTo('/admin/balance-transfer')" class="btn-secondary">Transfer Balance</button>
       </div>
       <!-- Add more sections for Slot Management, Settings, etc. -->
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import axios from 'axios'; // Import axios

const store = useStore();
const router = useRouter();
const dashboardData = ref(null);
const loading = ref(true);
const error = ref(null);

const fetchDashboardData = async () => {
  loading.value = true;
  error.value = null;
  try {
     const config = { headers: { Authorization: `Bearer ${store.state.userSession}` } };
     const response = await axios.get('/api/admin/dashboard', config);
    if (response.data.status) {
      dashboardData.value = response.data.dashboard_data;
    } else {
      throw new Error(response.data.status_message || 'Failed to load dashboard data.');
    }
  } catch (err) {
    console.error("Error fetching admin dashboard data:", err.response?.data || err.message);
    error.value = err.response?.data?.status_message || err.message || 'Could not fetch dashboard data.';
     // Check for 403 Forbidden specifically
     if (err.response?.status === 403) {
        error.value = "Access Denied: You do not have permission to view this page.";
    }
  } finally {
    loading.value = false;
  }
};

const navigateTo = (path) => {
    router.push(path);
};

onMounted(() => {
  // Ensure user is admin before fetching (redundant if route guard exists, but good practice)
  if (!store.getters.isAdmin) {
       error.value = "Access Denied.";
       loading.value = false;
       // Optional: Redirect immediately
       // router.push('/');
       return;
   }
  fetchDashboardData();
});
</script>

<style scoped>
.stat-card {
  @apply bg-white dark:bg-dark-card p-4 rounded-lg shadow flex items-center transition-shadow duration-200 hover:shadow-md;
}

.admin-section h2 {
    @apply border-b border-gray-200 dark:border-gray-700 pb-2 mb-4;
}
</style>