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
import { ref, watch, defineProps, defineEmits } from 'vue';

import { computed } from 'vue'; // Import computed

const props = defineProps({
  message: {
    type: String,
    default: ''
  },
  error: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['dismiss']);

const displayMessage = computed(() => {
  if (props.error) {
    return props.error.status_message || props.error.message || 'An unknown error occurred.';
  }
  return props.message;
});

const actionButton = computed(() => {
  if (props.error && props.error.actionButton) {
    return props.error.actionButton;
  }
  return null;
});

const visible = ref(!!displayMessage.value); // Initial visibility based on message presence

// Watch the displayMessage to automatically become visible when message changes
watch(displayMessage, (newMessage) => {
  visible.value = !!newMessage;
});

const dismiss = () => {
  visible.value = false;
  emit('dismiss');
};

const handleActionClick = () => {
  if (actionButton.value && typeof actionButton.value.action === 'function') {
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


