import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import Shell from "./layout/Shell";
import AgenciesPage from "./pages/AgenciesPage";
import AlertsPage from "./pages/AlertsPage";
import AwardsPage from "./pages/AwardsPage";
import BandPage from "./pages/BandPage";
import BidDetailPage from "./pages/BidDetailPage";
import BiddersPage from "./pages/BiddersPage";
import CompetitorsPage from "./pages/CompetitorsPage";
import DeliverablesPage from "./pages/DeliverablesPage";
import HomePage from "./pages/HomePage";
import NotFoundPage from "./pages/NotFoundPage";
import PlansPage from "./pages/PlansPage";
import PrespecsPage from "./pages/PrespecsPage";
import PricingPage from "./pages/PricingPage";
import ReportsPage from "./pages/ReportsPage";

/** /bids/:file.html -> /bids/:id (strip .html); React Router v6 has no partial-segment params. */
function BidRoute() {
  const { id = "" } = useParams();
  if (/\.html$/i.test(id)) {
    return <Navigate to={`/bids/${encodeURIComponent(id.replace(/\.html$/i, ""))}`} replace />;
  }
  return <BidDetailPage />;
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "") || undefined}>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<HomePage />} />
          <Route path="band" element={<BandPage />} />
          <Route path="awards" element={<AwardsPage />} />
          <Route path="pricing" element={<PricingPage />} />
          <Route path="plans" element={<PlansPage />} />
          <Route path="prespecs" element={<PrespecsPage />} />
          <Route path="bidders" element={<BiddersPage />} />
          <Route path="agencies" element={<AgenciesPage />} />
          <Route path="competitors" element={<CompetitorsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="deliverables" element={<DeliverablesPage />} />
          <Route path="bids/:id" element={<BidRoute />} />

          {/* legacy static-site URLs */}
          <Route path="index.html" element={<Navigate to="/" replace />} />
          <Route path="band.html" element={<Navigate to="/band" replace />} />
          <Route path="awards.html" element={<Navigate to="/awards" replace />} />
          <Route path="pricing.html" element={<Navigate to="/pricing" replace />} />
          <Route path="plans.html" element={<Navigate to="/plans" replace />} />
          <Route path="prespecs.html" element={<Navigate to="/prespecs" replace />} />
          <Route path="bidders.html" element={<Navigate to="/bidders" replace />} />
          <Route path="agencies.html" element={<Navigate to="/agencies" replace />} />
          <Route path="alerts.html" element={<Navigate to="/alerts" replace />} />
          <Route path="competitors.html" element={<Navigate to="/competitors" replace />} />
          <Route path="deliverables.html" element={<Navigate to="/deliverables" replace />} />
          <Route path="reports/index.html" element={<Navigate to="/reports" replace />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
