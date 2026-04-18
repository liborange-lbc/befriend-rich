import { Col, Row, Select } from 'antd';
import { useEffect, useState } from 'react';
import PriceChart from '../../components/Charts/PriceChart';
import { get } from '../../services/api';
import type { Fund, FundDailyPrice } from '../../types';

export default function Analysis() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [selectedFunds, setSelectedFunds] = useState<number[]>([]);
  const [priceData, setPriceData] = useState<Record<number, FundDailyPrice[]>>({});

  useEffect(() => { get<Fund[]>('/funds', { page_size: 100, is_active: true }).then((r) => r.success && setFunds(r.data)); }, []);
  useEffect(() => {
    selectedFunds.forEach((fid) => {
      if (!priceData[fid]) get<FundDailyPrice[]>(`/analysis/prices/${fid}`).then((r) => { if (r.success) setPriceData((prev) => ({ ...prev, [fid]: r.data })); });
    });
  }, [selectedFunds]);

  return (
    <div>
      <h1 style={{ marginBottom: 20 }}>基金分析</h1>
      <div className="section-card" style={{ marginBottom: 16 }}>
        <div className="section-card-header"><span className="section-card-title">选择基金</span></div>
        <div className="section-card-body">
          <Select mode="multiple" style={{ width: '100%' }} placeholder="选择基金进行分析" value={selectedFunds}
            onChange={setSelectedFunds} options={funds.map((f) => ({ label: `${f.name} (${f.code})`, value: f.id }))} />
        </div>
      </div>
      <Row gutter={16}>
        {selectedFunds.map((fid) => {
          const fund = funds.find((f) => f.id === fid);
          return <Col span={selectedFunds.length === 1 ? 24 : 12} key={fid}>
            <div className="section-card"><div className="section-card-body"><PriceChart data={priceData[fid] || []} title={fund?.name || ''} /></div></div>
          </Col>;
        })}
      </Row>
    </div>
  );
}
