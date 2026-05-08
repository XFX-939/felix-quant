import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "border-[var(--color-primary)] bg-[linear-gradient(180deg,var(--color-primary-hover),var(--color-primary))] text-[var(--text-inverse)] shadow-[0_8px_20px_rgba(255,106,0,0.22)] hover:border-[var(--color-primary-hover)] hover:brightness-110",
        secondary: "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]",
        ghost: "border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]",
        destructive: "border-[var(--color-danger)] bg-[var(--color-danger)] text-white hover:brightness-110",
        outline: "border-[var(--border-strong)] bg-transparent text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
      },
      size: {
        default: "h-9 px-3",
        sm: "h-8 px-2 text-xs",
        icon: "h-9 w-9 px-0"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
