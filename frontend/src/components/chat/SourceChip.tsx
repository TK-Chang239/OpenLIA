import type { JSX } from "react";
import { motion } from "framer-motion";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import {
  FileText,
  FileSpreadsheet,
  Code,
  Image,
  Newspaper,
  Search,
  Database,
  Table,
  Globe,
  type LucideIcon,
} from "lucide-react";

export type SourceKind =
  | "pdf"
  | "doc"
  | "csv"
  | "code"
  | "image"
  | "news"
  | "search"
  | "data"
  | "table"
  | "web";

interface Props {
  label: string;
  kind?: SourceKind;
  /** Tooltip / accessible name when label alone isn't enough context. */
  title?: string;
  /** Click handler. When omitted, the chip renders as non-interactive. */
  onClick?: () => void;
  /** Visual hint when the chip's underlying artifact is still resolving
   *  (e.g., tool call status === "running"). */
  pending?: boolean;
  /** Stagger index for entry animation; chips within a row pass 0,1,2,...
   *  to get a 40ms-apart fade-in. Omit for a static (non-staggered) entry. */
  index?: number;
}

const KIND_ICON: Record<SourceKind, LucideIcon> = {
  pdf: FileText,
  doc: FileText,
  csv: FileSpreadsheet,
  code: Code,
  image: Image,
  news: Newspaper,
  search: Search,
  data: Database,
  table: Table,
  web: Globe,
};

export function SourceChip({
  label,
  kind = "doc",
  title,
  onClick,
  pending = false,
  index = 0,
}: Props): JSX.Element {
  const Icon = KIND_ICON[kind];
  const interactive = typeof onClick === "function";
  const reduce = useReducedMotion();
  const MotionTag = interactive ? motion.button : motion.span;
  return (
    <MotionTag
      initial={{ opacity: 0, y: reduce ? 0 : 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduce ? 0 : 0.2,
        ease: "easeOut",
        delay: reduce ? 0 : index * 0.04,
      }}
      type={interactive ? "button" : undefined}
      onClick={onClick}
      title={title ?? label}
      aria-label={title ?? label}
      className={[
        "inline-flex items-center gap-[6px] rounded-sm border px-2 py-[3px] font-mono text-[10px]",
        "transition-colors duration-normal ease-out",
        interactive ? "cursor-pointer" : "cursor-default",
        pending ? "opacity-60" : "",
        interactive
          ? "hover:border-yellow-600 hover:text-feedback-success hover:bg-accent-subtle"
          : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        borderColor: "var(--color-border-subtle)",
        background: "var(--color-bg-elevated)",
        color: "var(--color-text-secondary)",
      }}
    >
      <Icon size={10} strokeWidth={1.5} aria-hidden />
      <span className="truncate max-w-[220px]">{label}</span>
    </MotionTag>
  );
}
