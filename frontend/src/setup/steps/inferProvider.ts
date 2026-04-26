// Pick the LLM adapter for a (model, api_key, base_url) triple.
// Primary signal: model id prefix. Secondary signal: api key prefix.
// A base_url forces the openai-compatible adapter (vLLM, Groq, etc.).
export function inferProvider(
  model: string,
  apiKey: string,
  baseUrl?: string | null,
): string {
  if (baseUrl && baseUrl.trim()) return "openai_compat";

  const m = model.toLowerCase().trim();
  if (m.startsWith("claude") || m.startsWith("anthropic.")) return "anthropic";
  if (m.startsWith("gemini")) return "gemini";
  if (
    m.startsWith("gpt") ||
    m.startsWith("o1") ||
    m.startsWith("o3") ||
    m.startsWith("o4") ||
    m.startsWith("chatgpt")
  )
    return "openai";
  if (m.startsWith("openrouter/") || m.includes("/")) return "openrouter";

  const key = apiKey.trim();
  if (key.startsWith("sk-ant-")) return "anthropic";
  if (key.startsWith("sk-or-")) return "openrouter";
  if (key.startsWith("sk-")) return "openai";

  return "openai_compat";
}
