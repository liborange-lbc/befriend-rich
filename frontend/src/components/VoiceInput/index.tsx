import { AudioOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';
import { useCallback, useRef, useState } from 'react';

interface VoiceInputProps {
  onResult: (text: string) => void;
  disabled?: boolean;
}

const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export default function VoiceInput({ onResult, disabled = false }: VoiceInputProps) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const supported = !!SpeechRecognition;

  const toggle = useCallback(() => {
    if (!supported) return;

    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0]?.[0]?.transcript;
      if (transcript) {
        onResult(transcript);
      }
      setListening(false);
    };

    recognition.onerror = () => {
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, [listening, onResult, supported]);

  const button = (
    <Button
      size="small"
      icon={<AudioOutlined />}
      disabled={disabled || !supported}
      onClick={toggle}
      danger={listening}
      style={listening ? { animation: 'pulse 1.2s infinite' } : undefined}
    />
  );

  if (!supported) {
    return <Tooltip title="浏览器不支持语音输入">{button}</Tooltip>;
  }

  return button;
}
