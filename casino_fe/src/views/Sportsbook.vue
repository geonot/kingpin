<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <header class="mb-8">
      <h1 class="text-3xl font-bold text-text-primary">Sportsbook</h1>
      <p class="text-text-secondary mt-1">Place your bets on upcoming games.</p>
    </header>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
      <div class="md:col-span-2">
        <div v-if="loading" class="text-center text-text-secondary">
          <p>Loading events...</p>
        </div>
        <div v-else-if="error" class="text-center text-red-500">
          <p>Error loading events: {{ error }}</p>
        </div>
        <div v-else class="space-y-4">
          <div v-for="event in events" :key="event.id" class="bg-bg-secondary p-4 rounded-lg">
            <div class="flex justify-between items-center mb-2">
              <div class="flex items-center space-x-4">
                <span class="font-semibold text-lg text-text-primary">{{ event.home_team }} vs {{ event.away_team }}</span>
              </div>
              <span class="text-sm text-text-secondary">{{ formatDateTime(event.event_datetime) }}</span>
            </div>
            <div v-for="market in event.markets" :key="market.id" class="mt-2">
              <h3 class="text-md font-semibold text-accent mb-2">{{ market.market_type }}</h3>
              <div class="grid grid-cols-2 gap-2">
                <div v-for="odd in market.odds" :key="odd.id"
                     @click="selectOdd(odd, event, market)"
                     :class="['p-2 rounded-md text-center cursor-pointer transition-colors duration-200',
                              selectedOddId === odd.id ? 'bg-accent text-white' : 'bg-bg-tertiary hover:bg-highlight']">
                  <span class="block text-sm text-text-secondary">{{ odd.display_name }}</span>
                  <span class="block font-bold text-lg text-white">{{ odd.decimal_value }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="md:col-span-1">
        <BetSlip :selection="selectedOdd" @clear-selection="clearSelection" @place-bet="handlePlaceBet" />
        <div v-if="betResult" :class="['mt-4 p-4 rounded-lg', betResult.success ? 'bg-green-800' : 'bg-red-800']">
            <p class="text-white">{{ betResult.message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import api from '@/services/api';
import BetSlip from '@/components/sportsbook/BetSlip.vue';
import { useStore } from 'vuex';

export default {
  name: 'Sportsbook',
  components: {
    BetSlip,
  },
  setup() {
    const store = useStore();
    const events = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const selectedOdd = ref(null);
    const selectedOddId = ref(null);
    const betResult = ref(null);

    const fetchEvents = async () => {
      loading.value = true;
      error.value = null;
      try {
        // For demonstration, we'll just fetch the first league's events.
        // In a real app, you'd have UI to select sport and league.
        const leaguesResponse = await api.getLeaguesForSport('nba'); // Hardcoding 'nba' for now
        if (leaguesResponse.data && leaguesResponse.data.length > 0) {
          const leagueSlug = leaguesResponse.data[0].slug;
          const eventsResponse = await api.getEventsForLeague(leagueSlug);

          // Fetch details for each event to get markets and odds
          const detailedEvents = await Promise.all(
            eventsResponse.data.map(event => api.getEventDetails(event.id))
          );
          events.value = detailedEvents.map(res => res.data);
        }
      } catch (err) {
        console.error('Failed to fetch events:', err);
        error.value = err.message || 'An unknown error occurred.';
      } finally {
        loading.value = false;
      }
    };

    const selectOdd = (odd, event, market) => {
      selectedOdd.value = {
        id: odd.id,
        details: {
          ...odd,
          event_name: `${event.home_team} vs ${event.away_team}`,
          market_type: market.market_type,
        }
      };
      selectedOddId.value = odd.id;
    };

    const clearSelection = () => {
      selectedOdd.value = null;
      selectedOddId.value = null;
    };

    const handlePlaceBet = async (betDetails) => {
        betResult.value = null;
        try {
            const response = await api.placeBet({
                odds_id: betDetails.odds_id,
                stake_satoshis: betDetails.stake_satoshis
            });
            betResult.value = { success: true, message: 'Bet placed successfully!' };
            // Refresh user balance from store
            store.dispatch('fetchUserProfile');
            betDetails.onSuccess();
        } catch (err) {
            console.error("Bet placement failed:", err);
            betResult.value = { success: false, message: err.message || "Failed to place bet." };
            betDetails.onError();
        }
    };

    const formatDateTime = (isoString) => {
      const date = new Date(isoString);
      return date.toLocaleString();
    };

    onMounted(fetchEvents);

    return {
      events,
      loading,
      error,
      selectedOdd,
      selectedOddId,
      betResult,
      selectOdd,
      clearSelection,
      handlePlaceBet,
      formatDateTime,
    };
  },
};
</script>

<style scoped>
/* Scoped styles here */
</style>
```
