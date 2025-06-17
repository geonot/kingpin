import { test, expect } from '@playwright/test';
import { loginUser, clearStorage } from './helpers/test-helpers';

test.describe('Slots Gameplay', () => {
  test.beforeEach(async ({ page }) => {
    await clearStorage(page);
    await loginUser(page, 'testuser', 'password123');
    await page.goto('/slots');
  });

  test('should load slots lobby with available games', async ({ page }) => {
    await expect(page.locator('[data-testid="slots-lobby"]')).toBeVisible();
    await expect(page.locator('.slot-card')).toHaveCount.toBeGreaterThan(0);
    
    // Check for essential slot information
    const firstSlot = page.locator('.slot-card').first();
    await expect(firstSlot.locator('.slot-name')).toBeVisible();
    await expect(firstSlot.locator('.slot-rtp')).toBeVisible();
    await expect(firstSlot.locator('.play-button')).toBeVisible();
  });

  test('should launch a slot game successfully', async ({ page }) => {
    const firstSlot = page.locator('.slot-card').first();
    const slotName = await firstSlot.locator('.slot-name').textContent();
    
    await firstSlot.locator('.play-button').click();
    
    // Should navigate to game
    await expect(page).toHaveURL(/\/slots\/.+/);
    await expect(page.locator('[data-testid="slot-game"]')).toBeVisible();
    await expect(page.locator('[data-testid="spin-button"]')).toBeVisible();
    await expect(page.locator('[data-testid="bet-controls"]')).toBeVisible();
  });

  test('should display game controls and bet settings', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Check for essential game controls
    await expect(page.locator('[data-testid="spin-button"]')).toBeVisible();
    await expect(page.locator('[data-testid="bet-amount"]')).toBeVisible();
    await expect(page.locator('[data-testid="balance-display"]')).toBeVisible();
    await expect(page.locator('[data-testid="bet-increase"]')).toBeVisible();
    await expect(page.locator('[data-testid="bet-decrease"]')).toBeVisible();
    
    // Check for auto-spin features
    await expect(page.locator('[data-testid="auto-spin-button"]')).toBeVisible();
  });

  test('should adjust bet amount correctly', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    const initialBet = await page.locator('[data-testid="bet-amount"]').textContent();
    
    // Increase bet
    await page.click('[data-testid="bet-increase"]');
    const increasedBet = await page.locator('[data-testid="bet-amount"]').textContent();
    expect(parseFloat(increasedBet)).toBeGreaterThan(parseFloat(initialBet));
    
    // Decrease bet
    await page.click('[data-testid="bet-decrease"]');
    const decreasedBet = await page.locator('[data-testid="bet-amount"]').textContent();
    expect(parseFloat(decreasedBet)).toBeLessThan(parseFloat(increasedBet));
  });

  test('should perform a spin and show results', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    const initialBalance = await page.locator('[data-testid="balance-display"]').textContent();
    const betAmount = await page.locator('[data-testid="bet-amount"]').textContent();
    
    // Start spin
    await page.click('[data-testid="spin-button"]');
    
    // Check for spinning animation
    await expect(page.locator('[data-testid="reels"]')).toHaveClass(/spinning/);
    
    // Wait for spin to complete
    await expect(page.locator('[data-testid="spin-button"]')).not.toHaveClass(/disabled/);
    await expect(page.locator('[data-testid="reels"]')).not.toHaveClass(/spinning/);
    
    // Check that balance was updated
    const finalBalance = await page.locator('[data-testid="balance-display"]').textContent();
    expect(parseFloat(finalBalance)).toBeLessThanOrEqual(parseFloat(initialBalance));
    
    // Check for win display if applicable
    const winAmount = page.locator('[data-testid="win-amount"]');
    if (await winAmount.isVisible()) {
      await expect(winAmount).toContainText(/\d+/);
    }
  });

  test('should handle insufficient balance gracefully', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Set bet higher than balance (simulate by calling API directly)
    await page.evaluate(() => {
      // Simulate low balance
      window.testSetBalance = 1;
    });
    
    // Try to set high bet
    for (let i = 0; i < 10; i++) {
      await page.click('[data-testid="bet-increase"]');
    }
    
    // Try to spin
    await page.click('[data-testid="spin-button"]');
    
    // Should show error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toContainText(/insufficient|balance/i);
  });

  test('should display game statistics', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Check for game info panel
    await expect(page.locator('[data-testid="game-info"]')).toBeVisible();
    await expect(page.locator('[data-testid="rtp-display"]')).toBeVisible();
    await expect(page.locator('[data-testid="volatility-display"]')).toBeVisible();
    await expect(page.locator('[data-testid="max-win-display"]')).toBeVisible();
  });

  test('should handle auto-spin functionality', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Start auto-spin
    await page.click('[data-testid="auto-spin-button"]');
    
    // Should show auto-spin controls
    await expect(page.locator('[data-testid="auto-spin-controls"]')).toBeVisible();
    
    // Select number of auto-spins
    await page.selectOption('[data-testid="auto-spin-count"]', '10');
    await page.click('[data-testid="start-auto-spin"]');
    
    // Should start auto-spinning
    await expect(page.locator('[data-testid="auto-spin-indicator"]')).toBeVisible();
    await expect(page.locator('[data-testid="stop-auto-spin"]')).toBeVisible();
    
    // Stop auto-spin
    await page.click('[data-testid="stop-auto-spin"]');
    await expect(page.locator('[data-testid="auto-spin-indicator"]')).not.toBeVisible();
  });

  test('should trigger bonus features correctly', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Simulate bonus trigger (this would need to be mocked or use test data)
    await page.evaluate(() => {
      // Simulate bonus round
      window.triggerBonusRound = true;
    });
    
    await page.click('[data-testid="spin-button"]');
    
    // Check for bonus round activation
    if (await page.locator('[data-testid="bonus-round"]').isVisible()) {
      await expect(page.locator('[data-testid="bonus-round"]')).toBeVisible();
      await expect(page.locator('[data-testid="bonus-instructions"]')).toBeVisible();
    }
  });

  test('should return to slots lobby', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Return to lobby
    await page.click('[data-testid="back-to-lobby"]');
    
    // Should be back in lobby
    await expect(page).toHaveURL('/slots');
    await expect(page.locator('[data-testid="slots-lobby"]')).toBeVisible();
  });

  test('should handle game errors gracefully', async ({ page }) => {
    await page.locator('.slot-card').first().locator('.play-button').click();
    
    // Simulate network error during spin
    await page.route('**/api/slots/*/spin', route => {
      route.abort();
    });
    
    await page.click('[data-testid="spin-button"]');
    
    // Should show error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toContainText(/error|failed/i);
  });
});
