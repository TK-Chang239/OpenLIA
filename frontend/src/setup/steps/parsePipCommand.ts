/**
 * Parse a pip install command (as it appears in provider docs) into the fields
 * the AddConnectorForm needs for `python_lib` mode.
 *
 * Accepted forms:
 *   pip install eodhd
 *   pip install eodhd -U
 *   python3 -m pip install eodhd -U
 *   pip install 'eodhd>=2.0'
 *   pip install eodhd==1.2.3
 */

export type ParsePipCommandResult =
  | {
      ok: true;
      pipName: string;
      pipVersion: string;
      importModule: string;
    }
  | { ok: false; error: string };

const VERSION_OP_RE = /(==|>=|<=|~=|!=|>|<)/;

export function parsePipCommand(text: string): ParsePipCommandResult {
  const stripped = text.trim().replace(/['"]/g, "");
  const tokens = stripped.split(/\s+/).filter(Boolean);

  const installIdx = tokens.indexOf("install");
  if (installIdx === -1) {
    return { ok: false, error: "Command does not contain 'install'" };
  }

  const pkgToken = tokens.slice(installIdx + 1).find((t) => !t.startsWith("-"));
  if (!pkgToken) {
    return { ok: false, error: "No package name found after 'install'" };
  }

  const match = pkgToken.match(VERSION_OP_RE);
  let pipName = pkgToken;
  let pipVersion = "";
  if (match && match.index !== undefined) {
    pipName = pkgToken.slice(0, match.index);
    pipVersion = pkgToken.slice(match.index);
  }

  const importModule = pipName.replace(/-/g, "_");

  return { ok: true, pipName, pipVersion, importModule };
}
