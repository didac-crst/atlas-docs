type FilterChip = {
  id: string;
  label: string;
};

type Props = {
  chips: FilterChip[];
  onRemove: (id: string) => void;
  onClearAll: () => void;
};

/** Removable active-filter chips for Explore / Classify. */
export function FilterChips({ chips, onRemove, onClearAll }: Props) {
  if (chips.length === 0) return null;
  return (
    <div className="filter-chips" role="group" aria-label="Active filters">
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          className="filter-chip"
          onClick={() => onRemove(chip.id)}
          aria-label={`Remove filter ${chip.label}`}
        >
          <span>{chip.label}</span>
          <span aria-hidden>×</span>
        </button>
      ))}
      <button type="button" className="btn btn-ghost filter-chips-clear" onClick={onClearAll}>
        Clear all
      </button>
    </div>
  );
}
