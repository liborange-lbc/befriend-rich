import { expect, test } from '@playwright/test';

test.describe('Fund Management', () => {
  test('should display fund management page', async ({ page }) => {
    await page.goto('/funds');
    await expect(page.getByRole('button', { name: /添加基金/ })).toBeVisible();
  });

  test('should create a fund', async ({ page }) => {
    await page.goto('/funds');

    await page.getByRole('button', { name: /添加基金/ }).click();
    await page.getByLabel('代码').fill('510300');
    await page.getByLabel('名称').fill('沪深300ETF');

    await page.getByRole('button', { name: 'OK' }).click();

    await expect(page.locator('text=510300')).toBeVisible();
    await expect(page.locator('text=沪深300ETF')).toBeVisible();
  });

  test('should show duplicate error', async ({ page }) => {
    await page.goto('/funds');

    const uniqueCode = `DUP${Date.now()}`;

    // Create first fund
    await page.getByRole('button', { name: /添加基金/ }).click();
    await page.getByLabel('代码').fill(uniqueCode);
    await page.getByLabel('名称').fill('去重测试基金');
    await page.getByRole('button', { name: 'OK' }).click();

    // Wait for the success message and table to update
    await expect(page.locator(`text=${uniqueCode}`)).toBeVisible({ timeout: 5000 });

    // Try creating duplicate
    await page.getByRole('button', { name: /添加基金/ }).click();
    await page.getByLabel('代码').fill(uniqueCode);
    await page.getByLabel('名称').fill('去重测试重复');
    await page.getByRole('button', { name: 'OK' }).click();

    // Should show error message
    await expect(page.locator('.ant-message').locator('text=已存在')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Classification Management', () => {
  test('should display classification matrix page', async ({ page }) => {
    await page.goto('/classification');
    await expect(page.locator('text=分类管理').first()).toBeVisible();
    await expect(page.getByRole('button', { name: /添加模型/ })).toBeVisible();
  });
});

test.describe('Strategy Management', () => {
  test('should create a strategy', async ({ page }) => {
    await page.goto('/strategy');

    await page.getByRole('button', { name: /添加策略/ }).click();
    await page.getByLabel('名称').fill('沪深300定投');
    await page.getByRole('button', { name: 'OK' }).click();

    await expect(page.locator('text=沪深300定投')).toBeVisible();
  });
});
