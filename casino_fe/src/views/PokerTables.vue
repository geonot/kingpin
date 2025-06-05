<template>
  <div class="poker-tables-view">
    <h1>Active Poker Tables</h1>
    <div v-if="loading" class="loading">Loading tables...</div>
    <div v-if="error" class="error-message">
      <p>Error loading poker tables: {{ error.message || 'Unknown error' }}</p>
      <pre v-if="error.response && error.response.data">{{ error.response.data }}</pre>
    </div>
    <div v-if="!loading && !error && tables.length === 0" class="no-tables">
      No active poker tables found.
    </div>
    <div v-if="!loading && !error && tables.length > 0" class="tables-list">
      <div v-for="table in tables" :key="table.id" class="table-card">
        <h2>{{ table.name }}</h2>
        <p><strong>Game Type:</strong> {{ table.game_type }}</p>
        <p><strong>Limit Type:</strong> {{ table.limit_type }}</p>
        <p><strong>Blinds:</strong> {{ table.small_blind }} / {{ table.big_blind }}</p>
        <p><strong>Buy-in:</strong> {{ table.min_buy_in }} - {{ table.max_buy_in }}</p>
        <p><strong>Max Seats:</strong> {{ table.max_seats }}</p>
        <p><strong>Status:</strong> {{ table.is_active ? 'Active' : 'Inactive' }}</p>
        <router-link :to="{ name: 'PokerTable', params: { id: table.id } }" class="join-button">
          View Table
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '@/services/apiClient'; // Assuming apiClient is configured

const tables = ref([]);
const loading = ref(true);
const error = ref(null);

const fetchPokerTables = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.get('/poker/tables');
    if (response.data && response.data.status && Array.isArray(response.data.tables)) {
      tables.value = response.data.tables;
    } else {
      throw new Error('Invalid API response structure for poker tables.');
    }
  } catch (err) {
    console.error('Failed to fetch poker tables:', err);
    error.value = err;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchPokerTables();
});
</script>

<style scoped>
.poker-tables-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: Arial, sans-serif;
}

h1 {
  text-align: center;
  margin-bottom: 30px;
  color: #333;
}

.loading {
  text-align: center;
  font-size: 1.2em;
  color: #555;
}

.error-message {
  background-color: #ffebee;
  color: #c62828;
  border: 1px solid #c62828;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 20px;
}

.error-message p {
  margin: 0;
}

.error-message pre {
  margin-top: 10px;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 0.9em;
  background-color: #fce4ec;
  padding: 10px;
  border-radius: 3px;
}


.no-tables {
  text-align: center;
  font-size: 1.1em;
  color: #777;
  margin-top: 20px;
}

.tables-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.table-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  background-color: #fff;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
  transition: transform 0.2s ease-in-out;
}

.table-card:hover {
  transform: translateY(-5px);
}

.table-card h2 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #007bff; /* Bootstrap primary color */
}

.table-card p {
  margin: 8px 0;
  color: #555;
  font-size: 0.95em;
}

.table-card p strong {
  color: #333;
}

.join-button {
  display: inline-block;
  margin-top: 15px;
  padding: 10px 15px;
  background-color: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 5px;
  text-align: center;
  transition: background-color 0.2s ease;
}

.join-button:hover {
  background-color: #0056b3;
}
</style>
