import type { ProjectSource } from "@/lib/board-utils";

function AdoIcon({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="none"
      aria-hidden="true"
    >
      <rect x="0" y="0" width="8.5" height="8.5" rx="1" fill="#F25022" />
      <rect x="9.5" y="0" width="8.5" height="8.5" rx="1" fill="#7FBA00" />
      <rect x="0" y="9.5" width="8.5" height="8.5" rx="1" fill="#00A4EF" />
      <rect x="9.5" y="9.5" width="8.5" height="8.5" rx="1" fill="#FFB900" />
    </svg>
  );
}

function JiraIcon({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M22.2 11.1L13 1.9 12 .9 4.1 8.8 1.8 11.1a.6.6 0 000 .9l5.5 5.5L12 22.1l7.9-7.9.3-.3 2-2a.6.6 0 000-.8zM12 15.3L8.7 12 12 8.7l3.3 3.3-3.3 3.3z"
        fill="#2684FF"
      />
    </svg>
  );
}

/**
 * Inline SVG badge for the project's work-item source (ADO or Jira).
 * Renders instantly with no network fetch.
 */
export function SourceLogo({
  source,
  size = 20,
  className = "",
}: {
  source: ProjectSource;
  size?: number;
  className?: string;
}) {
  const isJira = source === "jira";
  const label = isJira ? "Jira project" : "Azure DevOps project";
  const iconSize = size - 6;
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-[5px] bg-white ${className}`}
      style={{ width: size, height: size }}
      title={label}
      role="img"
      aria-label={label}
    >
      {isJira ? <JiraIcon size={iconSize} /> : <AdoIcon size={iconSize} />}
    </span>
  );
}
