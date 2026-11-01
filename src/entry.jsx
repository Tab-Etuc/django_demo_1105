import React from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import { ReducedMotionConfig } from "@animate-ui/react/utils/motion";
import "./styles.css";
import "./plan-map.css";
import "./login-shape.css";
import "./switch-class.css";
import "./readability.css";

const App = React.lazy(() => import("./main.jsx"));
const Login = React.lazy(() => import("./components/Login.jsx").then(({ Login }) => ({ default: Login })));
const root = document.getElementById("root");

createRoot(root).render(
  <MotionConfig reducedMotion="user">
    <ReducedMotionConfig>
      <React.Suspense fallback={<main className={root.dataset.page === "login" ? "login-page" : "loading-state"} />}>
        {root.dataset.page === "login" ? <Login /> : <App />}
      </React.Suspense>
    </ReducedMotionConfig>
  </MotionConfig>,
);
