/**
 * Utility functions for converting and formatting currency, especially Sats and BTC.
 */

const SATOSHI_FACTOR = 100_000_000; // 1 BTC = 100,000,000 Satoshis

/**
 * Formats a Satoshi amount into a BTC string representation.
 *
 * @param {number | bigint} satsAmount The amount in Satoshis.
 * @param {boolean} includeSuffix Whether to include the ' BTC' suffix.
 * @param {number} decimalPlaces The number of decimal places for BTC (default 8).
 * @returns {string} The formatted BTC string (e.g., "0.12345678 BTC"). Returns "0.00000000" for invalid input.
 */
export function formatSatsToBtc(satsAmount, includeSuffix = false, decimalPlaces = 8) {
    try {
        const amount = Number(satsAmount); // Convert BigInt or string if necessary
        if (isNaN(amount) || SATOSHI_FACTOR === 0) {
            return (0).toFixed(decimalPlaces) + (includeSuffix ? ' BTC' : '');
        }

        const btcValue = amount / SATOSHI_FACTOR;
        // Ensure the number of decimal places is respected
        const formatted = btcValue.toFixed(decimalPlaces);
        return includeSuffix ? `${formatted} BTC` : formatted;

    } catch (error) {
        console.error("Error formatting Sats to BTC:", error);
        return (0).toFixed(decimalPlaces) + (includeSuffix ? ' BTC' : '');
    }
}

/**
 * Formats a BTC amount (string or number) into an integer Satoshi amount.
 * Handles potential floating point inaccuracies.
 *
 * @param {number | string} btcAmount The amount in BTC.
 * @returns {number} The amount in Satoshis (integer). Returns 0 for invalid input.
 */
export function formatBtcToSats(btcAmount) {
    try {
        const amount = parseFloat(btcAmount);
        if (isNaN(amount) || SATOSHI_FACTOR === 0) {
            return 0;
        }

        // Multiply and round to avoid floating point issues with large numbers
        const satsValue = Math.round(amount * SATOSHI_FACTOR);
        return satsValue;

    } catch (error) {
        console.error("Error formatting BTC to Sats:", error);
        return 0;
    }
}

// Example usage (optional, for testing):
// console.log(formatSatsToBtc(100000000)); // "1.00000000"
// console.log(formatSatsToBtc(50000000, true)); // "0.50000000 BTC"
// console.log(formatSatsToBtc(12345, true)); // "0.00012345 BTC"
// console.log(formatBtcToSats("1.5")); // 150000000
// console.log(formatBtcToSats(0.00012345)); // 12345
// console.log(formatBtcToSats("invalid")); // 0


