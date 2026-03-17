import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { cx } from "./utils";

interface ChipListProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

interface ChipProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
}

export function ChipList({ children, className, ...rest }: ChipListProps) {
  return (
    <div className={cx("chips", className)} {...rest}>
      {children}
    </div>
  );
}

export function Chip({
  children,
  onClick,
  className,
  type = "button",
  disabled = false,
}: ChipProps) {
  if (onClick) {
    const buttonProps: ButtonHTMLAttributes<HTMLButtonElement> = {
      type,
      onClick,
      className: cx("chip", "button-chip", className),
      disabled,
    };
    return <button {...buttonProps}>{children}</button>;
  }

  return <span className={cx("chip", className)}>{children}</span>;
}
