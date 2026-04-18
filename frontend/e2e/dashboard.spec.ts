import { expect, test } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should display dashboard overview', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=总资产').first()).toBeVisible();
  });

  test('should show fund quotes section', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=基金行情').or(page.locator('text=最新行情')).first()).toBeVisible({ timeout: 5000 });
  });
});
