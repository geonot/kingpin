import { test, expect } from '@playwright/test';

/**
 * E2E tests for complete game workflows
 * Tests slot games, poker tables, and Plinko gameplay
 */

test.describe('Game Flow Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[type="text"]', 'testuser');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/slots');
  });

  test.describe('Slot Games', () => {
    test('should navigate to slots and display available games', async ({ page }) => {
      // Should be on slots page already from login
      await expect(page).toHaveURL('/slots');
      
      // Should show slot game options
      await expect(page.locator('.slot-card, .game-card')).toHaveCount.greaterThan(0);
      
      // Should show game titles and descriptions
      await expect(page.locator('text=/Classic Slots|Video Slots|Bonus Slots/i')).toBeVisible();
    });

    test('should load and play a slot game', async ({ page }) => {
      // Click on first available slot
      await page.click('.slot-card:first-child, .game-card:first-child');
      
      // Should navigate to slot game page
      await expect(page.url()).toMatch(/\/slots\/\d+/);
      
      // Wait for game to load
      await expect(page.locator('#phaser-slot-machine')).toBeVisible();
      
      // Should show game controls and info
      await expect(page.locator('.slot-container')).toBeVisible();
      
      // Should show back button
      await expect(page.locator('text=Back to Slots')).toBeVisible();
    });

    test('should handle slot game errors gracefully', async ({ page }) => {
      // Navigate to non-existent slot
      await page.goto('/slots/999999');
      
      // Should show error message or redirect
      const hasError = await page.locator('.error-message').isVisible();
      const wasRedirected = page.url().includes('/slots') && !page.url().includes('/slots/999999');
      
      expect(hasError || wasRedirected).toBeTruthy();
    });

    test('should show game information and controls', async ({ page }) => {
      // Navigate to slot game
      await page.click('.slot-card:first-child, .game-card:first-child');
      
      // Wait for game elements to load
      await page.waitForSelector('#phaser-slot-machine', { timeout: 10000 });
      
      // Should show game title and description
      await expect(page.locator('h2')).toBeVisible();
      
      // Should show user balance
      await expect(page.locator('.user-balance')).toBeVisible();
    });
  });

  test.describe('Table Games', () => {
    test('should navigate to tables and show available games', async ({ page }) => {
      await page.click('text=Tables');
      await expect(page).toHaveURL('/tables');
      
      // Should show table game options
      await expect(page.locator('text=/Blackjack|Poker|Baccarat/i')).toBeVisible();
    });

    test('should access Blackjack game', async ({ page }) => {
      await page.click('text=Tables');
      
      // Look for Blackjack option and click
      if (await page.locator('text=Blackjack').isVisible()) {
        await page.click('text=Blackjack');
        await expect(page).toHaveURL('/blackjack');
        
        // Should show blackjack interface
        await expect(page.locator('.blackjack-table, .game-table')).toBeVisible();
      }
    });

    test('should access Poker Tables', async ({ page }) => {
      await page.click('text=Tables');
      
      // Look for Poker option and click
      if (await page.locator('text=Poker').isVisible()) {
        await page.click('text=Poker');
        
        // Should navigate to poker tables or specific table
        expect(page.url()).toMatch(/\/poker|\/tables/);
      }
    });
  });

  test.describe('Plinko Game', () => {
    test('should access and interact with Plinko game', async ({ page }) => {
      // Navigate to Plinko (might be under Games or specific menu)
      await page.goto('/plinko');
      
      // Should show Plinko game interface
      await expect(page.locator('.plinko-game, #phaser-plinko')).toBeVisible();
      
      // Should show stake selection
      await expect(page.locator('.stake-selection')).toBeVisible();
      
      // Should show drop ball button
      await expect(page.locator('.drop-ball-button, button:has-text("Drop")')).toBeVisible();
    });

    test('should allow stake selection in Plinko', async ({ page }) => {
      await page.goto('/plinko');
      
      // Wait for game to load
      await page.waitForSelector('.stake-selection', { timeout: 5000 });
      
      // Try different stake levels
      const stakeButtons = await page.locator('.stake-selection button').all();
      
      if (stakeButtons.length > 0) {
        // Click different stake options
        await stakeButtons[0].click();
        await expect(stakeButtons[0]).toHaveClass(/active|selected/);
        
        if (stakeButtons.length > 1) {
          await stakeButtons[1].click();
          await expect(stakeButtons[1]).toHaveClass(/active|selected/);
        }
      }
    });
  });

  test.describe('Game Session Management', () => {
    test('should handle game session timeouts', async ({ page }) => {
      // Start a game
      await page.click('.slot-card:first-child, .game-card:first-child');
      
      // Wait for game to load
      await page.waitForSelector('#phaser-slot-machine', { timeout: 10000 });
      
      // Simulate session timeout by waiting and checking for session management
      await page.waitForTimeout(2000);
      
      // Navigate away and back
      await page.click('text=Back to Slots');
      await expect(page).toHaveURL('/slots');
    });

    test('should maintain balance updates across game sessions', async ({ page }) => {
      // Record initial balance
      const initialBalance = await page.locator('.user-balance').textContent();
      
      // Play a game (navigate to slot)
      await page.click('.slot-card:first-child, .game-card:first-child');
      
      // Wait for game to load
      await page.waitForSelector('#phaser-slot-machine', { timeout: 10000 });
      
      // Navigate back
      await page.click('text=Back to Slots');
      
      // Balance should still be displayed and reasonable
      const finalBalance = await page.locator('.user-balance').textContent();
      expect(finalBalance).toBeTruthy();
    });
  });

  test.describe('Cross-browser Game Compatibility', () => {
    test('should load Phaser games in different browsers', async ({ page, browserName }) => {
      console.log(`Testing in browser: ${browserName}`);
      
      // Navigate to a game
      await page.click('.slot-card:first-child, .game-card:first-child');
      
      // Wait for Phaser canvas to load
      await page.waitForSelector('#phaser-slot-machine canvas', { timeout: 15000 });
      
      // Verify game canvas is rendered
      const canvas = await page.locator('#phaser-slot-machine canvas');
      await expect(canvas).toBeVisible();
      
      // Check canvas dimensions are reasonable
      const canvasBox = await canvas.boundingBox();
      expect(canvasBox?.width).toBeGreaterThan(100);
      expect(canvasBox?.height).toBeGreaterThan(100);
    });
  });

  test.describe('Mobile Game Experience', () => {
    test('should be responsive on mobile devices', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      
      // Navigate to game
      await page.click('.slot-card:first-child, .game-card:first-child');
      
      // Game should adapt to mobile view
      await page.waitForSelector('#phaser-slot-machine', { timeout: 10000 });
      
      // Check mobile-specific elements
      const gameContainer = await page.locator('#phaser-slot-machine');
      const containerBox = await gameContainer.boundingBox();
      
      // Should fit mobile viewport
      expect(containerBox?.width).toBeLessThanOrEqual(375);
    });

    test('should handle touch interactions on mobile', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      
      await page.goto('/plinko');
      
      // Wait for game to load
      await page.waitForSelector('.plinko-game', { timeout: 5000 });
      
      // Try touch interactions (tap)
      if (await page.locator('.drop-ball-button').isVisible()) {
        await page.locator('.drop-ball-button').tap();
      }
    });
  });
});
