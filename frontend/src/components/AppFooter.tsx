import { Link } from "react-router-dom";
import { PRODUCT_NAME, PRODUCT_SLOGAN } from "../brand";

export function AppFooter() {
  return (
    <footer className="site-footer">
      <p className="site-footer-brand">
        <strong>{PRODUCT_NAME}</strong>
        <span className="muted"> {PRODUCT_SLOGAN}</span>
      </p>
      <p className="site-footer-credit muted">Powered by Paperless-ngx</p>
      <p className="site-footer-links">
        <Link to="/about">About</Link>
      </p>
    </footer>
  );
}
