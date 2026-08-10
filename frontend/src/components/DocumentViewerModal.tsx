import { DocumentModal } from "./DocumentModal";

type Props = {
  paperlessDocumentId: number;
  title: string;
  onClose: () => void;
  /** Ignored — DocumentModal always shows a mode-aware side panel. */
  sidePanel?: unknown;
};

/** @deprecated Prefer DocumentModal with mode="explore" | "classify". */
export function DocumentViewerModal({ paperlessDocumentId, title, onClose }: Props) {
  return (
    <DocumentModal
      paperlessDocumentId={paperlessDocumentId}
      title={title}
      mode="explore"
      onClose={onClose}
    />
  );
}
