import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { DebugLogOverlay } from "./components/debug/DebugLogOverlay";
import { router } from "./router";
import { AUTH_UNAUTHORIZED_EVENT } from "./services/authToken";

export function App() {
  useEffect(() => {
    const redirectToLogin = () => void router.navigate("/login", { replace: true });
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, redirectToLogin);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, redirectToLogin);
  }, []);

  return (
    <>
      <RouterProvider router={router} />
      {/* `?debug=1`일 때만 렌더링된다. 계약 점검·연습 모든 화면에서 쓴다. */}
      <DebugLogOverlay />
    </>
  );
}
