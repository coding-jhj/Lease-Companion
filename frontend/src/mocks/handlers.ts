import { delay, http, HttpResponse } from "msw";
import type { ChecklistItem, ContractSummary, ExtractedField, ReportItem } from "../types/api";

const mockContract: ContractSummary = {
  contractId: "contract-demo-001",
  title: "상도동 전세 계약",
  stage: "추출값 확인 전",
  updatedAt: "2026-07-16",
};

const extractedFields: ExtractedField[] = [
  {
    fieldName: "landlord_name",
    label: "임대인 이름",
    extractedValue: "김임대",
    userCorrectedValue: null,
    verificationStatus: "unverified",
    confidence: "추출됨",
    evidence: { page: 1, text: "임대인 김임대" },
  },
  {
    fieldName: "deposit",
    label: "보증금",
    extractedValue: "200,000,000원",
    userCorrectedValue: null,
    verificationStatus: "unverified",
    confidence: "불확실",
    evidence: { page: 1, text: "보증금 금 이억원정" },
  },
];

const report: ReportItem[] = [
  {
    judgmentId: "J01",
    title: "임대인과 등기 소유자 확인",
    status: "확인 필요",
    urgency: "계약 전 확인",
    priority: "확인 권장",
    explanation: "계약 상대방과 등기사항증명서의 소유자 이름을 함께 확인하세요.",
  },
  {
    judgmentId: "J06",
    title: "보증금 기재 상태",
    status: "명확",
    urgency: "참고",
    priority: "일반 확인",
    explanation: "보증금의 숫자 표기와 한글 표기를 다시 읽어보세요.",
  },
];

const checklist: ChecklistItem[] = [
  { id: "check-1", label: "등기사항증명서의 소유자 이름 확인", completed: false },
  { id: "check-2", label: "입금 계좌 명의 확인", completed: false },
  { id: "check-3", label: "계약서와 이체 내역 보관", completed: true },
];

export const handlers = [
  http.post("/api/auth/:mode", async ({ request }) => {
    const body = (await request.json()) as { email?: string };
    if (!body.email) {
      return HttpResponse.json(
        {
          error: {
            code: "validation_error",
            message: "입력값을 확인해 주세요.",
            details: [
              {
                loc: ["body", "email"],
                msg: "Field required",
                type: "missing",
              },
            ],
          },
        },
        { status: 422 },
      );
    }
    return HttpResponse.json({ accessToken: "mock-access-token", user: { id: "user-001", name: "김임차" } });
  }),
  http.get("/api/contracts", () => HttpResponse.json([mockContract])),
  http.post("/api/contracts", async ({ request }) => {
    const body = (await request.json()) as { title?: string };
    if (!body.title) {
      return HttpResponse.json(
        {
          error: {
            code: "validation_error",
            message: "입력값을 확인해 주세요.",
            details: [
              {
                loc: ["body", "title"],
                msg: "Field required",
                type: "missing",
              },
            ],
          },
        },
        { status: 422 },
      );
    }
    return HttpResponse.json({ ...mockContract, title: body.title }, { status: 201 });
  }),
  http.put("/api/contracts/:contractId/situation", ({ params }) =>
    HttpResponse.json({ contractId: String(params.contractId) }),
  ),
  http.post("/api/contracts/:contractId/documents", () =>
    HttpResponse.json({ documentId: "document-demo-001" }, { status: 201 }),
  ),
  http.get("/api/contracts/:contractId/extraction", () => HttpResponse.json(extractedFields)),
  http.put("/api/contracts/:contractId/extraction", () =>
    HttpResponse.json({ inputSnapshotId: "snapshot-demo-001" }),
  ),
  http.post("/api/contracts/:contractId/analyses", async () => {
    await delay(500);
    return HttpResponse.json({ analysisRunId: "analysis-demo-001" }, { status: 202 });
  }),
  http.get("/api/contracts/:contractId/report", () => HttpResponse.json(report)),
  http.get("/api/contracts/:contractId/checklist", () => HttpResponse.json(checklist)),
];
