import markUrl from "../assets/atlas-docs-mark.svg";
import { PRODUCT_NAME, PRODUCT_SLOGAN } from "../brand";

type Props = {
  /** Heading level for the product name. */
  titleId?: string;
  /** Use a larger mark for login/home hero moments. */
  size?: "sm" | "md" | "lg";
  /** Optional status line under the slogan (loading, etc.). */
  status?: string;
  asHeading?: boolean;
};

const MARK_SIZE = { sm: 40, md: 56, lg: 64 } as const;

export function ProductIdentity({
  titleId,
  size = "md",
  status,
  asHeading = true,
}: Props) {
  const mark = MARK_SIZE[size];
  const TitleTag = asHeading ? "h1" : "p";

  return (
    <div className={`product-identity product-identity-${size}`}>
      <img src={markUrl} alt="" width={mark} height={mark} />
      <TitleTag id={titleId} className="product-identity-name">
        {PRODUCT_NAME}
      </TitleTag>
      <p className="product-identity-slogan muted">{PRODUCT_SLOGAN}</p>
      {status ? (
        <p className="product-identity-status muted" role="status">
          {status}
        </p>
      ) : null}
    </div>
  );
}
