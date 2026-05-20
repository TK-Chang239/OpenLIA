import type { JSX } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PendingAttachmentChip } from "./PendingAttachmentChip";
import { useReducedMotion } from "../../hooks/useReducedMotion";

export interface UserBubbleAttachment {
  filename: string;
  sizeBytes: number;
}

interface Props {
  content: string;
  timestamp?: string;
  attachments?: UserBubbleAttachment[];
}

export function UserBubble({ content, timestamp, attachments }: Props): JSX.Element {
  const { t } = useTranslation();
  const hasAttachments = (attachments?.length ?? 0) > 0;
  const reduce = useReducedMotion();
  return (
    <motion.article
      role="article"
      aria-label={t("chat.aria_user_message")}
      initial={{ opacity: 0, y: reduce ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col items-end gap-[6px]"
    >
      {hasAttachments ? (
        <div className="flex flex-wrap justify-end gap-[6px] max-w-[520px]">
          {attachments!.map((a, i) => (
            <PendingAttachmentChip
              key={`${a.filename}-${i}`}
              filename={a.filename}
              sizeBytes={a.sizeBytes}
            />
          ))}
        </div>
      ) : null}
      {content ? (
        <div
          className="max-w-[520px] whitespace-pre-wrap rounded-[10px] px-[15px] py-[11px] text-[14px] leading-[1.5] font-display"
          style={{
            background: "var(--color-user-bubble-bg)",
            color: "var(--color-user-bubble-text)",
          }}
        >
          {content}
        </div>
      ) : null}
      {timestamp ? (
        <time className="mt-1 font-mono text-[10px] text-text-tertiary">{timestamp}</time>
      ) : null}
    </motion.article>
  );
}
