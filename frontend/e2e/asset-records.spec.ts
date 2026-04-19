import { expect, test } from '@playwright/test';

test.describe('Asset Records Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/asset-records');
  });

  test('should navigate to asset records page and show title', async ({ page }) => {
    await expect(page.locator('h1').filter({ hasText: '资产记录' })).toBeVisible();
  });

  test('should show upload and pull buttons in toolbar', async ({ page }) => {
    await expect(page.getByRole('button', { name: /上传 Excel/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /从邮箱拉取/ })).toBeVisible();
  });

  test('should show import history button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /导入历史/ })).toBeVisible();
  });

  test('should show filter bar with date range, search, and model filter', async ({ page }) => {
    await expect(page.getByText('日期范围:')).toBeVisible();
    await expect(page.getByText('搜索:')).toBeVisible();
    await expect(page.getByText('分类模型:')).toBeVisible();
  });

  test('should show group selector section', async ({ page }) => {
    await expect(page.getByText('分组:')).toBeVisible();
  });

  test('should open upload modal when clicking upload button', async ({ page }) => {
    await page.getByRole('button', { name: /上传 Excel/ }).click();
    await expect(page.getByText('选择文件')).toBeVisible();
    await expect(page.getByText('持仓日期')).toBeVisible();
    await expect(page.getByRole('button', { name: /开始导入/ })).toBeVisible();
  });

  test('should close upload modal on cancel', async ({ page }) => {
    await page.getByRole('button', { name: /上传 Excel/ }).click();
    await expect(page.getByText('选择文件')).toBeVisible();

    // Close via the modal's X (close) button
    await page.locator('.ant-modal-close').click();
    await expect(page.locator('.ant-modal-body')).not.toBeVisible();
  });

  test('should open import history drawer', async ({ page }) => {
    await page.getByRole('button', { name: /导入历史/ }).click();
    // Drawer title
    await expect(page.locator('.ant-drawer-title').filter({ hasText: '导入历史' })).toBeVisible();
  });

  test('should close import history drawer', async ({ page }) => {
    await page.getByRole('button', { name: /导入历史/ }).click();
    await expect(page.locator('.ant-drawer-title').filter({ hasText: '导入历史' })).toBeVisible();

    // Close drawer
    await page.locator('.ant-drawer-close').click();
    await expect(page.locator('.ant-drawer-title').filter({ hasText: '导入历史' })).not.toBeVisible();
  });

  test('should show asset records in sidebar navigation', async ({ page }) => {
    await expect(page.locator('.nav-item').filter({ hasText: '资产记录' })).toBeVisible();
  });

  test('should navigate to asset records from sidebar', async ({ page }) => {
    await page.goto('/');
    await page.locator('.nav-item').filter({ hasText: '资产记录' }).click();
    await expect(page).toHaveURL(/\/asset-records/);
    await expect(page.locator('h1').filter({ hasText: '资产记录' })).toBeVisible();
  });

  test('should show data table', async ({ page }) => {
    await expect(page.locator('.ant-table')).toBeVisible();
  });
});
