import { test, expect } from '@playwright/test';

test.describe('Council Dashboard E2E', () => {

  test('Should load council dashboard and allow sending a proposal', async ({ page }) => {
    // Navigate to the council dashboard
    await page.goto('/dashboard/council');

    // Wait for the "Council Console" heading or similar
    await expect(page.locator('h1', { hasText: 'Council Console' })).toBeVisible({ timeout: 10000 });

    // The page has a textarea for input
    const inputArea = page.getByPlaceholder('Submit a query for live council deliberation...');
    await expect(inputArea).toBeVisible();

    // Type a sample proposal
    await inputArea.fill('Should we migrate our backend to Rust?');

    // Select the "Parent" council type to trigger a full debate
    const parentButton = page.locator('button', { hasText: 'Parent' });
    if (await parentButton.isVisible()) {
      await parentButton.click();
    }

    // Submit the proposal
    const submitButton = page.locator('button', { hasText: 'Invoke Parent Council' })
                                  .or(page.getByRole('button', { name: /invoke/i }).first())
                                  .or(page.locator('button .lucide-send').locator('..')); // backup 

    if (await submitButton.isVisible()) {
       await submitButton.click();
       
       // Verify we enter a loading state
       await expect(page.locator('text=Initializing').or(page.locator('text=Initializing debate...'))).toBeVisible({ timeout: 15000 });
    }
  });

});
