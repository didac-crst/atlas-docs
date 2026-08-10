type Props = {
  selectedCount: number;
  onClear: () => void;
  onAddRelationship: () => void;
};

/** Contextual batch actions for Classify multi-selection. */
export function ClassifyBatchBar({ selectedCount, onClear, onAddRelationship }: Props) {
  if (selectedCount <= 0) return null;

  return (
    <div className="classify-batch-bar" role="region" aria-label="Batch actions">
      <p className="classify-batch-count">
        <strong>{selectedCount}</strong> selected
      </p>
      <div className="classify-batch-actions">
        <button type="button" className="btn btn-primary" onClick={onAddRelationship}>
          Add relationship
        </button>
        <button type="button" className="btn btn-ghost" onClick={onClear}>
          Clear selection
        </button>
      </div>
    </div>
  );
}
