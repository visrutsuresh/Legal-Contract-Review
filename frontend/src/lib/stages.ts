// stage keys written by the graph (Task 30) -> the docket's narrated lines
export const STAGE_LINES: Record<string, string> = {
  reading: "Reading the document…",
  extracting: "Finding the clauses…",
  inspecting:
    "Four checks are reading every clause: law, risk, your standard, the money terms…",
  negotiating: "Thinking through negotiation angles…",
  summarising: "Writing the plain-English report…",
  done: "Wrapping up…",
};

// the pipeline's stages in the order they run, so the UI can show "step 3 of 6"
export const STAGE_ORDER = [
  "reading",
  "extracting",
  "inspecting",
  "negotiating",
  "summarising",
  "done",
];
