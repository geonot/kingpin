<template>
  <div class="astrominerx-page container mx-auto p-4 flex flex-col lg:flex-row gap-6 text-white">

    <!-- Left Column: Controls & Post-Game Resource Display -->
    <div class="lg:w-1/3 order-2 lg:order-1 space-y-6">
      <BettingControls
        :current-balance="userBalance" <!-- Changed from currentBalance to userBalance -->
        :is-expedition-active="isExpeditionActive"
        :min-bet="minBet"
        :max-bet="maxBet"
        :default-bet="defaultBet"
        @launch-expedition="handleLaunchExpedition"
        class="bg-gray-700 p-4 rounded-xl shadow-2xl"
      />
      <ResourceDisplay
        v-if="!isExpeditionActive && (currentExpeditionStatus === 'completed' || currentExpeditionStatus === 'aborted')"
        :collected-resources="collectedResourcesList"
        :total-value="totalCollectedValue"
        class="bg-gray-700 p-4 rounded-xl shadow-2xl"
      />
       <div v-if="isExpeditionActive || currentExpeditionStatus === 'loading'" class="mt-4 p-4 bg-gray-700 rounded-xl shadow-2xl">
        <h3 class="text-lg font-semibold text-yellow-400 mb-2">Expedition Log</h3>
        <ul class="text-sm text-gray-300 space-y-1 max-h-48 overflow-y-auto custom-scrollbar">
          <li v-for="(log, index) in expeditionGameMessages" :key="index" :class="getLogMessageClass(log)">
            {{ log.text || log }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Right Column: Game HUD & Phaser Canvas -->
    <div class="lg:w-2/3 order-1 lg:order-2 space-y-6">
      <GameHUD
        :time-left="expeditionTimeLeft"
        :current-haul-value="currentExpeditionHaul"
        :game-messages="expeditionGameMessages"
        :is-expedition-active="isExpeditionActive"
        :expedition-status="currentExpeditionStatus"
        class="sticky top-20 z-10"
      />
      <div :id="phaserGameContainerId" class="bg-black border-2 border-yellow-500 text-white aspect-[16/10] rounded-xl shadow-2xl flex items-center justify-center relative overflow-hidden">
        <div v-if="!phaserGameInitialized && !isExpeditionActive" class="absolute inset-0 flex flex-col items-center justify-center p-8 text-center">
            <p class="text-2xl font-bold mb-4 text-yellow-400">AstroMiner X</p>
            <p class="text-gray-300 mb-6" v-if="currentExpeditionStatus === 'idle'">Prepare your expedition and launch into the asteroid belt to find valuable resources!</p>
            <p class="text-gray-300 mb-6" v-if="currentExpeditionStatus === 'completed'">Expedition complete! Check your haul in the Resource Display.</p>
            <p class="text-gray-300 mb-6" v-if="currentExpeditionStatus === 'aborted'">Expedition aborted. Resources collected (if any) are shown.</p>
            <p class="text-gray-300 mb-6" v-if="currentExpeditionStatus === 'error_launch' || currentExpeditionStatus === 'error_collecting' || currentExpeditionStatus === 'error_scan'">An error occurred. Please try again or contact support.</p>
        </div>
         <div v-if="currentExpeditionStatus === 'loading'" class="absolute inset-0 flex flex-col items-center justify-center p-8 text-center">
            <p class="text-xl font-semibold text-yellow-300 animate-pulse">Initializing Subspace Jump...</p>
            <p class="text-gray-400">Preparing asteroid field.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Phaser from 'phaser';
import AstroMinerXScene from '@/phaser/scenes/AstroMinerXScene';

import BettingControls from '@/components/astrominerx/BettingControls.vue';
import ResourceDisplay from '@/components/astrominerx/ResourceDisplay.vue';
import GameHUD from '@/components/astrominerx/GameHUD.vue';
import apiService from '@/services/api';
import { mapGetters, mapActions } from 'vuex';

export default {
  name: 'AstroMinerXPage',
  components: {
    BettingControls,
    ResourceDisplay,
    GameHUD,
  },
  data() {
    return {
      isExpeditionActive: false,
      minBet: 50,
      maxBet: 2000,
      defaultBet: 100,
      collectedResourcesList: [],
      totalCollectedValue: 0,
      expeditionTimeLeft: 0,    // in seconds
      expeditionTimerInterval: null,
      currentExpeditionHaul: 0,
      expeditionGameMessages: [],
      currentExpeditionStatus: "idle", // idle, loading, active, completed, aborted, error_launch, error_scan, error_collecting

      currentExpeditionId: null,

      phaserGame: null,
      phaserGameContainerId: 'phaser-astrominerx-container',
      phaserGameInitialized: false,
      phaserSceneInstance: null,
    };
  },
  computed: {
    ...mapGetters({
      currentUser: 'currentUser',
    }),
    userBalance() {
        return this.currentUser ? this.currentUser.balance : 0;
    }
  },
  methods: {
    ...mapActions({
      fetchUserProfileVuex: 'fetchUserProfile',
    }),

    async handleLaunchExpedition(betAmount) {
      if (this.userBalance < betAmount) {
        this.expeditionGameMessages.unshift({type: 'error', text: "Not enough balance to launch!"});
        this.currentExpeditionStatus = "idle";
        return;
      }

      console.log('AstroMinerXPage: Launch Expedition with bet:', betAmount);
      this.currentExpeditionStatus = "loading";
      this.isExpeditionActive = false;
      this.expeditionGameMessages = [{ type: 'info', text: `Launching expedition with ${betAmount} sats...`}];
      this.currentExpeditionHaul = 0;
      this.collectedResourcesList = [];
      this.totalCollectedValue = 0;
      this.phaserGameInitialized = false;

      try {
        const response = await apiService.launchAstroMinerXExpedition({ bet_amount: betAmount });
        if (response.data.status) {
          const expeditionData = response.data.expedition;
          this.currentExpeditionId = expeditionData.id;
          await this.fetchUserProfileVuex();

          this.isExpeditionActive = true;
          this.currentExpeditionStatus = "active";
          // Backend should ideally provide time_limit for consistency
          this.expeditionTimeLeft = response.data.expedition.time_limit || 120;
          this.startExpeditionTimer();
          this.expeditionGameMessages.unshift({ type: 'success', text: `Expedition ${this.currentExpeditionId} launched! Asteroid field generated.` });

          this.initializeOrRestartPhaserScene({
            expeditionId: this.currentExpeditionId,
            initialAsteroids: response.data.initial_asteroids || [],
            vueComponent: this
          });
        } else {
          this.handleApiError(response.data.status_message || "Launch failed due to an unknown server issue.", "error_launch");
          await this.fetchUserProfileVuex();
        }
      } catch (error) {
        this.handleApiError(error, "error_launch");
        await this.fetchUserProfileVuex();
      }
    },

    startExpeditionTimer() {
      if (this.expeditionTimerInterval) {
        clearInterval(this.expeditionTimerInterval);
      }
      this.expeditionTimerInterval = setInterval(() => {
        if (this.expeditionTimeLeft > 0) {
          this.expeditionTimeLeft--;
        } else {
          if(this.isExpeditionActive) this.completeExpedition("Time's up!");
        }
      }, 1000);
    },

    async handleScanAsteroid(asteroidId) {
        if (!this.isExpeditionActive || !this.currentExpeditionId) {
            this.expeditionGameMessages.unshift({type: 'warning', text: "Cannot scan: No active expedition."});
            return Promise.reject(new Error("No active expedition"));
        }
        this.expeditionGameMessages.unshift({type: 'info', text: `Scanning asteroid ${asteroidId}...`});
        try {
            const response = await apiService.scanAstroMinerXAsteroid({
                expedition_id: this.currentExpeditionId,
                asteroid_id: asteroidId
            });

            if (response.data.status) {
                const scanResultData = response.data.scan_result;
                let message = `Scanned ${scanResultData.asteroid_type}.`;
                if (scanResultData.is_hazard) {
                    message += " It's a HAZARD!";
                } else if (scanResultData.is_empty) {
                    message += " It's empty.";
                } else if (scanResultData.value && scanResultData.value > 0) {
                    message += ` Value: ${scanResultData.value} sats.`;
                    this.currentExpeditionHaul += scanResultData.value;
                    // This list is for the ResourceDisplay if shown post-game.
                    // The actual collected resources are confirmed by the /collect endpoint.
                    // this.collectedResourcesList.push({ name: scanResultData.asteroid_type, value: scanResultData.value });
                } else {
                    message += " Nothing of value found.";
                }
                this.expeditionGameMessages.unshift({type: 'scan_result', text: message});

                if (response.data.user_balance !== undefined) {
                     await this.fetchUserProfileVuex();
                }
                if (response.data.event_details) {
                    this.expeditionGameMessages.unshift({type: 'warning', text: `EVENT: ${response.data.event_details.message}`});
                }
                return response.data; // Return API response for Phaser
            } else {
                this.handleApiError(response.data.status_message || `Scan failed for asteroid ${asteroidId}.`, "error_scan");
                return Promise.reject(new Error(response.data.status_message || `Scan failed for asteroid ${asteroidId}.`));
            }
        } catch (error) {
            this.handleApiError(error, "error_scan");
            return Promise.reject(error);
        }
    },

    async completeExpedition(reason = "Collection initiated.") {
      if (!this.currentExpeditionId) {
          this.expeditionGameMessages.unshift({type: 'info', text: "No active expedition to complete."});
          this.isExpeditionActive = false;
          this.currentExpeditionStatus = "idle";
          if (this.expeditionTimerInterval) clearInterval(this.expeditionTimerInterval);
          return;
      }

      if (this.expeditionTimerInterval) clearInterval(this.expeditionTimerInterval);
      this.expeditionTimerInterval = null;

      const prevStatus = this.currentExpeditionStatus;
      this.isExpeditionActive = false; // Stop further game interactions
      this.currentExpeditionStatus = "collecting";
      this.expeditionGameMessages.unshift({ type: 'info', text: `Ending expedition (Reason: ${reason}). Calculating results...` });

      try {
        const response = await apiService.collectAstroMinerXResources({ expedition_id: this.currentExpeditionId });
        if (response.data.status) {
          const summary = response.data.expedition_summary;
          this.totalCollectedValue = summary.total_value_collected;
          this.collectedResourcesList = response.data.collected_resources_detail || [];
          await this.fetchUserProfileVuex();

          this.currentExpeditionStatus = "completed";
          this.expeditionGameMessages.unshift({ type: 'success', text: `Expedition ${summary.id} Complete! Total Value: ${this.totalCollectedValue} sats.` });
        } else {
          this.handleApiError(response.data.status_message || "Resource collection failed.", "error_collecting");
          this.currentExpeditionStatus = prevStatus === "aborted" ? "aborted" : "error_collecting"; // Revert to aborted if it was, else error
        }
      } catch (error) {
        this.handleApiError(error, "error_collecting");
         this.currentExpeditionStatus = prevStatus === "aborted" ? "aborted" : "error_collecting";
      } finally {
        // isExpeditionActive is already false
        if (this.phaserSceneInstance) {
           this.phaserSceneInstance.endExpedition();
        }
        // Do not nullify currentExpeditionId here if you want to show results for it
      }
    },

    initializePhaserGame() {
      if (this.phaserGame) {
        console.log("AstroMinerXPage: Destroying existing Phaser game instance for reinitialization.");
        this.phaserGame.destroy(true);
        this.phaserGame = null;
        this.phaserSceneInstance = null;
      }

      console.log("AstroMinerXPage: Initializing new Phaser game instance.");
      const gameConfig = {
        type: Phaser.AUTO,
        width: 800,
        height: 500,
        parent: this.phaserGameContainerId,
        physics: { default: 'arcade', arcade: { debug: false }},
        scene: [AstroMinerXScene],
        backgroundColor: '#000010', // Dark space background
      };

      this.phaserGame = new Phaser.Game(gameConfig);
      //this.phaserGameInitialized = true; // Set by phaserSceneReady callback
      console.log("AstroMinerXPage: Phaser game instance created.");
    },

    initializeOrRestartPhaserScene(expeditionLaunchData) {
        if (!this.phaserGame || !this.phaserGame.isRunning) {
            this.initializePhaserGame();
        }

        console.log("AstroMinerXPage: Starting/Restarting AstroMinerXScene with data:", expeditionLaunchData);

        if (this.phaserGame.scene.isActive('AstroMinerXScene')) {
            this.phaserGame.scene.stop('AstroMinerXScene');
        }
        this.phaserGame.scene.start('AstroMinerXScene', expeditionLaunchData);
        // phaserSceneReady will set this.phaserGameInitialized = true;
    },

    phaserSceneReady(sceneInstance) {
        console.log("AstroMinerXPage: Phaser scene is ready.", sceneInstance);
        this.phaserSceneInstance = sceneInstance;
        this.phaserGameInitialized = true;
    },

    handleApiError(error, statusOnError = "error") {
      let message = "An unexpected error occurred.";
      if (error && error.isStructuredError) {
          message = error.message || "API Error";
          if(error.details) console.error("AstroMinerXPage API Error Details:", error.details);
      } else if (error && error.response && error.response.data) {
          message = error.response.data.status_message || error.response.data.message || (error.response.data.error ? error.response.data.error.message : message);
      } else if (error && error.message) {
          message = error.message;
      }
      this.expeditionGameMessages.unshift({ type: 'error', text: message });
      this.currentExpeditionStatus = statusOnError;
      this.isExpeditionActive = false;
      if(this.expeditionTimerInterval) clearInterval(this.expeditionTimerInterval);
      console.error("AstroMinerXPage handleApiError:", error);
    },

    getLogMessageClass(log) {
      if (typeof log === 'object' && log.type) {
        switch (log.type) {
          case 'error': return 'text-red-400';
          case 'warning': return 'text-yellow-300';
          case 'info': return 'text-blue-300';
          case 'success': return 'text-green-400';
          case 'scan_result': return 'text-purple-300';
          case 'system': return 'text-gray-400 italic';
          default: return 'text-gray-300';
        }
      }
      return 'text-gray-300';
    }
  },
  async mounted() {
    await this.fetchUserProfileVuex();
    this.expeditionGameMessages.push({ type: 'system', text: 'AstroMiner X Online. Systems Nominal.' });
    this.initializePhaserGame();
  },
  beforeUnmount() {
    if (this.expeditionTimerInterval) {
      clearInterval(this.expeditionTimerInterval);
    }
    if (this.phaserGame) {
      console.log("AstroMinerXPage: Destroying Phaser game instance in beforeUnmount.");
      this.phaserGame.destroy(true);
      this.phaserGame = null;
      this.phaserSceneInstance = null;
      this.phaserGameInitialized = false;
    }
  },
};
</script>

<style scoped>
.astrominerx-page {
  min-height: calc(100vh - 80px); /* Adjust 80px based on header/footer height */
  background: linear-gradient(to bottom, #1f2937, #111827); /* Dark blue/gray gradient */
}

/* Custom scrollbar for internal lists if needed */
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #374151; /* bg-gray-700 */
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #f59e0b; /* bg-yellow-500 */
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #d97706; /* bg-yellow-600 */
}

/* Placeholder for game elements if not using Phaser for everything */
.asteroid {
    width: 30px; height: 30px; background-color: gray; border-radius: 50%;
    position: absolute; /* Example positioning */
    box-shadow: 0 0 5px #fff, 0 0 10px #fff, 0 0 15px #ffc107, 0 0 20px #ffc107;
}
</style>
