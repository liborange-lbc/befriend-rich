import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { createContext, useContext } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/Layout/AppLayout';
import { useTheme, type ThemeName } from './hooks/useTheme';
import Analysis from './pages/Analysis';
import Attribution from './pages/Attribution';
import Backtest from './pages/Backtest';
import ClassificationPage from './pages/Classification';
import Dashboard from './pages/Dashboard';
import Allocation from './pages/Allocation';
import FundsPage from './pages/Funds';
import MarketInsight from './pages/MarketInsight';
import Portfolio from './pages/Portfolio';
import AssetRecords from './pages/AssetRecords';
import Settings from './pages/Settings';
import DataHealth from './pages/DataHealth';
import Correlation from './pages/Correlation';
import FundCompare from './pages/FundCompare';
import FundXray from './pages/FundXray';
import SchedulerPage from './pages/Scheduler';
import StrategyPage from './pages/Strategy';
import Valuation from './pages/Valuation';
import GuruFocus from './pages/GuruFocus';
import ICOption from './pages/ICOption';
import MaTiming from './pages/MaTiming';
import NannySalary from './pages/NannySalary';
import DbViewer from './pages/DbViewer';

/* ── Theme context shared across app ── */
interface ThemeCtx {
  theme: ThemeName;
  setTheme: (t: ThemeName) => void;
}
const ThemeContext = createContext<ThemeCtx>({ theme: 'default', setTheme: () => {} });
export function useThemeContext() { return useContext(ThemeContext); }

export default function App() {
  const { theme, setTheme, antdTheme } = useTheme();

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <ConfigProvider locale={zhCN} theme={antdTheme}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<Navigate to="/portfolio" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="market-insight" element={<MarketInsight />} />
              <Route path="portfolio" element={<Portfolio />} />
              <Route path="funds" element={<FundsPage />} />
              <Route path="asset-records" element={<AssetRecords />} />
              <Route path="classification" element={<ClassificationPage />} />
              <Route path="fund-xray" element={<FundXray />} />
              <Route path="fund-compare" element={<FundCompare />} />
              <Route path="correlation" element={<Correlation />} />
              <Route path="attribution" element={<Attribution />} />
              <Route path="allocation" element={<Allocation />} />
              <Route path="analysis" element={<Analysis />} />
              <Route path="valuation" element={<Valuation />} />
              <Route path="backtest" element={<Backtest />} />
              <Route path="strategy" element={<StrategyPage />} />
              <Route path="scheduler" element={<SchedulerPage />} />
              <Route path="data-health" element={<DataHealth />} />
              <Route path="guru-focus" element={<GuruFocus />} />
              <Route path="ma-timing" element={<MaTiming />} />
              <Route path="ic-option" element={<ICOption />} />
              <Route path="nanny-salary" element={<NannySalary />} />
              <Route path="db-viewer" element={<DbViewer />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}
