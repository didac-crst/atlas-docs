import { PRODUCT_SLOGAN } from "../brand";
import { PageLayout } from "../components/PageLayout";
import { ProductIdentity } from "../components/ProductIdentity";

export function AboutPage() {
  return (
    <PageLayout width="narrow">
      <section className="about-page" aria-labelledby="about-title">
        <ProductIdentity titleId="about-title" size="lg" />

        <div className="about-body">
          <p>
            AtlasDocs transforms document archives into connected knowledge.
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

          <section className="about-manifesto" aria-labelledby="manifesto-title">
            <h2 id="manifesto-title">Product manifesto</h2>
            <blockquote className="about-manifesto-quote">
              <p>Documents are static.</p>
              <p>Knowledge is connected.</p>
              <p>
                Every invoice belongs to a purchase.
                <br />
                Every purchase belongs to a person.
                <br />
                Every person belongs to a family.
                <br />
                Every medical report belongs to a life.
              </p>
              <p>
                AtlasDocs transforms isolated documents into connected evidence,
                so knowledge can emerge.
              </p>
              <footer>{PRODUCT_SLOGAN}</footer>
            </blockquote>
          </section>
        </div>
      </section>
    </PageLayout>
  );
}
