import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./utils";

interface LoadingBannerProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function LoadingBanner({ children, className, ...rest }: LoadingBannerProps) {
  return (
    <div className={cx("loading-banner", className)} {...rest}>
      {children}
    </div>
  );
}
