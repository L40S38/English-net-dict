import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { cx } from "./utils";

type RowProps<T extends ElementType> = {
  children: ReactNode;
  as?: T;
  justify?: "start" | "between";
  className?: string;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className">;

export function Row<T extends ElementType = "div">({
  as,
  children,
  justify = "start",
  className,
  ...rest
}: RowProps<T>) {
  const Component = (as ?? "div") as ElementType;
  return (
    <Component className={cx(justify === "between" ? "row-between" : "row", className)} {...rest}>
      {children}
    </Component>
  );
}
