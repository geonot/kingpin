<template>
    <!-- Improved error message styling -->
    <div v-if="visible"
         class="error-message-box p-4 mb-4 text-sm text-red-700 bg-red-100 rounded-lg dark:bg-red-900 dark:text-red-300 border border-red-300 dark:border-red-600 shadow-md"
         role="alert">
        <div class="flex items-center justify-between">
            <div class="flex items-center">
                 <svg class="flex-shrink-0 inline w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                <span class="font-medium">Error!</span> <span class="ml-2 message">{{ displayMessage }}</span>
            </div>
            <button
                type="button"
                class="dismiss-button ml-auto -mx-1.5 -my-1.5 bg-red-100 text-red-500 rounded-lg focus:ring-2 focus:ring-red-400 p-1.5 hover:bg-red-200 inline-flex h-8 w-8 dark:bg-red-900 dark:text-red-300 dark:hover:bg-red-800"
                aria-label="Dismiss"
                @click="dismiss">
                <span class="sr-only">Dismiss</span>
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
            </button>
        </div>
        
        <!-- Action Button (for cases like deposit suggestion) -->
        <div v-if="actionButton" class="mt-3 flex justify-center">
            <button
                @click="handleActionClick"
                class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg text-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
            >
                {{ actionButton.text }}
            </button>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, defineProps, defineEmits, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from 'vuex';

const router = useRouter();
const store = useStore();

const props = defineProps({
  message: { // Fallback if error object is not provided or not structured
    type: String,
    default: ''
  },
  error: { // Expected to be the structured error object from api.js
    type: Object,
    default: null
  }
});

const emit = defineEmits(['dismiss']);

const enhancedMessage = computed(() => {
  if (props.error && props.error.isStructuredError) {
    // Optional: More specific messages based on errorCode if backend message is generic
    // and no actionButton is present to guide the user.
    if (!props.error.actionButton) {
      switch (props.error.errorCode) {
        case 'BE_GEN_003': // UNAUTHENTICATED
          return "Your session has expired. Please log in again.";
        case 'BE_FIN_200': // INSUFFICIENT_FUNDS
          return "You have insufficient funds for this action. Please consider making a deposit.";
        // Add more cases as needed
      }
    }
    return props.error.message; // Use message from structured error
  }
  return null;
});

const displayMessage = computed(() => {
  if (props.error) {
    if (props.error.isStructuredError) {
      return enhancedMessage.value || props.error.message || 'An unknown structured error occurred.';
    }
    // Fallback for non-structured errors (e.g., network error object from interceptor)
    return props.error.message || 'An unexpected error occurred.';
  }
  return props.message; // Legacy message prop
});

const actionButton = computed(() => {
  // Directly use the actionButton from the structured error if available
  if (props.error && props.error.isStructuredError && props.error.actionButton) {
    return props.error.actionButton;
  }
  // Fallback for older error structures if any part of the app still uses them
  if (props.error && props.error.actionButton) {
     return props.error.actionButton;
  }
  return null;
});

const visible = ref(false);

watch(() => displayMessage.value, (newMessage) => {
  visible.value = !!newMessage;
}, { immediate: true });


const dismiss = () => {
  visible.value = false;
  emit('dismiss');
  // Optionally clear the error from Vuex store if it's a global error message
  if (store.state.globalError === props.error) {
    store.commit('clearGlobalError');
  }
};

const handleActionClick = () => {
  if (actionButton.value && actionButton.value.actionType && actionButton.value.actionPayload) {
    switch (actionButton.value.actionType) {
      case 'NAVIGATE_TO_ROUTE':
        router.push(actionButton.value.actionPayload.route || actionButton.value.actionPayload); // Support simple string or object
        break;
      case 'DISPATCH_VUEX_ACTION':
        store.dispatch(actionButton.value.actionPayload.actionName, actionButton.value.actionPayload.payload);
        break;
      // Example: Emitting an event for parent component to handle
      // case 'EMIT_EVENT':
      //   emit(actionButton.value.actionPayload.eventName, actionButton.value.actionPayload.eventData);
      //   break;
      default:
        console.warn('Unknown actionButton type:', actionButton.value.actionType);
    }
  } else if (actionButton.value && typeof actionButton.value.action === 'function') {
    // Fallback for existing simple action function if still used (legacy)
    actionButton.value.action();
  }
  dismiss(); // Auto-dismiss after action
};

// Optional: Auto-dismiss after a delay
// import { onMounted } from 'vue';
// onMounted(() => {
//   if (props.autoDismissDelay && props.autoDismissDelay > 0) {
//     setTimeout(dismiss, props.autoDismissDelay);
//   }
// });
</script>

<style scoped>
/* Scoped styles if needed, Tailwind handles most styling */
</style>


