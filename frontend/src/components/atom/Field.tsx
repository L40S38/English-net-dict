import type { LabelHTMLAttributes, ReactNode } from "react";
import { cx } from "./utils";

interface FieldProps extends LabelHTMLAttributes<HTMLLabelElement> {
  label: string;
  children: ReactNode;
}

export function Field({ label, children, className, ...rest }: FieldProps) {
  return (
    <label className={cx("stack", "gap-sm", className)} {...rest}>
      <span>{label}</span>
      {children}
    </label>
  );
}
