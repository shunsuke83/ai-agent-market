import type { ChangeEvent, ElementType, ReactNode } from "react";
import { NavLink } from "react-router-dom";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* ------------------------------------------------------------------ */
/* Navigation shell                                                    */
/* ------------------------------------------------------------------ */

export type NavItem = { to: string; label: string };
export type NavGroup = { label?: string; items: NavItem[] };

export type AppSidebarProps = {
  brand: ReactNode;
  groups: NavGroup[];
  footer?: ReactNode;
  /** Mobile only: show the sidebar (controlled by the host app). */
  open?: boolean;
  /** Called after a nav link is clicked (e.g. to close the mobile menu). */
  onNavigate?: () => void;
};

export function AppSidebar({ brand, groups, footer, open, onNavigate }: AppSidebarProps) {
  return (
    <aside className={cx("ds-sidebar", open && "is-open")}>
      <div className="ds-sidebar__brand">{brand}</div>
      <nav className="ds-sidebar__nav" aria-label="주 메뉴">
        {groups.map((g, i) => (
          <div className="ds-sidebar__group" key={g.label ?? `group-${i}`}>
            {g.label ? <div className="ds-sidebar__group-label">{g.label}</div> : null}
            {g.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={onNavigate}
                className={({ isActive }) => cx("ds-sidebar__link", isActive && "is-active")}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      {footer ? <div className="ds-sidebar__footer">{footer}</div> : null}
    </aside>
  );
}

export function AppTopbar({ title, children }: { title?: ReactNode; children?: ReactNode }) {
  return (
    <header className="ds-topbar">
      {title ? <div className="ds-topbar__title">{title}</div> : null}
      {children}
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Primitives                                                          */
/* ------------------------------------------------------------------ */

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "brand";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: BadgeTone }) {
  return <span className={cx("ds-badge", `ds-badge--${tone}`)}>{children}</span>;
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="ds-tag">{children}</span>;
}

export type AlertTone = "info" | "success" | "warning" | "danger";

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={cx("ds-alert", `ds-alert--${tone}`)} role={tone === "danger" ? "alert" : "status"}>
      {title ? <div className="ds-alert__title">{title}</div> : null}
      {children ? <div>{children}</div> : null}
    </div>
  );
}

export function Spinner() {
  return <div className="ds-spinner" role="status" aria-label="불러오는 중" />;
}

export function EmptyState({ title, description }: { title: ReactNode; description?: ReactNode }) {
  return (
    <div className="ds-empty">
      <div className="ds-empty__title">{title}</div>
      {description ? <div className="ds-empty__desc">{description}</div> : null}
    </div>
  );
}

export type ButtonProps = {
  variant?: "primary" | "secondary" | "ghost";
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
};

export function Button({ variant = "primary", children, onClick, type = "button", disabled }: ButtonProps) {
  return (
    <button
      type={type}
      className={cx("ds-button", `ds-button--${variant}`)}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export type InputProps = {
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  type?: string;
};

export function Input({ value, onChange, placeholder, type = "text" }: InputProps) {
  return (
    <input
      className="ds-input"
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
    />
  );
}

export type TextVariant = "title" | "heading" | "body" | "caption" | "muted";

export function Text({
  as,
  variant = "body",
  children,
  className,
}: {
  as?: ElementType;
  variant?: TextVariant;
  children?: ReactNode;
  className?: string;
}) {
  const Tag = (as ?? "p") as ElementType;
  return <Tag className={cx("ds-text", `ds-text--${variant}`, className)}>{children}</Tag>;
}

/* ------------------------------------------------------------------ */
/* Data display                                                        */
/* ------------------------------------------------------------------ */

export function StatCard({ label, value, hint }: { label: ReactNode; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="ds-stat">
      <div className="ds-stat__label">{label}</div>
      <div className="ds-stat__value">{value}</div>
      {hint ? <div className="ds-stat__hint">{hint}</div> : null}
    </div>
  );
}

export function MetricCard({ label, value, hint }: { label: ReactNode; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="ds-stat ds-stat--metric">
      <div className="ds-stat__label">{label}</div>
      <div className="ds-stat__value">{value}</div>
      {hint ? <div className="ds-stat__hint">{hint}</div> : null}
    </div>
  );
}

export type DataTableColumn<Row = Record<string, unknown>> = {
  key: string;
  header: ReactNode;
  render?: (row: Row, index: number) => ReactNode;
  align?: "left" | "right" | "center";
};

export type DataTableProps<Row = Record<string, unknown>> = {
  columns: DataTableColumn<Row>[];
  rows: Row[];
  empty?: ReactNode;
};

export function DataTable<Row extends object = Record<string, unknown>>({
  columns,
  rows,
  empty,
}: DataTableProps<Row>) {
  if (rows.length === 0) {
    return <>{empty ?? <EmptyState title="데이터가 없습니다" />}</>;
  }
  const alignClass = (a?: "left" | "right" | "center") =>
    a === "right" ? "ds-align-right" : a === "center" ? "ds-align-center" : undefined;
  return (
    <div className="ds-table-wrap">
      <table className="ds-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={alignClass(c.align)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => {
                const raw = (row as Record<string, unknown>)[c.key];
                return (
                  <td key={c.key} className={alignClass(c.align)}>
                    {c.render ? c.render(row, i) : (raw as ReactNode) ?? ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DescriptionList({ items }: { items: { label: ReactNode; value: ReactNode }[] }) {
  return (
    <dl className="ds-dl">
      {items.map((it, i) => (
        <div key={i} style={{ display: "contents" }}>
          <dt>{it.label}</dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export type ListControlProps = {
  search?: boolean | string;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  filters?: ReactNode;
  children?: ReactNode;
};

export function ListControl({ search, searchValue, onSearchChange, filters, children }: ListControlProps) {
  const showSearch = !!search || onSearchChange !== undefined;
  const placeholder = typeof search === "string" ? search : "검색";
  return (
    <div className="ds-list-control">
      {showSearch ? (
        <div className="ds-list-control__search">
          <Input
            value={searchValue ?? ""}
            onChange={(e) => onSearchChange?.(e.target.value)}
            placeholder={placeholder}
            type="search"
          />
        </div>
      ) : null}
      {filters ? <div className="ds-list-control__filters">{filters}</div> : null}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page layouts                                                        */
/* ------------------------------------------------------------------ */

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="ds-page-header">
      <div>
        <h1 className="ds-page-header__title">{title}</h1>
        {description ? <p className="ds-page-header__desc">{description}</p> : null}
      </div>
      {actions ? <div className="ds-page-header__actions">{actions}</div> : null}
    </div>
  );
}

export function DashboardPageLayout({
  title,
  description,
  stamp,
  stats,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  stamp?: ReactNode;
  stats?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="ds-page">
      <PageHeader title={title} description={description} actions={stamp ? <span className="ds-stamp">{stamp}</span> : null} />
      {stats ? <div className="ds-stats">{stats}</div> : null}
      {children}
    </div>
  );
}

export function ListPageLayout({
  title,
  description,
  toolbar,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  toolbar?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="ds-page">
      <PageHeader title={title} description={description} />
      <div className="ds-card ds-card--flush">
        {toolbar}
        {children}
      </div>
    </div>
  );
}

export function DetailPageLayout({
  title,
  description,
  badges,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="ds-page">
      <div>
        <PageHeader title={title} description={description} />
        {badges ? <div className="ds-badges">{badges}</div> : null}
      </div>
      {children}
    </div>
  );
}

/** Convenience white card wrapper (not in the documented API, but handy inside layouts). */
export function Card({ children, flush }: { children?: ReactNode; flush?: boolean }) {
  return <div className={cx("ds-card", flush && "ds-card--flush")}>{children}</div>;
}

/** Shell frame: sidebar + main column. */
export function AppShellFrame({ sidebar, topbar, children }: { sidebar: ReactNode; topbar?: ReactNode; children: ReactNode }) {
  return (
    <div className="ds-shell">
      {sidebar}
      <div className="ds-main">
        {topbar}
        <main className="ds-main__content">{children}</main>
      </div>
    </div>
  );
}
