import { SmileOutlined } from '@ant-design/icons';

interface AssistantButtonProps {
  onClick: () => void;
}

export default function AssistantButton({ onClick }: AssistantButtonProps) {
  return (
    <div
      onClick={onClick}
      style={{
        position: 'fixed',
        right: 24,
        bottom: 24,
        width: 48,
        height: 48,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #D946EF, #A855F7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        zIndex: 1001,
        boxShadow: '0 4px 16px rgba(217, 70, 239, 0.4)',
        transition: 'transform 0.2s, box-shadow 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'scale(1.1)';
        e.currentTarget.style.boxShadow = '0 6px 20px rgba(217, 70, 239, 0.5)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'scale(1)';
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(217, 70, 239, 0.4)';
      }}
    >
      <SmileOutlined style={{ fontSize: 24, color: '#FFFFFF' }} />
    </div>
  );
}
