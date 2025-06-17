<template>
  <div class="poker-container">
    <!-- Game Header -->
    <div class="game-header">
      <h2>Texas Hold'em Poker</h2>
      <div class="table-info">
        <span>Table: {{ tableData?.name || 'Loading...' }}</span>
        <span>Stakes: ${{ tableData?.small_blind }}/${{ tableData?.big_blind }}</span>
      </div>
    </div>

    <!-- Phaser Game Container -->
    <div id="poker-phaser-container" class="phaser-container"></div>

    <!-- Game Controls -->
    <div class="game-controls">
      <div class="player-stats">
        <div class="stat-item">
          <label>Balance:</label>
          <span class="balance">${{ playerBalance }}</span>
        </div>
        <div class="stat-item">
          <label>Stack:</label>
          <span class="stack">${{ playerStack }}</span>
        </div>
        <div class="stat-item">
          <label>Position:</label>
          <span class="position">{{ playerPosition }}</span>
        </div>
      </div>

      <div class="table-controls">
        <button 
          @click="joinTable" 
          :disabled="!canJoinTable"
          class="join-btn"
        >
          {{ isSeated ? 'Leave Table' : 'Join Table' }}
        </button>
        
        <button 
          @click="sitOut" 
          :disabled="!isSeated"
          class="sit-out-btn"
        >
          {{ isSittingOut ? 'Sit In' : 'Sit Out' }}
        </button>

        <button 
          @click="showSettings"
          class="settings-btn"
        >
          Settings
        </button>
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="chat-panel" v-if="showChat">
      <div class="chat-header">
        <h4>Table Chat</h4>
        <button @click="toggleChat" class="close-chat">×</button>
      </div>
      <div class="chat-messages" ref="chatMessages">
        <div 
          v-for="message in chatMessages" 
          :key="message.id"
          class="chat-message"
          :class="{ 'own-message': message.isOwnMessage }"
        >
          <span class="username">{{ message.username }}:</span>
          <span class="text">{{ message.text }}</span>
        </div>
      </div>
      <div class="chat-input">
        <input 
          v-model="newChatMessage"
          @keyup.enter="sendChatMessage"
          placeholder="Type a message..."
          maxlength="200"
        />
        <button @click="sendChatMessage">Send</button>
      </div>
    </div>

    <!-- Game Status Overlay -->
    <div v-if="gameStatus" class="status-overlay">
      <div class="status-content">
        <h3>{{ gameStatus.title }}</h3>
        <p>{{ gameStatus.message }}</p>
        <div v-if="gameStatus.action" class="status-actions">
          <button @click="handleStatusAction">{{ gameStatus.action }}</button>
        </div>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>{{ loadingMessage }}</p>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, computed, nextTick } from 'vue'
import Phaser from 'phaser'
import EventBus from '@/event-bus'
import PokerBootScene from '@/phaser/scenes/PokerBootScene'
import PokerGameScene from '@/phaser/scenes/PokerGameScene'
import PokerUIScene from '@/phaser/scenes/PokerUIScene'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'

export default {
  name: 'Poker',
  props: {
    tableId: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const authStore = useAuthStore()
    const notificationStore = useNotificationStore()

    // Reactive state
    const game = ref(null)
    const isLoading = ref(true)
    const loadingMessage = ref('Connecting to table...')
    const tableData = ref(null)
    const gameState = ref(null)
    const playerData = ref(null)
    const isSeated = ref(false)
    const isSittingOut = ref(false)
    const showChat = ref(false)
    const chatMessages = ref([])
    const newChatMessage = ref('')
    const gameStatus = ref(null)

    // Computed properties
    const playerBalance = computed(() => authStore.user?.balance || 0)
    const playerStack = computed(() => playerData.value?.stack_sats || 0)
    const playerPosition = computed(() => playerData.value?.position || 'Observer')
    const canJoinTable = computed(() => !isSeated.value && playerBalance.value >= (tableData.value?.min_buyin || 100))

    // Phaser game configuration
    const phaserConfig = {
      type: Phaser.AUTO,
      width: 800,
      height: 600,
      parent: 'poker-phaser-container',
      backgroundColor: '#0d5016',
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH
      },
      physics: {
        default: 'arcade',
        arcade: {
          gravity: { y: 0 },
          debug: false
        }
      },
      scene: [PokerBootScene, PokerGameScene, PokerUIScene]
    }

    // Initialize Phaser game
    const initializeGame = async () => {
      try {
        loadingMessage.value = 'Loading game assets...'
        
        // Create Phaser game instance
        game.value = new Phaser.Game(phaserConfig)
        
        // Set up registry data
        game.value.registry.set('eventBus', EventBus)
        game.value.registry.set('tableId', props.tableId)
        game.value.registry.set('currentPlayer', authStore.user)
        
        // Set up event listeners
        setupEventListeners()
        
        // Load table data
        await loadTableData()
        
        isLoading.value = false
        
      } catch (error) {
        console.error('Failed to initialize poker game:', error)
        notificationStore.addNotification({
          type: 'error',
          message: 'Failed to load poker table'
        })
      }
    }

    // Load table data from API
    const loadTableData = async () => {
      try {
        loadingMessage.value = 'Loading table data...'
        
        const response = await fetch(`/api/poker/tables/${props.tableId}`, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        })
        
        if (!response.ok) {
          throw new Error('Failed to load table data')
        }
        
        const data = await response.json()
        tableData.value = data.table
        
        // Update game registry
        game.value.registry.set('tableData', data.table)
        game.value.registry.set('gameState', data.game_state)
        
        // Check if player is already seated
        if (data.game_state?.player_states) {
          const playerState = data.game_state.player_states.find(
            p => p.user_id === authStore.user.id
          )
          if (playerState) {
            isSeated.value = true
            playerData.value = playerState
            isSittingOut.value = playerState.is_sitting_out
          }
        }
        
      } catch (error) {
        console.error('Failed to load table data:', error)
        throw error
      }
    }

    // Set up event listeners
    const setupEventListeners = () => {
      // WebSocket connection for real-time updates
      setupWebSocket()
      
      // Phaser events
      EventBus.$on('pokerGameReady', handleGameReady)
      EventBus.$on('pokerPlayerAction', handlePlayerAction)
      EventBus.$on('pokerGameError', handleGameError)
    }

    // WebSocket connection for real-time game updates
    const setupWebSocket = () => {
      const wsUrl = `ws://localhost:8000/ws/poker/${props.tableId}?token=${authStore.token}`
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('Poker WebSocket connected')
        loadingMessage.value = 'Connected to table'
      }
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      }
      
      ws.onclose = () => {
        console.log('Poker WebSocket disconnected')
        // Attempt to reconnect
        setTimeout(setupWebSocket, 3000)
      }
      
      ws.onerror = (error) => {
        console.error('Poker WebSocket error:', error)
      }
    }

    // Handle WebSocket messages
    const handleWebSocketMessage = (data) => {
      switch (data.type) {
        case 'game_state_update':
          updateGameState(data.game_state)
          break
        case 'player_action':
          handlePlayerActionUpdate(data)
          break
        case 'hand_started':
          handleHandStarted(data)
          break
        case 'cards_dealt':
          handleCardsDealt(data)
          break
        case 'betting_round':
          handleBettingRound(data)
          break
        case 'hand_ended':
          handleHandEnded(data)
          break
        case 'chat_message':
          handleChatMessage(data)
          break
        case 'player_joined':
          handlePlayerJoined(data)
          break
        case 'player_left':
          handlePlayerLeft(data)
          break
        default:
          console.log('Unknown WebSocket message type:', data.type)
      }
    }

    // Update game state
    const updateGameState = (newGameState) => {
      gameState.value = newGameState
      
      // Update Phaser game
      if (game.value) {
        game.value.registry.set('gameState', newGameState)
        EventBus.$emit('pokerGameStateUpdate', newGameState)
      }
      
      // Update player data if seated
      if (isSeated.value && newGameState.player_states) {
        const playerState = newGameState.player_states.find(
          p => p.user_id === authStore.user.id
        )
        if (playerState) {
          playerData.value = playerState
        }
      }
    }

    // Handle player actions
    const handlePlayerAction = async (actionData) => {
      try {
        const response = await fetch(`/api/poker/tables/${props.tableId}/action`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authStore.token}`
          },
          body: JSON.stringify(actionData)
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Action failed')
        }
        
      } catch (error) {
        console.error('Player action failed:', error)
        notificationStore.addNotification({
          type: 'error',
          message: error.message
        })
      }
    }

    // Join/leave table
    const joinTable = async () => {
      if (isSeated.value) {
        // Leave table
        await leaveTable()
      } else {
        // Join table
        await joinTableRequest()
      }
    }

    const joinTableRequest = async () => {
      try {
        const response = await fetch(`/api/poker/tables/${props.tableId}/join`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authStore.token}`
          },
          body: JSON.stringify({
            buyin_amount: tableData.value?.min_buyin || 100
          })
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Failed to join table')
        }
        
        const data = await response.json()
        isSeated.value = true
        playerData.value = data.player_state
        
        notificationStore.addNotification({
          type: 'success',
          message: 'Joined table successfully'
        })
        
      } catch (error) {
        console.error('Failed to join table:', error)
        notificationStore.addNotification({
          type: 'error',
          message: error.message
        })
      }
    }

    const leaveTable = async () => {
      try {
        const response = await fetch(`/api/poker/tables/${props.tableId}/leave`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Failed to leave table')
        }
        
        isSeated.value = false
        playerData.value = null
        isSittingOut.value = false
        
        notificationStore.addNotification({
          type: 'info',
          message: 'Left table'
        })
        
      } catch (error) {
        console.error('Failed to leave table:', error)
        notificationStore.addNotification({
          type: 'error',
          message: error.message
        })
      }
    }

    // Sit out/sit in
    const sitOut = async () => {
      try {
        const action = isSittingOut.value ? 'sit_in' : 'sit_out'
        
        const response = await fetch(`/api/poker/tables/${props.tableId}/sit_out`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authStore.token}`
          },
          body: JSON.stringify({ action })
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || `Failed to ${action}`)
        }
        
        isSittingOut.value = !isSittingOut.value
        
      } catch (error) {
        console.error('Sit out/in failed:', error)
        notificationStore.addNotification({
          type: 'error',
          message: error.message
        })
      }
    }

    // Chat functionality
    const toggleChat = () => {
      showChat.value = !showChat.value
    }

    const sendChatMessage = async () => {
      if (!newChatMessage.value.trim()) return
      
      try {
        const response = await fetch(`/api/poker/tables/${props.tableId}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authStore.token}`
          },
          body: JSON.stringify({
            message: newChatMessage.value.trim()
          })
        })
        
        if (!response.ok) {
          throw new Error('Failed to send message')
        }
        
        newChatMessage.value = ''
        
      } catch (error) {
        console.error('Failed to send chat message:', error)
      }
    }

    const handleChatMessage = (data) => {
      chatMessages.value.push({
        id: Date.now() + Math.random(),
        username: data.username,
        text: data.message,
        isOwnMessage: data.user_id === authStore.user.id
      })
      
      // Auto-scroll to bottom
      nextTick(() => {
        const chatEl = this.$refs.chatMessages
        if (chatEl) {
          chatEl.scrollTop = chatEl.scrollHeight
        }
      })
    }

    // Game event handlers
    const handleGameReady = () => {
      console.log('Poker game ready')
    }

    const handlePlayerActionUpdate = (data) => {
      EventBus.$emit('pokerActionTaken', data)
    }

    const handleHandStarted = (data) => {
      EventBus.$emit('pokerHandStarted', data)
    }

    const handleCardsDealt = (data) => {
      EventBus.$emit('pokerCardsDealt', data)
    }

    const handleBettingRound = (data) => {
      EventBus.$emit('pokerBettingPhase', data)
    }

    const handleHandEnded = (data) => {
      EventBus.$emit('pokerHandEnded', data)
    }

    const handlePlayerJoined = (data) => {
      notificationStore.addNotification({
        type: 'info',
        message: `${data.username} joined the table`
      })
    }

    const handlePlayerLeft = (data) => {
      notificationStore.addNotification({
        type: 'info',
        message: `${data.username} left the table`
      })
    }

    const handleGameError = (error) => {
      notificationStore.addNotification({
        type: 'error',
        message: error.message || 'Game error occurred'
      })
    }

    // Settings
    const showSettings = () => {
      // Implement settings modal
      console.log('Show settings')
    }

    // Lifecycle hooks
    onMounted(() => {
      initializeGame()
    })

    onUnmounted(() => {
      // Clean up event listeners
      EventBus.$off('pokerGameReady', handleGameReady)
      EventBus.$off('pokerPlayerAction', handlePlayerAction)
      EventBus.$off('pokerGameError', handleGameError)
      
      // Destroy Phaser game
      if (game.value) {
        game.value.destroy(true)
      }
    })

    return {
      // Reactive state
      game,
      isLoading,
      loadingMessage,
      tableData,
      gameState,
      playerData,
      isSeated,
      isSittingOut,
      showChat,
      chatMessages,
      newChatMessage,
      gameStatus,
      
      // Computed
      playerBalance,
      playerStack,
      playerPosition,
      canJoinTable,
      
      // Methods
      joinTable,
      sitOut,
      toggleChat,
      sendChatMessage,
      showSettings
    }
  }
}
</script>

<style scoped>
.poker-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #0d5016 0%, #1a6b2a 100%);
  color: #ffffff;
}

.game-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 2px solid #ffd700;
}

.game-header h2 {
  margin: 0;
  color: #ffd700;
  font-size: 1.8rem;
}

.table-info {
  display: flex;
  gap: 2rem;
  font-size: 0.9rem;
}

.phaser-container {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #0d5016;
}

.game-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: rgba(0, 0, 0, 0.4);
  border-top: 1px solid #333;
}

.player-stats {
  display: flex;
  gap: 2rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-item label {
  font-size: 0.8rem;
  color: #ccc;
  margin-bottom: 0.25rem;
}

.balance {
  color: #4CAF50;
  font-weight: bold;
}

.stack {
  color: #2196F3;
  font-weight: bold;
}

.position {
  color: #ffd700;
  font-weight: bold;
}

.table-controls {
  display: flex;
  gap: 1rem;
}

.table-controls button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
}

.join-btn {
  background: #4CAF50;
  color: white;
}

.join-btn:hover:not(:disabled) {
  background: #45a049;
}

.sit-out-btn {
  background: #ff9800;
  color: white;
}

.sit-out-btn:hover:not(:disabled) {
  background: #e68900;
}

.settings-btn {
  background: #6c757d;
  color: white;
}

.settings-btn:hover {
  background: #5a6268;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-panel {
  position: fixed;
  top: 20%;
  right: 2rem;
  width: 300px;
  height: 400px;
  background: rgba(0, 0, 0, 0.9);
  border: 2px solid #ffd700;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  z-index: 1000;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  background: #ffd700;
  color: #000;
  border-radius: 6px 6px 0 0;
}

.chat-header h4 {
  margin: 0;
}

.close-chat {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #000;
}

.chat-messages {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
  font-size: 0.85rem;
}

.chat-message {
  margin-bottom: 0.5rem;
}

.chat-message .username {
  font-weight: bold;
  color: #ffd700;
}

.chat-message.own-message .username {
  color: #4CAF50;
}

.chat-input {
  display: flex;
  padding: 0.5rem;
  border-top: 1px solid #333;
}

.chat-input input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #333;
  background: #222;
  color: #fff;
  border-radius: 4px 0 0 4px;
}

.chat-input button {
  padding: 0.5rem 1rem;
  border: 1px solid #333;
  background: #ffd700;
  color: #000;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
}

.status-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}

.status-content {
  background: #1a6b2a;
  padding: 2rem;
  border-radius: 12px;
  border: 2px solid #ffd700;
  text-align: center;
  max-width: 400px;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 3000;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 5px solid #333;
  border-top: 5px solid #ffd700;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .game-header {
    flex-direction: column;
    gap: 1rem;
    text-align: center;
  }
  
  .game-controls {
    flex-direction: column;
    gap: 1rem;
  }
  
  .player-stats {
    justify-content: center;
  }
  
  .chat-panel {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    height: 100%;
    border-radius: 0;
  }
}
</style>
