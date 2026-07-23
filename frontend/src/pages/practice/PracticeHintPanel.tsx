import { useState } from "react";

export function PracticeHintPanel({ guide, prompt }: { guide: string; prompt: string }) {
  const [step, setStep] = useState(1);

  return (
    <section className="practice-hint-panel" aria-label="말할 내용 힌트">
      <div><strong>방향</strong><p>{guide}</p></div>
      {step >= 2 && <div><strong>확인 대상</strong><p>{prompt}</p></div>}
      {step >= 3 && <div><strong>예시 문장</strong><p>바로 결정하기 전에 필요한 내용을 확인하겠습니다.</p></div>}
      {step < 3 && <button type="button" className="secondary" onClick={() => setStep((current) => current + 1)}>다음 힌트</button>}
    </section>
  );
}
