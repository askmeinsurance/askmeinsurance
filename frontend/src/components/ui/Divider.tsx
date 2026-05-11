interface DividerProps {
  className?: string;
  orientation?: 'horizontal' | 'vertical';
}

export function Divider({ className = '', orientation = 'horizontal' }: DividerProps) {
  if (orientation === 'vertical') {
    return <div className={`w-px bg-gray-200 self-stretch ${className}`} />;
  }
  return <div className={`h-px w-full bg-gray-200 ${className}`} />;
}
