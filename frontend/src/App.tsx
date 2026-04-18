import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/Layout/AppLayout';
import Analysis from './pages/Analysis';
import Backtest from './pages/Backtest';
import ClassificationPage from './pages/Classification';
import Dashboard from './pages/Dashboard';
import FundsPage from './pages/Funds';
import Portfolio from './pages/Portfolio';
import Settings from './pages/Settings';
import StrategyPage from './pages/Strategy';

const feishuTheme = {
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
    Card: {
      colorBgContainer: '#FFFFFF',
      colorBorderSecondary: '#E5E7EB',
      paddingLG: 16,
      headerFontSize: 14,
      headerHeight: 44,
    },
    Table: {
      colorBgContainer: '#FFFFFF',
      headerBg: '#F9FAFB',
      headerColor: '#6B7280',
      rowHoverBg: '#F9FAFB',
      borderColor: '#E5E7EB',
      headerSplitColor: '#E5E7EB',
      fontSize: 13,
      headerFontSize: 12,
      cellPaddingBlock: 8,
      cellPaddingInline: 12,
    },
    Button: {
      primaryShadow: 'none',
      defaultBg: '#FFFFFF',
      defaultBorderColor: '#E5E7EB',
      defaultColor: '#374151',
    },
    Modal: {
      contentBg: '#FFFFFF',
      headerBg: '#FFFFFF',
      titleColor: '#1F2937',
    },
    Drawer: {
      colorBgElevated: '#FFFFFF',
    },
    Input: {
      colorBgContainer: '#FFFFFF',
      activeBorderColor: '#D946EF',
      hoverBorderColor: '#C084FC',
      colorBorder: '#E5E7EB',
    },
    InputNumber: {
      colorBgContainer: '#FFFFFF',
      activeBorderColor: '#D946EF',
      hoverBorderColor: '#C084FC',
      colorBorder: '#E5E7EB',
    },
    Select: {
      colorBgContainer: '#FFFFFF',
      colorBgElevated: '#FFFFFF',
      optionSelectedBg: '#FDF4FF',
      colorBorder: '#E5E7EB',
      selectorBg: '#FFFFFF',
    },
    DatePicker: {
      colorBgContainer: '#FFFFFF',
      colorBgElevated: '#FFFFFF',
      colorBorder: '#E5E7EB',
    },
    Statistic: {
      titleFontSize: 12,
      contentFontSize: 22,
    },
    Tag: {
      defaultBg: '#F3F4F6',
      defaultColor: '#374151',
    },
    Switch: {
      colorPrimary: '#D946EF',
      colorPrimaryHover: '#C026D3',
    },
    Form: {
      labelColor: '#6B7280',
      labelFontSize: 13,
    },
    List: {
      colorSplit: '#E5E7EB',
    },
    Tree: {
      nodeSelectedBg: '#FDF4FF',
    },
    Pagination: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#E5E7EB',
    },
    Popover: {
      colorBgElevated: '#FFFFFF',
    },
    Popconfirm: {
      colorBgElevated: '#FFFFFF',
    },
    Message: {
      contentBg: '#FFFFFF',
    },
    Tooltip: {
      colorBgSpotlight: '#1F2937',
    },
  },
};

export default function App() {
  return (
    <ConfigProvider locale={zhCN} theme={feishuTheme}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/portfolio" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="portfolio" element={<Portfolio />} />
            <Route path="funds" element={<FundsPage />} />
            <Route path="classification" element={<ClassificationPage />} />
            <Route path="analysis" element={<Analysis />} />
            <Route path="backtest" element={<Backtest />} />
            <Route path="strategy" element={<StrategyPage />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
