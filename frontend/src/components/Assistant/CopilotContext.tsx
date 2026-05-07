import { createContext, useContext } from 'react';

export type OpenWithContextFn = (sectionName: string, contextData: unknown) => void;

const CopilotCtx = createContext<OpenWithContextFn>(() => {});

export const CopilotProvider = CopilotCtx.Provider;

export function useCopilot(): OpenWithContextFn {
  return useContext(CopilotCtx);
}
