<template>
  <div class="poker-table-view">
    <h1 v-if="!loading && tableState && tableState.table_name">Poker Table: {{ tableState.table_name }} (ID: {{ id }})</h1>
    <h1 v-else-if="!loading && !tableState">Poker Table (ID: {{ id }})</h1>
    <h1 v-else>Loading Poker Table...</h1>

    <div v-if="loading" class="loading">Loading table state...</div>
    <div v-if="error" class="error-message">
      <p>Error loading table state: {{ error.message || 'Unknown error' }}</p>
      <pre v-if="error.response && error.response.data">{{ error.response.data }}</pre>
    </div>

    <div v-if="tableState" class="table-state-display">
      <h2>Live Table State:</h2>
      <pre>{{ JSON.stringify(tableState, null, 2) }}</pre>
    </div>

    <div v-if="!loading && !tableState && !error" class="no-state">
      Could not load table state.
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import apiClient from '@/services/apiClient'; // Assuming apiClient is configured

const route = useRoute();
const id = ref(route.params.id); // Table ID from route params

const tableState = ref(null);
const loading = ref(true);
const error = ref(null);

const fetchTableState = async (tableId) => {
  if (!tableId) {
    error.value = { message: 'Table ID is missing.' };
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.get(`/poker/tables/${tableId}/state`);
    if (response.data && response.data.status && response.data.table_state) {
      tableState.value = response.data.table_state;
    } else {
      throw new Error('Invalid API response structure for table state.');
    }
  } catch (err) {
    console.error(`Failed to fetch table state for table ${tableId}:`, err);
    error.value = err;
    tableState.value = null; // Clear previous state on error
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchTableState(id.value);
});

// Watch for route param changes if the user navigates from one table to another
// e.g. using browser back/forward after viewing a table
watch(() => route.params.id, (newId) => {
  if (newId) {
    id.value = newId;
    fetchTableState(newId);
  }
});

</script>

<style scoped>
.poker-table-view {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
  font-family: Arial, sans-serif;
  color: #333;
}

h1 {
  text-align: center;
  margin-bottom: 25px;
  color: #2c3e50;
}

.loading, .no-state {
  text-align: center;
  font-size: 1.2em;
  color: #777;
  margin-top: 30px;
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

.table-state-display {
  margin-top: 20px;
  background-color: #f9f9f9;
  border: 1px solid #eee;
  border-radius: 5px;
  padding: 20px;
}

.table-state-display h2 {
  margin-top: 0;
  color: #007bff;
  margin-bottom: 10px;
}

.table-state-display pre {
  background-color: #fff;
  border: 1px solid #ddd;
  padding: 15px;
  border-radius: 4px;
  white-space: pre-wrap; /* Ensures long lines wrap */
  word-break: break-all; /* Ensures long strings without spaces wrap */
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  max-height: 500px; /* For very large states */
  overflow-y: auto;
}
</style>
