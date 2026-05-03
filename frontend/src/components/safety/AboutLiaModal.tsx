import { type FC } from "react";
import ReactMarkdown from "react-markdown";

interface Props {
  text: string;
  onClose: () => void;
}

export const AboutLiaModal: FC<Props> = ({ text, onClose }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
    <div className="max-w-xl rounded-lg bg-white p-6 shadow-xl">
      <div className="prose prose-sm max-h-[60vh] overflow-y-auto">
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
      <div className="mt-4 flex justify-end">
        <button
          onClick={onClose}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white"
        >
          Close
        </button>
      </div>
    </div>
  </div>
);
