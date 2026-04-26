"use client";

import { create } from "zustand";

import type { Brief, EvidenceCard, Judgement } from "@/lib/types";

interface DrawerState {
  open: boolean;
  judgementId: string | null;
  triggerElementId: string | null;
  highlightedEvidenceId: string | null;
}

interface UploadDrawerState {
  open: boolean;
  fileId: string | null;
}

interface DemoEvidenceModalState {
  open: boolean;
  card: EvidenceCard | null;
  kind: "internal_demo" | "internal_research" | null;
}

interface ReviewModalState {
  open: boolean;
  judgementId: string | null;
}

interface EvidenceTrailDrawerState {
  open: boolean;
}

interface AppState {
  brief: Brief | null;
  drawer: DrawerState;
  uploadDrawer: UploadDrawerState;
  demoEvidenceModal: DemoEvidenceModalState;
  reviewModal: ReviewModalState;
  evidenceTrailDrawer: EvidenceTrailDrawerState;
  /** Last 3 QA turns for the active drawer scope */
  qaHistory: { question: string; answer: string }[];
  setBrief: (brief: Brief) => void;
  openDrawer: (
    judgementId: string,
    options?: { triggerElementId?: string; highlightEvidenceId?: string }
  ) => void;
  setHighlightedEvidence: (evidenceId: string | null) => void;
  closeDrawer: () => void;
  openUpload: (fileId?: string) => void;
  closeUpload: () => void;
  openDemoEvidenceModal: (
    card: EvidenceCard,
    kind: "internal_demo" | "internal_research"
  ) => void;
  closeDemoEvidenceModal: () => void;
  openReviewModal: (judgementId: string) => void;
  closeReviewModal: () => void;
  openEvidenceTrailDrawer: () => void;
  closeEvidenceTrailDrawer: () => void;
  pushQa: (turn: { question: string; answer: string }) => void;
  clearQa: () => void;
  getJudgement: (id: string) => Judgement | undefined;
}

export const useAppStore = create<AppState>((set, get) => ({
  brief: null,
  drawer: { open: false, judgementId: null, triggerElementId: null, highlightedEvidenceId: null },
  uploadDrawer: { open: false, fileId: null },
  demoEvidenceModal: { open: false, card: null, kind: null },
  reviewModal: { open: false, judgementId: null },
  evidenceTrailDrawer: { open: false },
  qaHistory: [],
  setBrief: (brief) => set({ brief }),
  openDrawer: (judgementId, options) =>
    set({
      drawer: {
        open: true,
        judgementId,
        triggerElementId: options?.triggerElementId ?? null,
        highlightedEvidenceId: options?.highlightEvidenceId ?? null,
      },
      qaHistory: [],
    }),
  setHighlightedEvidence: (evidenceId) =>
    set((state) => ({
      drawer: { ...state.drawer, highlightedEvidenceId: evidenceId },
    })),
  closeDrawer: () =>
    set({
      drawer: { open: false, judgementId: null, triggerElementId: null, highlightedEvidenceId: null },
      qaHistory: [],
    }),
  openUpload: (fileId) => set({ uploadDrawer: { open: true, fileId: fileId ?? null } }),
  closeUpload: () => set({ uploadDrawer: { open: false, fileId: null } }),
  openDemoEvidenceModal: (card, kind) =>
    set({ demoEvidenceModal: { open: true, card, kind } }),
  closeDemoEvidenceModal: () =>
    set({ demoEvidenceModal: { open: false, card: null, kind: null } }),
  openReviewModal: (judgementId) =>
    set({ reviewModal: { open: true, judgementId } }),
  closeReviewModal: () =>
    set({ reviewModal: { open: false, judgementId: null } }),
  openEvidenceTrailDrawer: () =>
    set({ evidenceTrailDrawer: { open: true } }),
  closeEvidenceTrailDrawer: () =>
    set({ evidenceTrailDrawer: { open: false } }),
  pushQa: (turn) =>
    set((state) => ({
      qaHistory: [...state.qaHistory.slice(-2), turn],
    })),
  clearQa: () => set({ qaHistory: [] }),
  getJudgement: (id) => get().brief?.judgements.find((j) => j.id === id),
}));
