import { expect, test } from '@playwright/test';

test.describe('Portfolio', () => {
  test('should display portfolio page', async ({ page }) => {
    await page.goto('/portfolio');
    await expect(page.locator('text=总资产').first()).toBeVisible();
    await expect(page.locator('text=录入本周数据').first()).toBeVisible();
  });

  test('should open input modal', async ({ page }) => {
    await page.goto('/portfolio');
    await page.getByRole('button', { name: /录入本周数据/ }).click();
    await expect(page.locator('text=录入本周持仓')).toBeVisible();
  });

  test('should display top5 section', async ({ page }) => {
    await page.goto('/portfolio');
    await expect(page.locator('text=持仓 TOP 5')).toBeVisible();
  });
});
