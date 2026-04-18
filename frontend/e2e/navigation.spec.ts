import { expect, test } from '@playwright/test';

test.describe('Navigation - Asset Mode', () => {
  test('should load the app and show asset mode sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=资产总览').first()).toBeVisible();
    await expect(page.locator('text=基金管理').first()).toBeVisible();
    await expect(page.locator('text=分类管理').first()).toBeVisible();
  });

  test('should default to portfolio page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/portfolio/);
  });

  test('should navigate to funds', async ({ page }) => {
    await page.goto('/');
    await page.locator('text=基金管理').first().click();
    await expect(page).toHaveURL(/\/funds/);
  });

  test('should navigate to classification', async ({ page }) => {
    await page.goto('/');
    await page.locator('text=分类管理').first().click();
    await expect(page).toHaveURL(/\/classification/);
  });
});

test.describe('Navigation - Market Mode', () => {
  test('should switch to market mode and show market sidebar', async ({ page }) => {
    await page.goto('/');
    await page.locator('text=行情分析').first().click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator('text=大盘看板').first()).toBeVisible();
    await expect(page.locator('text=基金分析').first()).toBeVisible();
    await expect(page.locator('text=回测').first()).toBeVisible();
    await expect(page.locator('text=策略管理').first()).toBeVisible();
  });

  test('should navigate to analysis in market mode', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('text=基金分析').first().click();
    await expect(page).toHaveURL(/\/analysis/);
  });

  test('should navigate to backtest in market mode', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('text=回测').first().click();
    await expect(page).toHaveURL(/\/backtest/);
  });

  test('should navigate to strategy in market mode', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('text=策略管理').first().click();
    await expect(page).toHaveURL(/\/strategy/);
  });
});

test.describe('Navigation - Settings', () => {
  test('should navigate to settings via gear icon', async ({ page }) => {
    await page.goto('/');
    await page.locator('text=设置').first().click();
    await expect(page).toHaveURL(/\/settings/);
  });
});
