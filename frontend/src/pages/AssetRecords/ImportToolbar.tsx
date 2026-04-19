import {
  FileExcelOutlined,
  HistoryOutlined,
  MailOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  Button,
  DatePicker,
  Drawer,
  Modal,
  notification,
  Space,
  Table,
  Tag,
  Upload,
} from 'antd';
import type { UploadFile } from 'antd';
import type { Dayjs } from 'dayjs';
import { useCallback, useState } from 'react';
import { getImportLogs, pullEmail, uploadExcel } from '../../services/api';
import type { ImportLog } from '../../types';

interface ImportToolbarProps {
  onImportSuccess: () => void;
}

export default function ImportToolbar({ onImportSuccess }: ImportToolbarProps) {
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<UploadFile | null>(null);
  const [recordDate, setRecordDate] = useState<Dayjs | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [logs, setLogs] = useState<ImportLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const handleUpload = useCallback(async () => {
    if (!uploadFile?.originFileObj || !recordDate) {
      notification.warning({ message: '请选择文件和日期' });
      return;
    }
    setUploading(true);
    try {
      const resp = await uploadExcel(
        uploadFile.originFileObj,
        recordDate.format('YYYY-MM-DD'),
      );
      if (resp.success) {
        notification.success({
          message: '导入成功',
          description: `共导入 ${resp.data.records_imported} 条记录，新建 ${resp.data.new_funds_created} 个基金`,
        });
        setUploadModalOpen(false);
        setUploadFile(null);
        setRecordDate(null);
        onImportSuccess();
      } else {
        notification.error({ message: '导入失败', description: resp.error || '未知错误' });
      }
    } catch (err) {
      notification.error({ message: '导入失败', description: String(err) });
    } finally {
      setUploading(false);
    }
  }, [uploadFile, recordDate, onImportSuccess]);

  const handlePullEmail = useCallback(async (force = false) => {
    setPulling(true);
    try {
      const resp = await pullEmail(force);
      if (resp.success) {
        notification.success({
          message: '拉取成功',
          description: `对账单日期: ${resp.data.statement_date}，导入 ${resp.data.records_imported} 条记录`,
        });
        onImportSuccess();
      } else {
        // Handle 409 conflict - ask user if they want to force
        if (resp.error?.includes('已导入') && !force) {
          Modal.confirm({
            title: '对账单已导入',
            content: resp.error + '，是否覆盖？',
            onOk: () => handlePullEmail(true),
          });
        } else {
          notification.error({ message: '拉取失败', description: resp.error || '未知错误' });
        }
      }
    } catch (err) {
      notification.error({ message: '拉取失败', description: String(err) });
    } finally {
      setPulling(false);
    }
  }, [onImportSuccess]);

  const openHistory = useCallback(async () => {
    setHistoryOpen(true);
    setLogsLoading(true);
    try {
      const resp = await getImportLogs(50);
      if (resp.success) setLogs(resp.data);
    } finally {
      setLogsLoading(false);
    }
  }, []);

  const logColumns = [
    {
      title: '日期', dataIndex: 'import_date', key: 'import_date', width: 110,
    },
    {
      title: '来源', dataIndex: 'source', key: 'source', width: 100,
      render: (v: string) => (
        <Tag color={v === 'excel_upload' ? 'blue' : 'green'}>
          {v === 'excel_upload' ? 'Excel' : '邮箱'}
        </Tag>
      ),
    },
    { title: '文件名', dataIndex: 'file_name', key: 'file_name', ellipsis: true },
    { title: '记录数', dataIndex: 'record_count', key: 'record_count', width: 80 },
    { title: '新基金', dataIndex: 'new_funds_count', key: 'new_funds_count', width: 80 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => (
        <Tag color={v === 'success' ? 'green' : 'red'}>{v === 'success' ? '成功' : '失败'}</Tag>
      ),
    },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  ];

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
      <Space>
        <Button
          icon={<UploadOutlined />}
          onClick={() => setUploadModalOpen(true)}
        >
          上传 Excel
        </Button>
        <Button
          icon={<MailOutlined />}
          loading={pulling}
          onClick={() => handlePullEmail(false)}
        >
          从邮箱拉取
        </Button>
      </Space>
      <Button
        icon={<HistoryOutlined />}
        onClick={openHistory}
      >
        导入历史
      </Button>

      {/* Upload Modal */}
      <Modal
        title="上传 Excel"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setUploadFile(null); setRecordDate(null); }}
        onOk={handleUpload}
        confirmLoading={uploading}
        okText="开始导入"
        okButtonProps={{ disabled: !uploadFile || !recordDate }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '12px 0' }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>选择文件</div>
            <Upload
              accept=".xlsx"
              maxCount={1}
              beforeUpload={() => false}
              fileList={uploadFile ? [uploadFile] : []}
              onChange={({ fileList }) => setUploadFile(fileList[0] || null)}
            >
              <Button icon={<FileExcelOutlined />}>选择 .xlsx 文件</Button>
            </Upload>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>持仓日期</div>
            <DatePicker
              value={recordDate}
              onChange={setRecordDate}
              style={{ width: '100%' }}
              placeholder="选择持仓记录日期"
            />
          </div>
        </div>
      </Modal>

      {/* History Drawer */}
      <Drawer
        title="导入历史"
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        width={720}
      >
        <Table
          dataSource={logs}
          columns={logColumns}
          rowKey="id"
          loading={logsLoading}
          size="small"
          pagination={false}
        />
      </Drawer>
    </div>
  );
}
