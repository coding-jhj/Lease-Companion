import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { AUTH_UNAUTHORIZED_EVENT } from "./services/authToken";

export function App() {
  useEffect(() => {
    const redirectToLogin = () => void router.navigate("/login", { replace: true });
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, redirectToLogin);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, redirectToLogin);
  }, []);

  return <RouterProvider router={router} />;
}
