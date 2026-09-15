import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AuthEntry } from "./AuthEntry";
import { AuthResult } from "./AuthResult";
import { CreateProjectPage } from "./CreateProjectPage";
import { ProjectOperationPage } from "./ProjectOperationPage";
import { ProjectPage } from "./ProjectPage";
import { ProjectsPage } from "./ProjectsPage";
import { ModelSavePage } from "./ModelSavePage";
import { ModelSettingsPage } from "./ModelSettingsPage";
import { ProjectSettingsPage } from "./ProjectSettingsPage";
import { RepositoryHome } from "./RepositoryHome";
import { destinationForRoute, parseRoute, rememberLoginDestination } from "./routes";
import { AuthFrame } from "./shared";
import { useSession } from "./session";
import { WorkspaceApp } from "./workspace/WorkspaceApp";
import { isWorkspaceDemoPath } from "./workspace/routes";
import "./style.css";

function App() {
  const [path, setPath] = useState(() => window.location.pathname);
  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const navigate = useCallback((next: string) => {
    window.history.pushState(null, "", next);
    setPath(next);
    window.scrollTo(0, 0);
  }, []);
  if (isWorkspaceDemoPath(path)) return <WorkspaceApp path={path} navigate={navigate} />;
  return <ProductApp path={path} navigate={navigate} />;
}

function ProductApp({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const auth = useSession();
  const currentRoute = parseRoute(path);
  if (currentRoute.kind === "result") return <AuthResult key={`${currentRoute.id}:${auth.generation}`} id={currentRoute.id} auth={auth} navigate={navigate} />;
  if (currentRoute.kind !== "login" && currentRoute.kind !== "not-found" && auth.state.kind !== "authenticated") {
    rememberLoginDestination(destinationForRoute(currentRoute));
    return <AuthEntry key={auth.generation} auth={auth} navigate={navigate} />;
  }
  if (auth.state.kind === "authenticated") {
    const props = { session: auth.state.session, auth, navigate };
    switch (currentRoute.kind) {
      case "home": return <RepositoryHome key={auth.generation} {...props} />;
      case "projects": return <ProjectsPage key={auth.generation} {...props} />;
      case "project-create": return <CreateProjectPage key={auth.generation} {...props} />;
      case "project": return <ProjectPage key={`${auth.generation}:${currentRoute.projectId}`} {...props} projectId={currentRoute.projectId} />;
      case "project-settings": return <ProjectSettingsPage key={`${auth.generation}:${currentRoute.projectId}`} {...props} projectId={currentRoute.projectId} />;
      case "project-creation-result": return <ProjectOperationPage key={`${auth.generation}:${currentRoute.key}`} {...props} operation={{ actor: auth.state.session.user.id, kind: "project_create", key: currentRoute.key }} />;
      case "project-update-result": return <ProjectOperationPage key={`${auth.generation}:${currentRoute.projectId}:${currentRoute.key}`} {...props} operation={{ actor: auth.state.session.user.id, kind: "project_update", projectId: currentRoute.projectId, key: currentRoute.key }} />;
      case "model-settings": return <ModelSettingsPage key={auth.generation} {...props} />;
      case "model-save-result": return <ModelSavePage key={`${auth.generation}:${currentRoute.key}`} {...props} saveId={currentRoute.key} />;
      case "login": return <AuthEntry key={auth.generation} auth={auth} navigate={navigate} />;
      case "not-found": return <AuthFrame title="页面不存在" description="这个地址没有对应的 RepoMesh 页面。"><button className="primary" onClick={() => navigate("/")}>返回工作区</button></AuthFrame>;
      default: {
        const exhaustive: never = currentRoute;
        return exhaustive;
      }
    }
  }
  switch (currentRoute.kind) {
    case "login": return <AuthEntry key={auth.generation} auth={auth} navigate={navigate} />;
    case "not-found": return <AuthFrame title="页面不存在" description="这个地址没有对应的 RepoMesh 页面。"><button className="primary" onClick={() => navigate("/")}>返回工作区</button></AuthFrame>;
    default: return <AuthEntry key={auth.generation} auth={auth} navigate={navigate} />;
  }
}

const root = document.getElementById("root");
if (root === null) throw new Error("Missing application root");
createRoot(root).render(<StrictMode><App /></StrictMode>);
