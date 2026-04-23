import type { FileSource } from "../FileViewerContext";
interface Props { source: FileSource; filename?: string }
export function UnsupportedRenderer(_props: Props): JSX.Element { return <></>; }
