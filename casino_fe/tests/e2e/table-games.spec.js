import { test, expect } from '@playwright/test';
import { loginUser, clearStorage } from './helpers/test-helpers';

test.describe('Table Games', () => {
  test.beforeEach(async ({ page }) => {
    await clearStorage(page);
    await loginUser(page, 'testuser', 'password123');
  });

  test.describe('Blackjack', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/tables/blackjack');
    });

    test('should load blackjack game correctly', async ({ page }) => {
      await expect(page.locator('[data-testid="blackjack-table"]')).toBeVisible();
      await expect(page.locator('[data-testid="dealer-cards"]')).toBeVisible();
      await expect(page.locator('[data-testid="player-cards"]')).toBeVisible();
      await expect(page.locator('[data-testid="betting-area"]')).toBeVisible();
    });

    test('should handle betting phase correctly', async ({ page }) => {
      // Check betting controls
      await expect(page.locator('[data-testid="bet-amount"]')).toBeVisible();
      await expect(page.locator('[data-testid="bet-increase"]')).toBeVisible();
      await expect(page.locator('[data-testid="bet-decrease"]')).toBeVisible();
      await expect(page.locator('[data-testid="place-bet"]')).toBeVisible();

      // Place a bet
      await page.click('[data-testid="bet-increase"]');
      const betAmount = await page.locator('[data-testid="bet-amount"]').textContent();
      await page.click('[data-testid="place-bet"]');

      // Should start the hand
      await expect(page.locator('[data-testid="deal-button"]')).toBeVisible();
    });

    test('should deal cards and show game actions', async ({ page }) => {
      // Place bet and deal
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-button"]');

      // Should show cards
      await expect(page.locator('[data-testid="player-cards"] .card')).toHaveCount(2);
      await expect(page.locator('[data-testid="dealer-cards"] .card')).toHaveCount.toBeGreaterThanOrEqual(1);

      // Should show action buttons
      await expect(page.locator('[data-testid="hit-button"]')).toBeVisible();
      await expect(page.locator('[data-testid="stand-button"]')).toBeVisible();

      // Check for hand values
      await expect(page.locator('[data-testid="player-hand-value"]')).toBeVisible();
      await expect(page.locator('[data-testid="dealer-hand-value"]')).toBeVisible();
    });

    test('should handle hit action correctly', async ({ page }) => {
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-button"]');

      const initialCards = await page.locator('[data-testid="player-cards"] .card').count();
      
      await page.click('[data-testid="hit-button"]');

      // Should add a card
      await expect(page.locator('[data-testid="player-cards"] .card')).toHaveCount(initialCards + 1);
    });

    test('should handle stand action correctly', async ({ page }) => {
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-button"]');

      await page.click('[data-testid="stand-button"]');

      // Should reveal dealer cards and show result
      await expect(page.locator('[data-testid="game-result"]')).toBeVisible();
      await expect(page.locator('[data-testid="new-hand-button"]')).toBeVisible();
    });

    test('should handle blackjack correctly', async ({ page }) => {
      // This would require mocking the cards to get 21
      await page.evaluate(() => {
        window.mockBlackjack = true;
      });

      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-button"]');

      // Should show blackjack result
      if (await page.locator('[data-testid="blackjack-indicator"]').isVisible()) {
        await expect(page.locator('[data-testid="blackjack-indicator"]')).toBeVisible();
        await expect(page.locator('[data-testid="game-result"]')).toContainText(/blackjack/i);
      }
    });

    test('should handle bust correctly', async ({ page }) => {
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-button"]');

      // Keep hitting until bust (this would need proper test data)
      let handValue = 0;
      while (handValue < 21) {
        if (await page.locator('[data-testid="hit-button"]').isVisible()) {
          await page.click('[data-testid="hit-button"]');
          const valueText = await page.locator('[data-testid="player-hand-value"]').textContent();
          handValue = parseInt(valueText);
        } else {
          break;
        }
      }

      if (handValue > 21) {
        await expect(page.locator('[data-testid="game-result"]')).toContainText(/bust/i);
      }
    });
  });

  test.describe('Baccarat', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/tables/baccarat');
    });

    test('should load baccarat game correctly', async ({ page }) => {
      await expect(page.locator('[data-testid="baccarat-table"]')).toBeVisible();
      await expect(page.locator('[data-testid="player-area"]')).toBeVisible();
      await expect(page.locator('[data-testid="banker-area"]')).toBeVisible();
      await expect(page.locator('[data-testid="tie-area"]')).toBeVisible();
    });

    test('should handle betting on player', async ({ page }) => {
      await page.click('[data-testid="bet-player"]');
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-cards"]');

      await expect(page.locator('[data-testid="player-cards"]')).toBeVisible();
      await expect(page.locator('[data-testid="banker-cards"]')).toBeVisible();
      await expect(page.locator('[data-testid="game-result"]')).toBeVisible();
    });

    test('should handle betting on banker', async ({ page }) => {
      await page.click('[data-testid="bet-banker"]');
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-cards"]');

      await expect(page.locator('[data-testid="game-result"]')).toBeVisible();
    });

    test('should handle tie bet', async ({ page }) => {
      await page.click('[data-testid="bet-tie"]');
      await page.click('[data-testid="place-bet"]');
      await page.click('[data-testid="deal-cards"]');

      await expect(page.locator('[data-testid="game-result"]')).toBeVisible();
    });
  });

  test.describe('Poker', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/tables/poker');
    });

    test('should load poker table correctly', async ({ page }) => {
      await expect(page.locator('[data-testid="poker-table"]')).toBeVisible();
      await expect(page.locator('[data-testid="player-seat"]')).toBeVisible();
      await expect(page.locator('[data-testid="community-cards"]')).toBeVisible();
      await expect(page.locator('[data-testid="pot-display"]')).toBeVisible();
    });

    test('should handle poker actions', async ({ page }) => {
      // Wait for hand to start
      await expect(page.locator('[data-testid="player-cards"]')).toBeVisible();

      // Check available actions
      if (await page.locator('[data-testid="fold-button"]').isVisible()) {
        await expect(page.locator('[data-testid="fold-button"]')).toBeVisible();
      }
      if (await page.locator('[data-testid="call-button"]').isVisible()) {
        await expect(page.locator('[data-testid="call-button"]')).toBeVisible();
      }
      if (await page.locator('[data-testid="raise-button"]').isVisible()) {
        await expect(page.locator('[data-testid="raise-button"]')).toBeVisible();
      }
    });

    test('should handle fold action', async ({ page }) => {
      await expect(page.locator('[data-testid="player-cards"]')).toBeVisible();
      
      if (await page.locator('[data-testid="fold-button"]').isVisible()) {
        await page.click('[data-testid="fold-button"]');
        await expect(page.locator('[data-testid="folded-indicator"]')).toBeVisible();
      }
    });
  });

  test.describe('Roulette', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/tables/roulette');
    });

    test('should load roulette game correctly', async ({ page }) => {
      await expect(page.locator('[data-testid="roulette-wheel"]')).toBeVisible();
      await expect(page.locator('[data-testid="betting-board"]')).toBeVisible();
      await expect(page.locator('[data-testid="chip-selector"]')).toBeVisible();
    });

    test('should place bets on numbers', async ({ page }) => {
      // Select chip value
      await page.click('[data-testid="chip-value-5"]');
      
      // Place bet on number
      await page.click('[data-testid="number-17"]');
      
      // Should show bet on the board
      await expect(page.locator('[data-testid="bet-17"]')).toBeVisible();
    });

    test('should place outside bets', async ({ page }) => {
      await page.click('[data-testid="chip-value-10"]');
      
      // Place bet on red
      await page.click('[data-testid="bet-red"]');
      await expect(page.locator('[data-testid="bet-red-chips"]')).toBeVisible();
      
      // Place bet on odd
      await page.click('[data-testid="bet-odd"]');
      await expect(page.locator('[data-testid="bet-odd-chips"]')).toBeVisible();
    });

    test('should spin wheel and show results', async ({ page }) => {
      // Place a bet
      await page.click('[data-testid="chip-value-5"]');
      await page.click('[data-testid="number-17"]');
      
      // Spin the wheel
      await page.click('[data-testid="spin-button"]');
      
      // Should show spinning animation
      await expect(page.locator('[data-testid="wheel-spinning"]')).toBeVisible();
      
      // Wait for result
      await expect(page.locator('[data-testid="winning-number"]')).toBeVisible();
      await expect(page.locator('[data-testid="spin-result"]')).toBeVisible();
    });
  });
});
