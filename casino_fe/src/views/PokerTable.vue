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
import apiClient from '@/services/apiClient'; // Assuming apiClient is configured

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
    const response = await apiClient.get(`/poker/tables/${tableId}/state`);
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
    apiClient.post(`/poker/tables/${id.value}/join`, { seat_id: joinSeatId.value, buy_in_amount: joinBuyInAmount.value }),
    'Successfully joined table.'
  );
  joinSeatId.value = null;
  joinBuyInAmount.value = null;
};

const leaveTable = async () => {
  await handleApiResponse(
    apiClient.post(`/poker/tables/${id.value}/leave`),
    'Successfully left table.'
  );
};

const startHand = async () => {
  await handleApiResponse(
    apiClient.post(`/poker/tables/${id.value}/start_hand`),
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
    apiClient.post(`/poker/tables/${id.value}/hands/${tableState.value.current_hand_id}/action`, payload),
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
  max-width: 1200px; /* Increased max-width for better layout */
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

.poker-table-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.table-info {
  background-color: #e9f5ff;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #b3d7ff;
  width: 100%;
  max-width: 600px; /* Centered info box */
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.table-info h2 {
  margin-top: 0;
  color: #0056b3;
}

.community-cards {
  margin-top: 10px;
  padding: 10px;
  background-color: #fff;
  border: 1px solid #ccc;
  border-radius: 4px;
  text-align: center;
}

.card {
  display: inline-block;
  padding: 5px 10px;
  border: 1px solid #333;
  background-color: white;
  border-radius: 4px;
  margin: 0 3px;
  font-weight: bold;
  min-width: 30px;
  text-align: center;
}

.player-seats-area {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); /* Responsive grid */
  gap: 15px;
  width: 100%;
  padding: 10px;
  background-color: #f0f0f0; /* Light grey background for seats area */
  border-radius: 8px;
}

.seat {
  border: 1px solid #ccc;
  border-radius: 6px;
  padding: 10px;
  background-color: #fff;
  min-height: 120px; /* Ensure seats have some height */
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.player-info {
  position: relative; /* For dealer chip positioning */
}
.player-info strong {
  color: #007bff;
}
.player-info p {
  margin: 4px 0;
  font-size: 0.9em;
}
.hole-cards .card {
  background-color: #f8f9fa;
  color: #212529;
}

.empty-seat {
  color: #888;
  text-align: center;
  padding-top: 40px; /* Center text a bit */
}

.dealer-chip {
  position: absolute;
  top: -5px;
  right: -5px;
  background-color: #ffc107; /* Yellow for dealer chip */
  color: #333;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.8em;
  border: 1px solid #e0a800;
}

.current-turn {
  border: 2px solid #28a745; /* Green border for current turn */
  box-shadow: 0 0 10px rgba(40, 167, 69, 0.5);
}

.actions-area {
  margin-top: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  display: flex;
  flex-direction: column; /* Stack form and buttons */
  gap: 15px; /* Space between elements in actions area */
  width: 100%;
  max-width: 400px; /* Centered actions box */
}
.join-table-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 15px;
}
.actions-area > button {
  margin-bottom: 10px; /* Space below Leave and Start Hand buttons */
}

.join-table-form input[type="number"],
.join-table-form button,
.actions-area > button,
.in-game-actions button,
.in-game-actions input[type="number"] {
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #ced4da;
  font-size: 1em;
}
.join-table-form button,
.actions-area > button,
.in-game-actions button {
  background-color: #007bff;
  color: white;
  cursor: pointer;
  transition: background-color 0.2s;
}
.join-table-form button:hover,
.actions-area > button:hover,
.in-game-actions button:hover {
  background-color: #0056b3;
}
.in-game-actions button:disabled,
.actions-area > button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}


.in-game-actions {
  border-top: 1px solid #ccc;
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
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}
.action-error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.hand-history-area {
  margin-top: 20px;
  padding: 15px;
  background-color: #fdfdfd;
  border: 1px solid #eee;
  border-radius: 8px;
  width: 100%;
  max-width: 600px; /* Or align with table-info */
}
.hand-history-area h3 {
  margin-top: 0;
  color: #333;
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
  border-bottom: 1px dashed #eee;
}
.hand-history-area li:last-child {
  border-bottom: none;
}


/* Basic attempt at circular/oval layout for more seats - very simplified */
/* This would need significant work for a true circle, especially dynamic seat counts */
/* For more than 4-6 seats, a grid or simpler flex row layout is more practical without complex JS positioning */
/*
.player-seats-area.seats-6 .seat:nth-child(1) { grid-column: 2 / 3; grid-row: 1 / 2; }
.player-seats-area.seats-6 .seat:nth-child(2) { grid-column: 3 / 4; grid-row: 2 / 3; }
.player-seats-area.seats-6 .seat:nth-child(3) { grid-column: 2 / 3; grid-row: 3 / 4; }
.player-seats-area.seats-6 .seat:nth-child(4) { grid-column: 1 / 2; grid-row: 3 / 4; }
.player-seats-area.seats-6 .seat:nth-child(5) { grid-column: 0 / 1; grid-row: 2 / 3; }
.player-seats-area.seats-6 .seat:nth-child(6) { grid-column: 1 / 2; grid-row: 1 / 2; }
*/

</style>
