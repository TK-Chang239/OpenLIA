import { Info } from "lucide-react";

export function MCPInfoCard() {
  return (
    <div className="bg-[--color-feedback-info]/10 border border-[--color-feedback-info]/30 rounded-[--radius-md] p-3 mb-4 flex gap-3">
      <Info size={16} className="text-[--color-feedback-info] mt-0.5 flex-shrink-0" />
      <div>
        <p className="text-sm font-semibold text-[--color-text-primary] mb-1">
          MCP authentication
        </p>
        <p className="text-sm text-[--color-text-secondary] leading-relaxed">
          OpenLIA doesn't support OAuth for MCP providers. If your endpoint requires
          authentication, include your API key directly in the URL as a query parameter:
        </p>
        <code className="text-xs font-mono bg-[--color-surface-active] px-2 py-1 rounded-[--radius-sm] inline-block mt-1 break-all">
          https://mcp.example.com/sse?api_key=sk_live_xxxxxxxxxxxxxxxx
        </code>
      </div>
    </div>
  );
}
