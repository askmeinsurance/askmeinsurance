import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  label?: string;
  variant?: 'ghost' | 'solid';
  size?: 'sm' | 'md';
}

export function IconButton({
  children,
  label,
  variant = 'ghost',
  size = 'md',
  className = '',
  ...props
}: IconButtonProps) {
  const base =
    'inline-flex items-center justify-center rounded-lg cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500';

  const variants: Record<string, string> = {
    ghost: 'text-gray-500 hover:bg-gray-100 hover:text-gray-700',
    solid: 'bg-blue-600 text-white hover:bg-blue-700',
  };

  const sizes: Record<string, string> = {
    sm: 'p-1',
    md: 'p-2',
  };

  return (
    <button
      type="button"
      aria-label={label}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
