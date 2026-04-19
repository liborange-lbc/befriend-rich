import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { createContext, useContext } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/Layout/AppLayout';
import { useTheme, type ThemeName } from './hooks/useTheme';
import Analysis from './pages/Analysis';
import Backtest from './pages/Backtest';
import ClassificationPage from './pages/Classification';
import Dashboard from './pages/Dashboard';
import FundsPage from './pages/Funds';
import Portfolio from './pages/Portfolio';
import Settings from './pages/Settings';
import StrategyPage from './pages/Strategy';

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
    </ThemeContext.Provider>
  );
}
