import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { cx } from "./utils";

type CardVariant = "default" | "sub";

type CardProps<T extends ElementType> = {
  children: ReactNode;
  as?: T;
  variant?: CardVariant;
  hoverable?: boolean;
  stack?: boolean;
  className?: string;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className">;

export function Card<T extends ElementType = "section">({
  as,
  children,
  variant = "default",
  hoverable = false,
  stack = false,
  className,
  ...rest
}: CardProps<T>) {
  const Component = (as ?? "section") as ElementType;
  return (
    <Component
      className={cx(
        variant === "sub" ? "subcard" : "card",
        hoverable && "hoverable",
        stack && "stack",
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  );
}
