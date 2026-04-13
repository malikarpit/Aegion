import { test, expect } from '@playwright/test';

test.describe('Dashboard interactions', () => {
  test('should display overview metrics', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Check main title
    await expect(page.locator('h1', { hasText: 'Dashboard' })).toBeVisible();
    
    // Check metric cards exist
    await expect(page.getByText('Active Sessions')).toBeVisible();
    await expect(page.getByText('Pending Proposals')).toBeVisible();
    await expect(page.getByText('Spend Today')).toBeVisible();
    await expect(page.getByText('Council Invocations')).toBeVisible();
  });

  test('sidebar navigation functions correctly', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Use the sidebar navigation
    const proposalsLink = page.locator('a[href="/dashboard/proposals"]');
    if (await proposalsLink.isVisible()) {
      await proposalsLink.click();
      
      // Assume navigation completes
      await expect(page).toHaveURL(/.*\/proposals/);
    }
  });
});
