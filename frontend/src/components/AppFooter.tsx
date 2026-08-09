import { Link } from "react-router-dom";
import { PRODUCT_SLOGAN } from "../brand";
import { AtlasDocsWordmark } from "./AtlasDocsWordmark";

export function AppFooter() {
  return (
    <footer className="site-footer">
      <p className="site-footer-brand">
        <AtlasDocsWordmark as="strong" />
        <span className="site-footer-sep" aria-hidden>
          ·
        </span>
        <span className="site-footer-motto muted">{PRODUCT_SLOGAN}</span>
      </p>
      <p className="site-footer-credit muted">Powered by Paperless-ngx</p>
      <p className="site-footer-links">
        <Link to="/about">About</Link>
      </p>
    </footer>
  );
}
