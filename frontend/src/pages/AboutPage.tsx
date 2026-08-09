import { Link } from "react-router-dom";
import { PRODUCT_NAME, PRODUCT_SLOGAN } from "../brand";
import { PageLayout } from "../components/PageLayout";
import { ProductIdentity } from "../components/ProductIdentity";

export function AboutPage() {
  return (
    <PageLayout width="narrow">
    <section className="about-page" aria-labelledby="about-title">
      <ProductIdentity titleId="about-title" size="lg" />

      <div className="about-body">
        <p>
          {PRODUCT_NAME} transforms document archives into connected knowledge.
        </p>
        <p>
          Every document is treated as evidence. Through entities, relationships, and context,
          evidence becomes knowledge that can be explored, searched, and understood.
        </p>

        <h2>Built on</h2>
        <ul className="about-stack">
          <li>Paperless-ngx</li>
          <li>PostgreSQL</li>
          <li>Valkey</li>
          <li>FastAPI</li>
          <li>React</li>
        </ul>

        <details className="about-manifesto">
          <summary>Product manifesto</summary>
          <pre className="about-manifesto-text">{`Documents are static.
Knowledge is connected.

Every invoice belongs to a purchase.
Every purchase belongs to a person.
Every person belongs to a family.
Every medical report belongs to a life.

AtlasDocs transforms isolated documents into connected evidence,
so knowledge can emerge.

${PRODUCT_SLOGAN}`}</pre>
        </details>

        <p className="muted">
          <Link to="/">Back to Home</Link>
        </p>
      </div>
    </section>
    </PageLayout>
  );
}
