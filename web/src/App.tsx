import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { CpuPage } from "./pages/CpuPage";
import { MemoryPage } from "./pages/MemoryPage";
import { DiskPage } from "./pages/DiskPage";
import { NetworkPage } from "./pages/NetworkPage";
import { DockerPage } from "./pages/DockerPage";
import { SecurityPage } from "./pages/SecurityPage";
import { DockerImagesPage } from "./pages/DockerImagesPage";
import { DockerNetworksPage } from "./pages/DockerNetworksPage";
import { DockerVolumesPage } from "./pages/DockerVolumesPage";

function Gate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink-300 border-t-ink-800" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LoginRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route
            path="/"
            element={
              <Gate>
                <Dashboard />
              </Gate>
            }
          />
          <Route
            path="/cpu"
            element={
              <Gate>
                <CpuPage />
              </Gate>
            }
          />
          <Route
            path="/memory"
            element={
              <Gate>
                <MemoryPage />
              </Gate>
            }
          />
          <Route
            path="/disk"
            element={
              <Gate>
                <DiskPage />
              </Gate>
            }
          />
          <Route
            path="/network"
            element={
              <Gate>
                <NetworkPage />
              </Gate>
            }
          />
          <Route path="/security" element={<Gate><SecurityPage /></Gate>} />
          <Route path="/docker/containers" element={<Gate><DockerPage /></Gate>} />
          <Route path="/docker/images" element={<Gate><DockerImagesPage /></Gate>} />
          <Route path="/docker/networks" element={<Gate><DockerNetworksPage /></Gate>} />
          <Route path="/docker/volumes" element={<Gate><DockerVolumesPage /></Gate>} />
          <Route path="/docker" element={<Navigate to="/docker/containers" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
