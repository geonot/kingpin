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

    <div v-if="tableState" class="poker-table-container">
      <!-- Table Information Area -->
      <div class="table-info">
        <h2>{{ tableState.table_name }}</h2>
        <p>Blinds: {{ tableState.small_blind }} / {{ tableState.big_blind }}</p>
        <p>Pot: {{ tableState.current_hand_id ? (tableState.pot_size_sats || 0) : 'N/A' }}</p>
        <div class="community-cards">
          Community Cards:
          <span v-if="tableState.board_cards && tableState.board_cards.length > 0">
            <span v-for="card in tableState.board_cards" :key="card" class="card">{{ card }}</span>
          </span>
          <span v-else>N/A</span>
        </div>
      </div>

      <!-- Player Seats Area -->
      <div class="player-seats-area">
        <div v-for="seatNum in tableState.max_seats" :key="seatNum" class="seat">
          <div v-if="getPlayerAtSeat(seatNum)" class="player-info" :class="{ 'current-turn': isCurrentTurn(getPlayerAtSeat(seatNum).user_id) }">
            <p><strong>{{ getPlayerAtSeat(seatNum).username }}</strong> (Seat {{ seatNum }})</p>
            <p>Stack: {{ getPlayerAtSeat(seatNum).stack_sats }}</p>
            <p>Status: {{ getPlayerAtSeat(seatNum).last_action || 'Waiting' }}</p>
            <p class="hole-cards">
              Cards:
              <span v-if="getPlayerAtSeat(seatNum).user_id === loggedInUserId && getPlayerAtSeat(seatNum).hole_cards">
                <span v-for="card in getPlayerAtSeat(seatNum).hole_cards" :key="card" class="card">{{ card }}</span>
              </span>
              <span v-else-if="getPlayerAtSeat(seatNum).hole_cards">XX</span>
              <span v-else>N/A</span>
            </p>
            <p v-if="isDealer(seatNum)" class="dealer-chip">D</p>
          </div>
          <div v-else class="empty-seat">
            Seat {{ seatNum }} (Empty)
          </div>
        </div>
      </div>

      <!-- Action Buttons/Forms Area -->
      <div class="actions-area">
        <div class="join-table-form">
          <h3>Join Table</h3>
          <input type="number" v-model.number="joinSeatId" placeholder="Seat ID (1-{{ tableState.max_seats }})" />
          <input type="number" v-model.number="joinBuyInAmount" placeholder="Buy-in Amount" />
          <button @click="joinTable">Join Table</button>
        </div>
        <button @click="leaveTable">Leave Table</button>
        <button @click="startHand" v-if="canStartHand()" :disabled="actionInProgress">Start New Hand</button>

        <div v-if="isPlayerSeatedAndHandActive && isCurrentTurn(loggedInUserId)" class="in-game-actions">
          <h4>Your Turn:</h4>
          <button @click="performAction('fold')" :disabled="actionInProgress">Fold</button>
          <button @click="performAction('check')" :disabled="actionInProgress">Check</button>
          <button @click="performAction('call')" :disabled="actionInProgress">Call</button>
          <div class="bet-raise-action">
            <input type="number" v-model.number="betRaiseAmount" placeholder="Amount" :disabled="actionInProgress" />
            <button @click="performAction('bet', betRaiseAmount)" :disabled="actionInProgress || !betRaiseAmount">Bet</button>
            <button @click="performAction('raise', betRaiseAmount)" :disabled="actionInProgress || !betRaiseAmount">Raise</button>
          </div>
        </div>
        <p v-if="actionMessage" :class="{ 'action-error': actionError, 'action-success': !actionError }">{{ actionMessage }}</p>
      </div>

      <!-- Hand History Area -->
      <div class="hand-history-area" v-if="tableState && tableState.hand_history_preview && tableState.hand_history_preview.length > 0">
        <h3>Recent Hand History:</h3>
        <ul>
          <li v-for="(event, index) in tableState.hand_history_preview" :key="index">
            {{ formatHandHistoryEvent(event) }}
          </li>
        </ul>
      </div>
    </div>

    <div v-if="!loading && !tableState && !error" class="no-state">
      Could not load table state or table does not exist.
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { useRoute } from 'vue-router';
import api from '@/services/api'; // Use the existing api service

const route = useRoute();
const id = ref(route.params.id); // Table ID from route params

const tableState = ref(null);
const loading = ref(true);
const error = ref(null);

// Placeholder for logged-in user ID (replace with actual store/auth logic)
const loggedInUserId = ref(1); // TODO: Replace with actual user ID from auth store

const joinSeatId = ref(null);
const joinBuyInAmount = ref(null);
const betRaiseAmount = ref(null);

const actionInProgress = ref(false);
const actionMessage = ref('');
const actionError = ref(false);

const fetchTableState = async (tableId) => {
  if (!tableId) {
    error.value = { message: 'Table ID is missing.' };
    loading.value = false;
    return;
  }
  loading.value = true; // General loading for page/state refresh
  // error.value = null; // Keep previous general error if action fails
  try {
    const response = await api.get(`/poker/tables/${tableId}/state`);
    tableState.value = response.data;
  } catch (err) {
    console.error(`Failed to fetch table state for table ${tableId}:`, err);
    error.value = err; // This is for general table state loading errors
    // tableState.value = null; // Don't clear if previous state was valid and this is just a refresh failing
  } finally {
    loading.value = false;
  }
};

const getPlayerAtSeat = (seatNum) => {
  if (tableState.value && tableState.value.player_states) {
    return tableState.value.player_states.find(p => p.seat_id === seatNum);
  }
  return null;
};

const isDealer = (seatNum) => {
  return tableState.value && tableState.value.current_dealer_seat_id === seatNum;
};

const isCurrentTurn = (userId) => {
  return tableState.value && tableState.value.current_hand_id && tableState.value.current_turn_user_id === userId;
};

const isPlayerSeated = computed(() => {
  if (!tableState.value || !tableState.value.player_states) return false;
  return tableState.value.player_states.some(p => p.user_id === loggedInUserId.value);
});

const isPlayerSeatedAndHandActive = computed(() => {
  return isPlayerSeated.value && tableState.value && tableState.value.current_hand_id;
});


const handleApiResponse = async (promise, successMessage) => {
  actionInProgress.value = true;
  actionMessage.value = '';
  actionError.value = false;
  try {
    const response = await promise;
    actionMessage.value = response.data.message || successMessage || 'Action successful!';
    await fetchTableState(id.value); // Refresh state
    if (response.data.game_flow) { // Log game flow if present
        console.log("Game flow response:", response.data.game_flow);
    }
  } catch (err) {
    console.error('API Action Error:', err.response || err.message);
    actionMessage.value = err.response?.data?.error || err.response?.data?.message || err.message || 'An error occurred.';
    actionError.value = true;
    // No need to fetchTableState here as the primary action failed.
  } finally {
    actionInProgress.value = false;
  }
};

const joinTable = async () => {
  if (joinSeatId.value === null || joinBuyInAmount.value === null) {
    actionMessage.value = "Seat ID and Buy-in Amount are required.";
    actionError.value = true;
    return;
  }
  if (joinBuyInAmount.value <= 0) {
    actionMessage.value = "Buy-in amount must be positive.";
    actionError.value = true;
    return;
  }
  await handleApiResponse(
    api.post(`/poker/tables/${id.value}/join`, { seat_id: joinSeatId.value, buy_in_amount: joinBuyInAmount.value }),
    'Successfully joined table.'
  );
  joinSeatId.value = null;
  joinBuyInAmount.value = null;
};

const leaveTable = async () => {
  await handleApiResponse(
    api.post(`/poker/tables/${id.value}/leave`),
    'Successfully left table.'
  );
};

const startHand = async () => {
  await handleApiResponse(
    api.post(`/poker/tables/${id.value}/start_hand`),
    'New hand started.'
  );
};

const performAction = async (actionType, amount = null) => {
  if (!tableState.value || !tableState.value.current_hand_id) {
    actionMessage.value = "No active hand to perform action on.";
    actionError.value = true;
    return;
  }
  const payload = { action_type: actionType };
  if (amount !== null && (actionType === 'bet' || actionType === 'raise')) {
    if (amount <= 0) {
        actionMessage.value = "Bet/Raise amount must be positive.";
        actionError.value = true;
        return;
    }
    payload.amount = amount;
  }

  await handleApiResponse(
    api.post(`/poker/tables/${id.value}/hands/${tableState.value.current_hand_id}/action`, payload),
    `Action ${actionType} performed.`
  );
  betRaiseAmount.value = null; // Clear input after action
};


const canStartHand = () => {
  if (!tableState.value || !tableState.value.player_states || !isPlayerSeated.value) return false;
  // Hand status might be on tableState.value.hand_status or nested in current_hand_details.status
  // For now, assume if current_hand_id is null, we can start. Or if status is completed/showdown.
  const handInactive = !tableState.value.current_hand_id ||
                       (tableState.value.current_hand_details && ['completed', 'showdown'].includes(tableState.value.current_hand_details.status));
  return isPlayerSeated.value && handInactive;
};

const formatHandHistoryEvent = (event) => {
  if (!event || !event.action) return "Unknown event";
  let details = "";
  if (event.amount) details += ` Amount: ${event.amount}`;
  if (event.added_to_pot) details += ` (Added: ${event.added_to_pot})`;
  if (event.cards) details += ` Cards: ${event.cards.join(', ')}`;
  if (event.winning_hand) details += ` Hand: ${event.winning_hand}`;

  const player = event.user_id ? (getPlayerAtSeat(event.seat_id)?.username || `User ${event.user_id}`) : '';

  return `[${new Date(event.timestamp).toLocaleTimeString()}] ${player ? player + ' ' : ''}${event.action.replace(/_/g, ' ')}${details}`;
};


onMounted(() => {
  fetchTableState(id.value);
  // setInterval(() => {
  //   if (tableState.value && tableState.value.current_hand_id && !isCurrentTurn(loggedInUserId.value) && !actionInProgress.value) {
  //     fetchTableState(id.value);
  //   }
  // }, 5000); // Poll if hand active, not your turn, and no action in progress
});

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
  max-width: 1200px;
  margin: 0 auto;
  font-family: Arial, sans-serif;
  @apply text-gray-900 dark:text-gray-100;
}

h1 {
  text-align: center;
  margin-bottom: 25px;
  @apply text-gray-800 dark:text-gray-200;
}

.loading, .no-state {
  text-align: center;
  font-size: 1.2em;
  @apply text-gray-600 dark:text-gray-400;
  margin-top: 30px;
}

.error-message {
  @apply bg-red-50 dark:bg-red-900 text-red-800 dark:text-red-200 border border-red-300 dark:border-red-600;
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
  @apply bg-red-100 dark:bg-red-800;
  padding: 10px;
  border-radius: 3px;
}

.table-state-display {
  margin-top: 20px;
  @apply bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-600;
  border-radius: 5px;
  padding: 20px;
}

.table-state-display h2 {
  margin-top: 0;
  @apply text-blue-600 dark:text-blue-400;
  margin-bottom: 10px;
}

.table-state-display pre {
  @apply bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600;
  padding: 15px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  max-height: 500px;
  overflow-y: auto;
}

.poker-table-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.table-info {
  @apply bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700;
  padding: 15px;
  border-radius: 8px;
  width: 100%;
  max-width: 600px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.table-info h2 {
  margin-top: 0;
  @apply text-blue-700 dark:text-blue-300;
}

.community-cards {
  margin-top: 10px;
  padding: 10px;
  @apply bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600;
  border-radius: 4px;
  text-align: center;
}

.card {
  display: inline-block;
  padding: 5px 10px;
  @apply border border-gray-900 dark:border-gray-100 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100;
  border-radius: 4px;
  margin: 0 3px;
  font-weight: bold;
  min-width: 30px;
  text-align: center;
}

.player-seats-area {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
  width: 100%;
  padding: 10px;
  @apply bg-gray-100 dark:bg-gray-800;
  border-radius: 8px;
}

.seat {
  @apply border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700;
  border-radius: 6px;
  padding: 10px;
  min-height: 120px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.player-info {
  position: relative;
}
.player-info strong {
  @apply text-blue-600 dark:text-blue-400;
}
.player-info p {
  margin: 4px 0;
  font-size: 0.9em;
}
.hole-cards .card {
  @apply bg-gray-100 dark:bg-gray-600 text-gray-900 dark:text-gray-100;
}

.empty-seat {
  @apply text-gray-500 dark:text-gray-400;
  text-align: center;
  padding-top: 40px;
}

.dealer-chip {
  position: absolute;
  top: -5px;
  right: -5px;
  @apply bg-yellow-400 text-gray-900 border border-yellow-500;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.8em;
}

.current-turn {
  @apply border-2 border-green-500 dark:border-green-400;
  box-shadow: 0 0 10px rgba(34, 197, 94, 0.5);
}

.actions-area {
  margin-top: 20px;
  padding: 15px;
  @apply bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-600;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  width: 100%;
  max-width: 400px;
}
.join-table-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 15px;
}
.actions-area > button {
  margin-bottom: 10px;
}

.join-table-form input[type="number"],
.join-table-form button,
.actions-area > button,
.in-game-actions button,
.in-game-actions input[type="number"] {
  padding: 10px;
  border-radius: 4px;
  @apply border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100;
  font-size: 1em;
}
.join-table-form button,
.actions-area > button,
.in-game-actions button {
  @apply bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white dark:text-white border border-blue-600 dark:border-blue-500;
  cursor: pointer;
  transition: background-color 0.2s;
}
.in-game-actions button:disabled,
.actions-area > button:disabled {
  @apply bg-gray-400 dark:bg-gray-600 text-gray-700 dark:text-gray-400 border-gray-400 dark:border-gray-600;
  cursor: not-allowed;
}

.in-game-actions {
  @apply border-t border-gray-300 dark:border-gray-600;
  margin-top: 15px;
  padding-top: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.in-game-actions h4{
  margin:0 0 5px 0;
  text-align: center;
}
.bet-raise-action {
  display: flex;
  gap: 5px;
  align-items: center;
}
.bet-raise-action input[type="number"] {
  flex-grow: 1;
}

.action-message {
  margin-top:10px;
  padding: 8px;
  border-radius: 4px;
  text-align: center;
}
.action-success {
  @apply bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 border border-green-300 dark:border-green-600;
}
.action-error {
  @apply bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 border border-red-300 dark:border-red-600;
}

.hand-history-area {
  margin-top: 20px;
  padding: 15px;
  @apply bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-600;
  border-radius: 8px;
  width: 100%;
  max-width: 600px;
}
.hand-history-area h3 {
  margin-top: 0;
  @apply text-gray-900 dark:text-gray-100;
}
.hand-history-area ul {
  list-style-type: none;
  padding-left: 0;
  max-height: 200px;
  overflow-y: auto;
  font-size: 0.85em;
}
.hand-history-area li {
  padding: 3px 0;
  @apply border-b border-dashed border-gray-200 dark:border-gray-600;
}
.hand-history-area li:last-child {
  border-bottom: none;
}
</style>
