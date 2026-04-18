import { Drawer, Tooltip } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { get } from '../services/api';
import type { Fund } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
  fund: Fund | null;
}

interface DatesResponse {
  dates: string[];
  years: number[];
}

const CELL = 12;
const GAP = 2;
const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
const DAYS = ['一', '', '三', '', '五', '', '日'];

function buildGrid(year: number) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const cells: { date: string; row: number; col: number; future: boolean }[] = [];
  const monthFirstCol: number[] = new Array(12).fill(-1);

  const jan1 = new Date(year, 0, 1);
  const jan1Dow = (jan1.getDay() + 6) % 7; // Mon=0

  const dec31 = new Date(year, 11, 31);
  const cursor = new Date(jan1);

  while (cursor <= dec31) {
    const dayOfYear = Math.floor((cursor.getTime() - jan1.getTime()) / 86400000);
    const dow = (cursor.getDay() + 6) % 7;
    const col = Math.floor((dayOfYear + jan1Dow) / 7);

    const m = cursor.getMonth();
    if (monthFirstCol[m] === -1) {
      monthFirstCol[m] = col;
    }

    const dateStr = `${cursor.getFullYear()}-${String(m + 1).padStart(2, '0')}-${String(cursor.getDate()).padStart(2, '0')}`;
    cells.push({ date: dateStr, row: dow, col, future: cursor > today });

    cursor.setDate(cursor.getDate() + 1);
  }

  const totalCols = cells.length > 0 ? cells[cells.length - 1].col + 1 : 53;

  return { cells, monthFirstCol, totalCols };
}

export default function HeatmapDrawer({ open, fund, onClose }: Props) {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [dateSet, setDateSet] = useState<Set<string>>(new Set());
  const [years, setYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !fund) return;
    setLoading(true);
    get<DatesResponse>('/market-data/dates/' + fund.id, { year }).then((r) => {
      if (r.success) {
        setDateSet(new Set(r.data.dates));
        const yrs = r.data.years;
        const currentYear = new Date().getFullYear();
        if (!yrs.includes(currentYear)) yrs.unshift(currentYear);
        setYears(yrs.sort((a, b) => b - a));
      }
      setLoading(false);
    });
  }, [open, fund, year]);

  const { cells, monthFirstCol, totalCols } = useMemo(() => buildGrid(year), [year]);

  const dataCount = dateSet.size;

  return (
    <Drawer
      title={`${fund?.name || ''} — 历史数据`}
      open={open}
      onClose={onClose}
      width={Math.max(520, totalCols * (CELL + GAP) + 60)}
    >
      {/* Year tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap' }}>
        {years.map((y) => (
          <button
            key={y}
            onClick={() => setYear(y)}
            style={{
              padding: '4px 12px',
              borderRadius: 4,
              border: y === year ? '1px solid #D946EF' : '1px solid #E5E7EB',
              background: y === year ? '#FDF4FF' : '#fff',
              color: y === year ? '#D946EF' : '#6B7280',
              fontWeight: y === year ? 600 : 400,
              fontSize: 13,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {y}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
        {loading ? '加载中...' : `${year} 年共 ${dataCount} 条数据`}
      </div>

      {/* Heatmap */}
      <div style={{ overflowX: 'auto' }}>
        {/* Month labels */}
        <div style={{ display: 'flex', marginLeft: 28, marginBottom: 4 }}>
          {monthFirstCol.map((col, m) => (
            <span
              key={m}
              style={{
                position: 'absolute',
                left: 28 + col * (CELL + GAP),
                fontSize: 10,
                color: '#9CA3AF',
              }}
            >
              {MONTHS[m]}
            </span>
          ))}
        </div>

        <div style={{ position: 'relative', marginTop: 18 }}>
          {/* Day labels */}
          <div style={{ position: 'absolute', left: 0, top: 0 }}>
            {DAYS.map((d, i) => (
              <div
                key={i}
                style={{
                  height: CELL,
                  marginBottom: GAP,
                  fontSize: 10,
                  color: '#9CA3AF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  width: 22,
                }}
              >
                {d}
              </div>
            ))}
          </div>

          {/* Grid */}
          <div
            style={{
              marginLeft: 28,
              display: 'grid',
              gridTemplateRows: `repeat(7, ${CELL}px)`,
              gridAutoColumns: `${CELL}px`,
              gridAutoFlow: 'column',
              gap: GAP,
            }}
          >
            {cells.map((cell) => {
              if (cell.future) {
                return (
                  <div
                    key={cell.date}
                    style={{
                      width: CELL,
                      height: CELL,
                      borderRadius: 2,
                      gridRow: cell.row + 1,
                      gridColumn: cell.col + 1,
                    }}
                  />
                );
              }
              const hasData = dateSet.has(cell.date);
              return (
                <Tooltip
                  key={cell.date}
                  title={`${cell.date} ${hasData ? '✓ 有数据' : '✗ 无数据'}`}
                  mouseEnterDelay={0}
                  mouseLeaveDelay={0}
                >
                  <div
                    style={{
                      width: CELL,
                      height: CELL,
                      borderRadius: 2,
                      background: hasData ? '#D946EF' : '#ebedf0',
                      gridRow: cell.row + 1,
                      gridColumn: cell.col + 1,
                      cursor: 'pointer',
                      transition: 'opacity 0.1s',
                    }}
                  />
                </Tooltip>
              );
            })}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20, fontSize: 11, color: '#9CA3AF' }}>
        <span>少</span>
        <div style={{ width: CELL, height: CELL, borderRadius: 2, background: '#ebedf0' }} />
        <div style={{ width: CELL, height: CELL, borderRadius: 2, background: '#D946EF', opacity: 0.4 }} />
        <div style={{ width: CELL, height: CELL, borderRadius: 2, background: '#D946EF' }} />
        <span>多</span>
      </div>
    </Drawer>
  );
}
