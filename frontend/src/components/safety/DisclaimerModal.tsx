import { type FC } from "react";
import ReactMarkdown from "react-markdown";

interface Props {
  text: string;
  onAccept: () => void;
  onDecline: () => void;
}

export const DisclaimerModal: FC<Props> = ({ text, onAccept, onDecline }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
    <div className="max-w-xl rounded-lg bg-white p-6 shadow-xl">
      <div className="prose prose-sm max-h-[60vh] overflow-y-auto">
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button onClick={onDecline} className="px-3 py-1.5 text-sm text-slate-600">
          Sign out / Quit
        </button>
        <button
          onClick={onAccept}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white"
        >
          I understand
        </button>
      </div>
    </div>
  </div>
);
