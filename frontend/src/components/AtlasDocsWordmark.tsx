type Props = {
  /** Optional accessible name; decorative when omitted and parent supplies text. */
  labelled?: boolean;
  className?: string;
  as?: "span" | "strong" | "h1" | "h2" | "p";
};

/**
 * Official AtlasDocs wordmark: Atlas in navy, Docs as one color per letter
 * (D→o→c→s stepped blue→cyan). Do not apply this styling to ordinary body copy.
 */
export function AtlasDocsWordmark({
  labelled = true,
  className,
  as: Tag = "span",
}: Props) {
  const classes = ["atlas-docs-wordmark", className].filter(Boolean).join(" ");
  // Spans must be adjacent (no whitespace) so the accessible name is “AtlasDocs”.
  return (
    <Tag className={classes} aria-label={labelled ? "AtlasDocs" : undefined}>
      <span className="atlas-docs-wordmark-atlas">Atlas</span><span className="atlas-docs-wordmark-d">D</span><span className="atlas-docs-wordmark-o">o</span><span className="atlas-docs-wordmark-c">c</span><span className="atlas-docs-wordmark-s">s</span>
    </Tag>
  );
}
