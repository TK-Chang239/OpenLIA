import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/sidebar/Sidebar";

export function AppLayout(): JSX.Element {
  return (
    <div className="flex h-screen w-full bg-bg-app text-text-primary">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
