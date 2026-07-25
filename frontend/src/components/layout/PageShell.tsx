import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearAccessToken } from "../../services/authToken";

interface JourneyDisplay {
  current: number;
  currentLabel: string;
  nextLabel?: string;
}

interface PageShellProps {
  step: string;
  journey?: JourneyDisplay;
  title: string;
  description: string;
  children: ReactNode;
  showLogout?: boolean;
  showJourney?: boolean;
  layout?: "auth" | "default" | "narrow" | "workspace" | "report";
  eyebrow?: string;
  hero?: ReactNode;
}

const journeySteps = ["시작 방법", "집 등록", "상황 입력", "문서 준비", "내용 확인", "결과 준비", "확인 결과", "다음 행동"];

// 지나온 단계로 돌아갈 주소. 6단계(결과 준비)는 분석 실행 화면이라 되돌아가지 않는다.
function stepPath(step: number, contractId: string | null): string | null {
  if (step === 1) return "/choose-mode";
  if (step === 2) return "/contracts";
  if (!contractId) return null;
  if (step === 3) return `/contracts/${contractId}/situation`;
  if (step === 4) return `/contracts/${contractId}/upload`;
  if (step === 5) return `/contracts/${contractId}/review`;
  if (step === 7) return `/contracts/${contractId}/report`;
  if (step === 8) return `/contracts/${contractId}`;
  return null;
}
// 아이콘 path = Phosphor Icons (MIT License) — duotone.
const journeyIconPaths: ReactNode[] = [
  <><path d="M128,32a96,96,0,1,0,96,96A96,96,0,0,0,128,32Zm16,112L80,176l32-64,64-32Z" opacity="0.2" /><path d="M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm0,192a88,88,0,1,1,88-88A88.1,88.1,0,0,1,128,216ZM172.42,72.84l-64,32a8.05,8.05,0,0,0-3.58,3.58l-32,64A8,8,0,0,0,80,184a8.1,8.1,0,0,0,3.58-.84l64-32a8.05,8.05,0,0,0,3.58-3.58l32-64a8,8,0,0,0-10.74-10.74ZM138,138,97.89,158.11,118,118l40.15-20.07Z" /></>, // 시작 방법 — compass
  <><path d="M216,120v96H152V152H104v64H40V120a8,8,0,0,1,2.34-5.66l80-80a8,8,0,0,1,11.32,0l80,80A8,8,0,0,1,216,120Z" opacity="0.2" /><path d="M219.31,108.68l-80-80a16,16,0,0,0-22.62,0l-80,80A15.87,15.87,0,0,0,32,120v96a8,8,0,0,0,8,8h64a8,8,0,0,0,8-8V160h32v56a8,8,0,0,0,8,8h64a8,8,0,0,0,8-8V120A15.87,15.87,0,0,0,219.31,108.68ZM208,208H160V152a8,8,0,0,0-8-8H104a8,8,0,0,0-8,8v56H48V120l80-80,80,80Z" /></>, // 집 등록 — house
  <><path d="M200,88l-72,72H96V128l72-72Z" opacity="0.2" /><path d="M229.66,58.34l-32-32a8,8,0,0,0-11.32,0l-96,96A8,8,0,0,0,88,128v32a8,8,0,0,0,8,8h32a8,8,0,0,0,5.66-2.34l96-96A8,8,0,0,0,229.66,58.34ZM124.69,152H104V131.31l64-64L188.69,88ZM200,76.69,179.31,56,192,43.31,212.69,64ZM224,128v80a16,16,0,0,1-16,16H48a16,16,0,0,1-16-16V48A16,16,0,0,1,48,32h80a8,8,0,0,1,0,16H48V208H208V128a8,8,0,0,1,16,0Z" /></>, // 상황 입력 — note-pencil
  <><path d="M208,88H152V32Z" opacity="0.2" /><path d="M213.66,82.34l-56-56A8,8,0,0,0,152,24H56A16,16,0,0,0,40,40V216a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V88A8,8,0,0,0,213.66,82.34ZM160,51.31,188.69,80H160ZM200,216H56V40h88V88a8,8,0,0,0,8,8h48V216Zm-32-80a8,8,0,0,1-8,8H96a8,8,0,0,1,0-16h64A8,8,0,0,1,168,136Zm0,32a8,8,0,0,1-8,8H96a8,8,0,0,1,0-16h64A8,8,0,0,1,168,168Z" /></>, // 문서 준비 — file-text
  <><path d="M192,112a80,80,0,1,1-80-80A80,80,0,0,1,192,112Z" opacity="0.2" /><path d="M229.66,218.34,179.6,168.28a88.21,88.21,0,1,0-11.32,11.31l50.06,50.07a8,8,0,0,0,11.32-11.32ZM40,112a72,72,0,1,1,72,72A72.08,72.08,0,0,1,40,112Z" /></>, // 내용 확인 — magnifying-glass
  <><path d="M208,48V216a8,8,0,0,1-8,8H56a8,8,0,0,1-8-8V48a8,8,0,0,1,8-8H96a39.83,39.83,0,0,0-8,24v8h80V64a39.83,39.83,0,0,0-8-24h40A8,8,0,0,1,208,48Z" opacity="0.2" /><path d="M168,152a8,8,0,0,1-8,8H96a8,8,0,0,1,0-16h64A8,8,0,0,1,168,152Zm-8-40H96a8,8,0,0,0,0,16h64a8,8,0,0,0,0-16Zm56-64V216a16,16,0,0,1-16,16H56a16,16,0,0,1-16-16V48A16,16,0,0,1,56,32H92.26a47.92,47.92,0,0,1,71.48,0H200A16,16,0,0,1,216,48ZM96,64h64a32,32,0,0,0-64,0ZM200,48H173.25A47.93,47.93,0,0,1,176,64v8a8,8,0,0,1-8,8H88a8,8,0,0,1-8-8V64a47.93,47.93,0,0,1,2.75-16H56V216H200Z" /></>, // 결과 준비 — clipboard-text
  <><path d="M232,128c0,12.51-17.82,21.95-22.68,33.69-4.68,11.32,1.42,30.65-7.78,39.85s-28.53,3.1-39.85,7.78C150,214.18,140.5,232,128,232s-22-17.82-33.69-22.68c-11.32-4.68-30.65,1.42-39.85-7.78s-3.1-28.53-7.78-39.85C41.82,150,24,140.5,24,128s17.82-22,22.68-33.69C51.36,83,45.26,63.66,54.46,54.46S83,51.36,94.31,46.68C106.05,41.82,115.5,24,128,24S150,41.82,161.69,46.68c11.32,4.68,30.65-1.42,39.85,7.78s3.1,28.53,7.78,39.85C214.18,106.05,232,115.5,232,128Z" opacity="0.2" /><path d="M225.86,102.82c-3.77-3.94-7.67-8-9.14-11.57-1.36-3.27-1.44-8.69-1.52-13.94-.15-9.76-.31-20.82-8-28.51s-18.75-7.85-28.51-8c-5.25-.08-10.67-.16-13.94-1.52-3.56-1.47-7.63-5.37-11.57-9.14C146.28,23.51,138.44,16,128,16s-18.27,7.51-25.18,14.14c-3.94,3.77-8,7.67-11.57,9.14C88,40.64,82.56,40.72,77.31,40.8c-9.76.15-20.82.31-28.51,8S41,67.55,40.8,77.31c-.08,5.25-.16,10.67-1.52,13.94-1.47,3.56-5.37,7.63-9.14,11.57C23.51,109.72,16,117.56,16,128s7.51,18.27,14.14,25.18c3.77,3.94,7.67,8,9.14,11.57,1.36,3.27,1.44,8.69,1.52,13.94.15,9.76.31,20.82,8,28.51s18.75,7.85,28.51,8c5.25.08,10.67.16,13.94,1.52,3.56,1.47,7.63,5.37,11.57,9.14C109.72,232.49,117.56,240,128,240s18.27-7.51,25.18-14.14c3.94-3.77,8-7.67,11.57-9.14,3.27-1.36,8.69-1.44,13.94-1.52,9.76-.15,20.82-.31,28.51-8s7.85-18.75,8-28.51c.08-5.25.16-10.67,1.52-13.94,1.47-3.56,5.37-7.63,9.14-11.57C232.49,146.28,240,138.44,240,128S232.49,109.73,225.86,102.82Zm-11.55,39.29c-4.79,5-9.75,10.17-12.38,16.52-2.52,6.1-2.63,13.07-2.73,19.82-.1,7-.21,14.33-3.32,17.43s-10.39,3.22-17.43,3.32c-6.75.1-13.72.21-19.82,2.73-6.35,2.63-11.52,7.59-16.52,12.38S132,224,128,224s-9.15-4.92-14.11-9.69-10.17-9.75-16.52-12.38c-6.1-2.52-13.07-2.63-19.82-2.73-7-.1-14.33-.21-17.43-3.32s-3.22-10.39-3.32-17.43c-.1-6.75-.21-13.72-2.73-19.82-2.63-6.35-7.59-11.52-12.38-16.52S32,132,32,128s4.92-9.15,9.69-14.11,9.75-10.17,12.38-16.52c2.52-6.1,2.63-13.07,2.73-19.82.1-7,.21-14.33,3.32-17.43S70.51,56.9,77.55,56.8c6.75-.1,13.72-.21,19.82-2.73,6.35-2.63,11.52-7.59,16.52-12.38S124,32,128,32s9.15,4.92,14.11,9.69,10.17,9.75,16.52,12.38c6.1,2.52,13.07,2.63,19.82,2.73,7,.1,14.33.21,17.43,3.32s3.22,10.39,3.32,17.43c.1,6.75.21,13.72,2.73,19.82,2.63,6.35,7.59,11.52,12.38,16.52S224,124,224,128,219.08,137.15,214.31,142.11ZM173.66,98.34a8,8,0,0,1,0,11.32l-56,56a8,8,0,0,1-11.32,0l-24-24a8,8,0,0,1,11.32-11.32L112,148.69l50.34-50.35A8,8,0,0,1,173.66,98.34Z" /></>, // 확인 결과 — seal-check
  <><path d="M224,128a96,96,0,1,1-96-96A96,96,0,0,1,224,128Z" opacity="0.2" /><path d="M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm0,192a88,88,0,1,1,88-88A88.1,88.1,0,0,1,128,216Zm45.66-93.66a8,8,0,0,1,0,11.32l-32,32a8,8,0,0,1-11.32-11.32L148.69,136H88a8,8,0,0,1,0-16h60.69l-18.35-18.34a8,8,0,0,1,11.32-11.32Z" /></>, // 다음 행동 — arrow-circle-right
];

function JourneyIcon({ index, className }: { index: number; className: string }) {
  return (
    <svg className={className} viewBox="0 0 256 256" fill="currentColor" aria-hidden="true">
      {journeyIconPaths[index]}
    </svg>
  );
}

export function PageShell({
  step,
  journey,
  title,
  description,
  children,
  showLogout = true,
  showJourney = true,
  layout = "default",
  eyebrow = "첫 계약 확인 도우미",
  hero,
}: PageShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const currentStep = journey?.current ?? Number(step.split("/")[0].trim());
  const validStep = Number.isInteger(currentStep) && currentStep >= 1 && currentStep <= journeySteps.length;
  const currentLabel = journey?.currentLabel ?? journeySteps[currentStep - 1];
  const nextLabel = journey?.nextLabel ?? journeySteps[currentStep];
  const showModeSelect = showLogout && location.pathname !== "/choose-mode";
  const contractId = location.pathname.match(/\/contracts\/(\d+)/)?.[1] ?? null;
  // 6단계(결과 준비)처럼 되돌아갈 수 없는 단계는 건너뛰고 그 앞 단계를 찾는다.
  // 건너뛰지 않으면 7단계에서 "이전 단계" 버튼이 사라진다.
  const previousPath = (() => {
    if (!validStep) return null;
    for (let step = currentStep - 1; step >= 1; step -= 1) {
      const path = stepPath(step, contractId);
      if (path) return path;
    }
    return null;
  })();
  const currentStepRef = useRef<HTMLDivElement | null>(null);
  const [showFullJourney, setShowFullJourney] = useState(false);

  // 8단계로 늘어난 진행 표시가 좁은 화면에서 가로로 넘칠 때, 현재 단계가 화면 밖에
  // 숨지 않도록 진행 표시 안에서만 가로 스크롤한다. 포커스는 옮기지 않는다.
  useEffect(() => {
    const element = currentStepRef.current;
    if (!element || typeof element.scrollIntoView !== "function") return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    try {
      element.scrollIntoView({
        block: "nearest",
        inline: "center",
        behavior: reduceMotion ? "auto" : "smooth",
      });
    } catch {
      // jsdom 등 scrollIntoView 미구현 환경은 무시한다.
    }
  }, [currentStep, showFullJourney]);

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [location.pathname]);

  function logout() {
    clearAccessToken();
    navigate("/login", { replace: true });
  }

  const journeyMap = (
    <nav className="journey-map" aria-label="계약 확인 진행 단계">
      {journeySteps.map((label, index) => {
        const number = index + 1;
        const state = number === currentStep ? "current" : number < currentStep ? "complete" : "upcoming";
        const className = `journey-step journey-step--${state}`;
        const body = (
          <>
            <span>{state === "complete" ? "✓" : number}</span>
            <JourneyIcon index={index} className="journey-step__icon" />
            <small>{label}</small>
            <em className="journey-step__status">{state === "complete" ? "완료" : state === "current" ? "진행 중" : "예정"}</em>
          </>
        );
        // 지나온 단계만 돌아갈 수 있게 링크로 만든다. 현재·예정 단계는 그대로 둔다.
        const path = state === "complete" ? stepPath(number, contractId) : null;
        if (path) {
          return (
            <Link className={`${className} journey-step--link`} to={path} key={label}>{body}</Link>
          );
        }
        return (
          <div className={className} ref={state === "current" ? currentStepRef : undefined} aria-current={state === "current" ? "step" : undefined} key={label}>
            {body}
          </div>
        );
      })}
    </nav>
  );

  return (
    <main className={`app-shell app-shell--${layout}`}>
      <header className="app-header">
        <Link className="brand" to="/contracts">
          <span className="brand__mark" aria-hidden="true">
            {/* Phosphor Icons (MIT) — house-duotone */}
            <svg viewBox="0 0 256 256" width="19" height="19" fill="currentColor">
              <path d="M216,120v96H152V152H104v64H40V120a8,8,0,0,1,2.34-5.66l80-80a8,8,0,0,1,11.32,0l80,80A8,8,0,0,1,216,120Z" opacity="0.2" />
              <path d="M219.31,108.68l-80-80a16,16,0,0,0-22.62,0l-80,80A15.87,15.87,0,0,0,32,120v96a8,8,0,0,0,8,8h64a8,8,0,0,0,8-8V160h32v56a8,8,0,0,0,8,8h64a8,8,0,0,0,8-8V120A15.87,15.87,0,0,0,219.31,108.68ZM208,208H160V152a8,8,0,0,0-8-8H104a8,8,0,0,0-8,8v56H48V120l80-80,80,80Z" />
            </svg>
          </span>
          <span className="brand__name">슬기로운 계약생활</span>
        </Link>
        <div className="header-actions">
          <span className="step-badge">{step}</span>
          {showModeSelect && <Link className="mode-switch-link" to="/choose-mode">처음으로</Link>}
          {showLogout && <button className="logout-button" type="button" onClick={logout}>로그아웃</button>}
        </div>
      </header>
      {showJourney && validStep && (
        <div className="journey-progress">
          <div
            className="journey-progress__track"
            role="progressbar"
            aria-valuemin={1}
            aria-valuemax={journeySteps.length}
            aria-valuenow={currentStep}
            aria-label={`계약 확인 진행 ${currentStep} / ${journeySteps.length}단계 · ${currentLabel}`}
          >
            <div className="journey-progress__fill" style={{ width: `${(currentStep / journeySteps.length) * 100}%` }} />
          </div>
          <div className="journey-progress__row">
            {previousPath && (
              <Link className="journey-progress__back" to={previousPath}>
                <span aria-hidden="true">←</span> 이전 단계
              </Link>
            )}
            <p className="journey-progress__head">
              <JourneyIcon index={currentStep - 1} className="journey-progress__icon" />
              <span className="journey-progress__kicker">{`${currentStep}/${journeySteps.length}단계`}</span>
              <strong className="journey-progress__title">{currentLabel}</strong>
            </p>
            <div className="journey-progress__meta">
              {nextLabel && <span className="journey-progress__next">{`다음: ${nextLabel}`}</span>}
              <button
                aria-controls="full-journey"
                aria-expanded={showFullJourney}
                aria-label={showFullJourney ? "전체 과정 접기" : "전체 과정 보기"}
                className="journey-progress__toggle"
                type="button"
                onClick={() => setShowFullJourney((isOpen) => !isOpen)}
              >
                {showFullJourney ? "접기" : "전체"}
              </button>
            </div>
          </div>
          {showFullJourney && <div className="journey-progress__full" id="full-journey">{journeyMap}</div>}
        </div>
      )}
      {hero ? (
        <section className="page-card page-card--split">
          <div className="auth-hero">{hero}</div>
          <div className="auth-form-panel">
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p className="description">{description}</p>
            {children}
          </div>
        </section>
      ) : (
        <section className="page-card">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="description">{description}</p>
          {children}
        </section>
      )}
    </main>
  );
}
