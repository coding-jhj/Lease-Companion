import { Navigate, createBrowserRouter } from "react-router-dom";
import { AnalysisProgressPage } from "./pages/analysis-progress/AnalysisProgressPage";
import { AuthPage } from "./pages/auth/AuthPage";
import { ContractCreatePage } from "./pages/contract-create/ContractCreatePage";
import { ContractSituationPage } from "./pages/contract-create/ContractSituationPage";
import { ContractDetailPage } from "./pages/contract-detail/ContractDetailPage";
import { DashboardPage } from "./pages/dashboard/DashboardPage";
import { DocumentUploadPage } from "./pages/document-upload/DocumentUploadPage";
import { ExtractionReviewPage } from "./pages/extraction-review/ExtractionReviewPage";
import { ResultReportPage } from "./pages/result-report/ResultReportPage";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "/login", element: <AuthPage mode="login" /> },
  { path: "/signup", element: <AuthPage mode="signup" /> },
  { path: "/contracts", element: <DashboardPage /> },
  { path: "/contracts/new", element: <ContractCreatePage /> },
  { path: "/contracts/:contractId/situation", element: <ContractSituationPage /> },
  { path: "/contracts/:contractId/upload", element: <DocumentUploadPage /> },
  { path: "/contracts/:contractId/review", element: <ExtractionReviewPage /> },
  { path: "/contracts/:contractId/analyzing", element: <AnalysisProgressPage /> },
  { path: "/contracts/:contractId/report", element: <ResultReportPage /> },
  { path: "/contracts/:contractId", element: <ContractDetailPage /> },
]);
