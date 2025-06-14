<template>
  <div class="crystal-garden-page-container">
    <h1 v-if="isLoading" class="loading-text">Loading Crystal Garden...</h1>
    <div v-if="!isLoading && !gameReady" class="error-text">
      <p>Error loading Crystal Garden.</p>
      <p>Please ensure your browser supports WebGL or try refreshing the page.</p>
    </div>
    <div id="phaser-crystal-garden-game" ref="gameContainer" :style="{ width: gameWidth + 'px', height: gameHeight + 'px' }"></div>
    <!-- You can add other UI elements here, outside the Phaser canvas -->
  </div>
</template>

<script>
import Phaser from 'phaser';
import CrystalGardenScene from '@/phaser/scenes/crystal_garden_scene'; // Path based on @ alias for src

// Holder for the Phaser game instance
let gameInstance = null;

// Function to launch the Crystal Garden game
function launchCrystalGarden(containerId, width, height) {
  const gameConfig = {
    type: Phaser.AUTO,
    width: width,
    height: height,
    parent: containerId,
    backgroundColor: '#1A431A', // A slightly different green for the page background if needed
    scene: [CrystalGardenScene], // Only the Crystal Garden scene for this instance
    scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
    },
    render: {
        antialias: true,
        pixelArt: false, // Assuming non-pixel art assets for garden
    }
  };
  return new Phaser.Game(gameConfig);
}

export default {
  name: 'CrystalGardenPage',
  data() {
    return {
      isLoading: true,
      gameReady: false,
      gameWidth: 1024, // Desired game width
      gameHeight: 768, // Desired game height
      // featureIsEnabled: false, // Will be checked by router or parent component normally
    };
  },
  // beforeRouteEnter(to, from, next) {
  //   // Example: Check feature flag before entering route (if using Vuex store or global state)
  //   // if (!store.getters.isFeatureEnabled('CRYSTAL_GARDEN_ENABLED')) {
  //   //   next({ name: 'NotFound' }); // Or some 'FeatureDisabled' page
  //   // } else {
  //   //   next();
  //   // }
  //   // For this subtask, assuming flag check is handled elsewhere or by link visibility.
  //   next();
  // },
  mounted() {
    // Ensure the DOM element is available
    this.$nextTick(() => {
      const container = this.$refs.gameContainer;
      if (container) {
        try {
            console.log("CrystalGardenPage: Mounting and launching Phaser game.");
            gameInstance = launchCrystalGarden(container, this.gameWidth, this.gameHeight);
            this.gameReady = true;
            this.isLoading = false;
        } catch (error) {
            console.error("Error launching Phaser game for Crystal Garden:", error);
            this.gameReady = false;
            this.isLoading = false;
        }
      } else {
        console.error("Phaser container (gameContainer ref) not found in DOM.");
        this.isLoading = false;
        this.gameReady = false;
      }
    });
  },
  beforeUnmount() {
    console.log("CrystalGardenPage: Destroying Phaser game instance.");
    if (gameInstance) {
      gameInstance.destroy(true); // True to remove canvas from DOM
      gameInstance = null;
    }
    this.gameReady = false;
  },
  // methods: {
  //   // Example: If you need to communicate with the Phaser scene from Vue
  //   handleSomeGameEvent(eventData) {
  //     if (gameInstance && gameInstance.scene.isActive('CrystalGardenScene')) {
  //       const scene = gameInstance.scene.getScene('CrystalGardenScene');
  //       // scene.someMethod(eventData);
  //     }
  //   }
  // }
};
</script>

<style scoped>
.crystal-garden-page-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 20px;
  background-color: #f0f0f0; /* Light grey background for the page */
  min-height: 100vh;
}

#phaser-crystal-garden-game {
  /* Styles for the game container div. Width/height set by data properties. */
  border: 2px solid #333;
  box-shadow: 0 0 10px rgba(0,0,0,0.5);
}

.loading-text, .error-text {
  margin-bottom: 20px;
  font-size: 1.2em;
  color: #333;
}
.error-text {
    color: red;
}
</style>
