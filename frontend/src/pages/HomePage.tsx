import { Link } from "react-router-dom";
import { FilePlus2, GitBranch, Link2, Tags } from "lucide-react";
import markUrl from "../assets/atlas-docs-mark.svg";

const tasks = [
  {
    to: "/classify",
    title: "Classify",
    description: "Search and assign typed relationships to Paperless documents.",
    icon: Tags,
  },
  {
    to: "/ingest",
    title: "Ingest",
    description: "Upload documents and track durable ingestion jobs.",
    icon: FilePlus2,
  },
  {
    to: "/reconcile",
    title: "Reconcile",
    description: "Create missing AtlasDocs entities for Paperless documents.",
    icon: GitBranch,
  },
  {
    to: "/connect",
    title: "Connect",
    description: "Review session connection to Paperless.",
    icon: Link2,
  },
] as const;

export function HomePage() {
  return (
    <section className="home-chooser" aria-labelledby="home-title">
      <div className="home-brand">
        <img src={markUrl} alt="" width={64} height={64} />
        <h1 id="home-title">AtlasDocs</h1>
        <p className="muted">Choose a task to continue.</p>
      </div>
      <ul className="chooser-list">
        {tasks.map((task) => {
          const Icon = task.icon;
          return (
            <li key={task.to}>
              <Link to={task.to} className="chooser-link">
                <Icon size={20} aria-hidden />
                <span>
                  <strong>{task.title}</strong>
                  <span className="meta">{task.description}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
