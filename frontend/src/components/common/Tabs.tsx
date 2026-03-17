import type { ReactNode } from "react";

type TabItem<T extends string> = {
  key: T;
  label: ReactNode;
};

type TabsProps<T extends string> = {
  items: TabItem<T>[];
  activeKey: T;
  onChange: (key: T) => void;
  className?: string;
};

export function Tabs<T extends string>({ items, activeKey, onChange, className }: TabsProps<T>) {
  return (
    <div className={className}>
      <div className="tab-bar" role="tablist" aria-label="編集タブ">
        {items.map((item) => {
          const isActive = item.key === activeKey;
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`tab-item${isActive ? " active" : ""}`}
              onClick={() => onChange(item.key)}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
