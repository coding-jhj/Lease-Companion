import { Navigate, Outlet, createBrowserRouter } from "react-router-dom";
import { AnalysisProgressPage } from "./pages/analysis-progress/AnalysisProgressPage";
import { AuthPage } from "./pages/auth/AuthPage";
import { ContractCreatePage } from "./pages/contract-create/ContractCreatePage";
import { ContractSituationPage } from "./pages/contract-create/ContractSituationPage";
import { ContractPreparationPage } from "./pages/contract-preparation/ContractPreparationPage";
import { ContractDetailPage } from "./pages/contract-detail/ContractDetailPage";
import { DashboardPage } from "./pages/dashboard/DashboardPage";
import { DocumentUploadPage } from "./pages/document-upload/DocumentUploadPage";
import { ExtractionReviewPage } from "./pages/extraction-review/ExtractionReviewPage";
import { ResultReportPage } from "./pages/result-report/ResultReportPage";
import { ModeSelectPage } from "./pages/mode-select/ModeSelectPage";
import { PracticeHomePage } from "./pages/practice/PracticeHomePage";
import { PracticeResultPage } from "./pages/practice/PracticeResultPage";
import { PracticeScenarioPage } from "./pages/practice/PracticeScenarioPage";
import { PracticeSessionPage } from "./pages/practice/PracticeSessionPage";
import { getAccessToken } from "./services/authToken";

function RequireAuth() {
  return getAccessToken() ? <Outlet /> : <Navigate to="/login" replace />;
}

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "/login", element: <AuthPage mode="login" /> },
  { path: "/signup", element: <AuthPage mode="signup" /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/choose-mode", element: <ModeSelectPage /> },
      { path: "/prepare", element: <ContractPreparationPage /> },
      { path: "/contracts", element: <DashboardPage /> },
      { path: "/contracts/new", element: <ContractCreatePage /> },
      { path: "/contracts/:contractId/situation", element: <ContractSituationPage /> },
      { path: "/contracts/:contractId/upload", element: <DocumentUploadPage /> },
      { path: "/contracts/:contractId/review", element: <ExtractionReviewPage /> },
      { path: "/contracts/:contractId/analyzing", element: <AnalysisProgressPage /> },
      { path: "/contracts/:contractId/report", element: <ResultReportPage /> },
      { path: "/contracts/:contractId", element: <ContractDetailPage /> },
      { path: "/practice", element: <PracticeHomePage /> },
      { path: "/practice/scenarios/:scenarioId", element: <PracticeScenarioPage /> },
      { path: "/practice/sessions/:sessionId", element: <PracticeSessionPage /> },
      { path: "/practice/sessions/:sessionId/result", element: <PracticeResultPage /> },
      {
        path: "/practice/signing",
        element: <Navigate to="/practice/scenarios/PRACTICE-DEFERRED-REFUND-001" replace />,
      },
    ],
  },
]);
