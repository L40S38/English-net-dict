import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./utils";

interface StackProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  gap?: "sm" | "md" | "lg";
}

export function Stack({ children, gap = "md", className, ...rest }: StackProps) {
  return (
    <div
      className={cx("stack", gap === "sm" && "gap-sm", gap === "lg" && "gap-lg", className)}
      {...rest}
    >
      {children}
    </div>
  );
}
