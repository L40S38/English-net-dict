import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { cx } from "./utils";

type MutedProps<T extends ElementType> = {
  children: ReactNode;
  as?: T;
  className?: string;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className">;

export function Muted<T extends ElementType = "span">({
  as,
  children,
  className,
  ...rest
}: MutedProps<T>) {
  const Component = (as ?? "span") as ElementType;
  return (
    <Component className={cx("muted", className)} {...rest}>
      {children}
    </Component>
  );
}
