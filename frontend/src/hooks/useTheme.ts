import type { ThemeConfig } from 'antd';
import { useCallback, useEffect, useState } from 'react';

export type ThemeName = 'default' | 'qingming' | 'ningye';

const STORAGE_KEY = 'app-theme';

/* ── Ant Design token overrides per theme ── */
const defaultTokens: ThemeConfig = {
  token: {
    colorPrimary: '#D946EF',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#FFFFFF',
    colorBgSpotlight: '#F9FAFB',
    colorBorder: '#E5E7EB',
    colorBorderSecondary: '#F3F4F6',
    colorText: '#1F2937',
    colorTextSecondary: '#6B7280',
    colorTextTertiary: '#9CA3AF',
    colorTextQuaternary: '#D1D5DB',
    colorFillSecondary: '#F3F4F6',
    colorFillTertiary: '#F9FAFB',
    fontFamily: "-apple-system, 'PingFang SC', 'Helvetica Neue', 'Microsoft YaHei', sans-serif",
    fontSize: 13,
    borderRadius: 6,
    borderRadiusLG: 8,
    borderRadiusSM: 4,
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
    boxShadowSecondary: '0 4px 12px rgba(0,0,0,0.08)',
    motionDurationFast: '0.1s',
    motionDurationMid: '0.15s',
    motionDurationSlow: '0.25s',
  },
  components: {
    Card: { colorBgContainer: '#FFFFFF', colorBorderSecondary: '#E5E7EB', paddingLG: 16, headerHeight: 44 },
    Table: { colorBgContainer: '#FFFFFF', headerBg: '#F9FAFB', headerColor: '#6B7280', rowHoverBg: '#F9FAFB', borderColor: '#E5E7EB', headerSplitColor: '#E5E7EB', fontSize: 13, cellPaddingBlock: 8, cellPaddingInline: 12 },
    Button: { primaryShadow: 'none', defaultBg: '#FFFFFF', defaultBorderColor: '#E5E7EB', defaultColor: '#374151' },
    Modal: { contentBg: '#FFFFFF', headerBg: '#FFFFFF', titleColor: '#1F2937' },
    Drawer: { colorBgElevated: '#FFFFFF' },
    Input: { colorBgContainer: '#FFFFFF', activeBorderColor: '#D946EF', hoverBorderColor: '#C084FC', colorBorder: '#E5E7EB' },
    InputNumber: { colorBgContainer: '#FFFFFF', activeBorderColor: '#D946EF', hoverBorderColor: '#C084FC', colorBorder: '#E5E7EB' },
    Select: { colorBgContainer: '#FFFFFF', colorBgElevated: '#FFFFFF', optionSelectedBg: '#FDF4FF', colorBorder: '#E5E7EB', selectorBg: '#FFFFFF' },
    DatePicker: { colorBgContainer: '#FFFFFF', colorBgElevated: '#FFFFFF', colorBorder: '#E5E7EB' },
    Statistic: { titleFontSize: 12, contentFontSize: 22 },
    Tag: { defaultBg: '#F3F4F6', defaultColor: '#374151' },
    Switch: { colorPrimary: '#D946EF', colorPrimaryHover: '#C026D3' },
    Form: { labelColor: '#6B7280', labelFontSize: 13 },
    List: { colorSplit: '#E5E7EB' },
    Tree: { nodeSelectedBg: '#FDF4FF' },
    Pagination: { colorBgContainer: '#FFFFFF', colorBorder: '#E5E7EB' },
    Popover: { colorBgElevated: '#FFFFFF' },
    Popconfirm: { colorBgElevated: '#FFFFFF' },
    Message: { contentBg: '#FFFFFF' },
    Tooltip: { colorBgSpotlight: '#1F2937' },
    Collapse: { colorBgContainer: '#FFFFFF', headerBg: '#F9FAFB', colorBorder: '#E5E7EB' },
  },
};

const qingmingTokens: ThemeConfig = {
  token: {
    ...defaultTokens.token,
    colorPrimary: '#3271AE',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#FAFAF8',
    colorBgSpotlight: '#F2F1EB',
    colorBorder: '#DDD9CE',
    colorBorderSecondary: '#EDECE4',
    colorText: '#343333',
    colorTextSecondary: '#6B6B5E',
    colorTextTertiary: '#9E9B8E',
    colorTextQuaternary: '#C8C4B8',
    colorFillSecondary: '#EDECE4',
    colorFillTertiary: '#F2F1EB',
  },
  components: {
    ...defaultTokens.components,
    Card: { colorBgContainer: '#FFFFFF', colorBorderSecondary: '#DDD9CE', paddingLG: 16, headerHeight: 44 },
    Table: { colorBgContainer: '#FFFFFF', headerBg: '#F2F1EB', headerColor: '#6B6B5E', rowHoverBg: '#F5F3ED', borderColor: '#DDD9CE', headerSplitColor: '#DDD9CE', fontSize: 13, cellPaddingBlock: 8, cellPaddingInline: 12 },
    Button: { primaryShadow: 'none', defaultBg: '#FFFFFF', defaultBorderColor: '#DDD9CE', defaultColor: '#343333' },
    Modal: { contentBg: '#FFFFFF', headerBg: '#FFFFFF', titleColor: '#343333' },
    Input: { colorBgContainer: '#FFFFFF', activeBorderColor: '#3271AE', hoverBorderColor: '#5A94C8', colorBorder: '#DDD9CE' },
    InputNumber: { colorBgContainer: '#FFFFFF', activeBorderColor: '#3271AE', hoverBorderColor: '#5A94C8', colorBorder: '#DDD9CE' },
    Select: { colorBgContainer: '#FFFFFF', colorBgElevated: '#FFFFFF', optionSelectedBg: '#EBF2FA', colorBorder: '#DDD9CE', selectorBg: '#FFFFFF' },
    DatePicker: { colorBgContainer: '#FFFFFF', colorBgElevated: '#FFFFFF', colorBorder: '#DDD9CE' },
    Switch: { colorPrimary: '#3271AE', colorPrimaryHover: '#2861A0' },
    Form: { labelColor: '#6B6B5E', labelFontSize: 13 },
    List: { colorSplit: '#DDD9CE' },
    Tree: { nodeSelectedBg: '#EBF2FA' },
    Pagination: { colorBgContainer: '#FFFFFF', colorBorder: '#DDD9CE' },
    Tag: { defaultBg: '#EDECE4', defaultColor: '#343333' },
    Collapse: { colorBgContainer: '#FFFFFF', headerBg: '#F2F1EB', colorBorder: '#DDD9CE' },
    Tooltip: { colorBgSpotlight: '#343333' },
  },
};

const ningyeTokens: ThemeConfig = {
  token: {
    ...defaultTokens.token,
    colorPrimary: '#A6559D',
    colorBgContainer: '#22223A',
    colorBgElevated: '#22223A',
    colorBgLayout: '#1A1A2E',
    colorBgSpotlight: '#1E1E36',
    colorBorder: '#2E2E4A',
    colorBorderSecondary: '#252542',
    colorText: '#E0DFD5',
    colorTextSecondary: '#A09D90',
    colorTextTertiary: '#706E62',
    colorTextQuaternary: '#4A4840',
    colorFillSecondary: '#252542',
    colorFillTertiary: '#1E1E36',
  },
  components: {
    ...defaultTokens.components,
    Card: { colorBgContainer: '#22223A', colorBorderSecondary: '#2E2E4A', paddingLG: 16, headerHeight: 44 },
    Table: { colorBgContainer: '#22223A', headerBg: '#1E1E36', headerColor: '#A09D90', rowHoverBg: '#252542', borderColor: '#2E2E4A', headerSplitColor: '#2E2E4A', fontSize: 13, cellPaddingBlock: 8, cellPaddingInline: 12 },
    Button: { primaryShadow: 'none', defaultBg: '#22223A', defaultBorderColor: '#2E2E4A', defaultColor: '#E0DFD5' },
    Modal: { contentBg: '#22223A', headerBg: '#22223A', titleColor: '#E0DFD5' },
    Drawer: { colorBgElevated: '#22223A' },
    Input: { colorBgContainer: '#22223A', activeBorderColor: '#A6559D', hoverBorderColor: '#B866AF', colorBorder: '#2E2E4A' },
    InputNumber: { colorBgContainer: '#22223A', activeBorderColor: '#A6559D', hoverBorderColor: '#B866AF', colorBorder: '#2E2E4A' },
    Select: { colorBgContainer: '#22223A', colorBgElevated: '#22223A', optionSelectedBg: '#2A1F2E', colorBorder: '#2E2E4A', selectorBg: '#22223A' },
    DatePicker: { colorBgContainer: '#22223A', colorBgElevated: '#22223A', colorBorder: '#2E2E4A' },
    Switch: { colorPrimary: '#A6559D', colorPrimaryHover: '#B866AF' },
    Form: { labelColor: '#A09D90', labelFontSize: 13 },
    List: { colorSplit: '#2E2E4A' },
    Tree: { nodeSelectedBg: '#2A1F2E' },
    Pagination: { colorBgContainer: '#22223A', colorBorder: '#2E2E4A' },
    Tag: { defaultBg: '#252542', defaultColor: '#E0DFD5' },
    Popover: { colorBgElevated: '#22223A' },
    Popconfirm: { colorBgElevated: '#22223A' },
    Message: { contentBg: '#22223A' },
    Tooltip: { colorBgSpotlight: '#E0DFD5' },
    Collapse: { colorBgContainer: '#22223A', headerBg: '#1E1E36', colorBorder: '#2E2E4A' },
  },
};

const themeMap: Record<ThemeName, ThemeConfig> = {
  default: defaultTokens,
  qingming: qingmingTokens,
  ningye: ningyeTokens,
};

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeName>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return (stored as ThemeName) || 'default';
  });

  useEffect(() => {
    if (theme === 'default') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', theme);
    }
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = useCallback((t: ThemeName) => {
    setThemeState(t);
  }, []);

  return { theme, setTheme, antdTheme: themeMap[theme] };
}
