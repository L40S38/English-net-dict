import type { ReactNode } from "react";

import { LoadingBanner, Row } from "./atom";

interface PageHeaderProps {
  title: ReactNode;
  actions?: ReactNode;
  busy?: boolean;
  busyText?: string;
}

export function PageHeader({
  title,
  actions,
  busy = false,
  busyText = "サーバーと通信中...",
}: PageHeaderProps) {
  return (
    <div className="page-header">
      <Row justify="between">
        <h1>{title}</h1>
        {actions ? <Row>{actions}</Row> : <span />}
      </Row>
      {busy && <LoadingBanner>{busyText}</LoadingBanner>}
    </div>
  );
}
