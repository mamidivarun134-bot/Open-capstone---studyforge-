# StudyForge — Responsible AI

## Limitations

- **StudyForge is grounded in the student's uploaded materials, not a fact-checked source of truth about the world.** If the uploaded document itself contains an error, StudyForge will faithfully reproduce that error rather than correcting it. This is a deliberate design choice (answer from what was taught, not from general internet knowledge) but is also a real limitation students should understand.
- **Retrieval is lexical (TF-IDF), not semantic.** A question that paraphrases the source material using entirely different vocabulary may retrieve nothing relevant, even though the answer exists in the document. The system is honest about this: when retrieval finds nothing, it says so rather than guessing.
- **The extractive fallback (used when no LLM API key is configured) produces lower-quality quiz questions** — simple fill-in-the-blank rather than genuinely tests of understanding. This is disclosed to the user via the `generation_method` field, not hidden.
- **OCR accuracy on low-quality scans is imperfect.** Handwritten notes or heavily stylized slide fonts may produce garbled extracted text, which will degrade both retrieval and question quality for those pages.
- **Mastery scores are a simple heuristic (EMA of correctness + recency), not a validated psychometric model.** They should be read as a directional study aid ("you're weaker here than there"), not as a certified measurement of learning.

## Possible biases

- **Topic clustering (KMeans over TF-IDF) can produce uneven or oddly-named topics** for documents with unusual structure (e.g. a document that's 90% one subject and 10% a tangent may absorb the tangent into a larger cluster rather than surfacing it as its own topic).
- **Documents with more pages get proportionally more quiz coverage** simply because they produce more chunks — the system does not currently weight topics by importance, only by mastery and recency.
- **English-language tooling assumption:** the TF-IDF vectorizer uses English stop words by default; retrieval quality for non-English documents will degrade unless this is reconfigured.

## Hallucination risks

- When an LLM is configured, it is instructed to answer only from retrieved excerpts and to say when it cannot — but instruction-following is not a guarantee. Students should treat citations as a way to *verify* an answer, not as proof the answer is automatically correct.
- The system does not currently run a separate verification/groundedness-checking pass on LLM answers before showing them to the student (see `docs/EVALUATION.md` for how this is manually spot-checked instead, and `docs/ARCHITECTURE.md`'s "Future Improvements" for where an automated verifier agent would fit).

## Privacy concerns

- Uploaded documents may contain personal or sensitive course material. Documents and derived data (chunks, embeddings) are stored per-user and are not currently deleted automatically; a "delete my data" flow is not yet implemented (documented gap, not a claim of automatic compliance with any specific privacy regulation).
- No content is sent to Anthropic's API unless `ANTHROPIC_API_KEY` is configured, and only the specific retrieved excerpts (not the full document) are sent per request.

## Human-in-the-loop requirements

- StudyForge is a study aid, not a substitute for instructor feedback or grading. It should not be used as the sole basis for high-stakes assessment decisions.
- Students should be encouraged to verify important answers against the cited source excerpt themselves, especially before using StudyForge's output in graded work.

## Appropriate usage

- Self-study and review from a student's own legitimately obtained course materials.
- Generating low-stakes practice quizzes to identify weak areas.
- Getting a quick, grounded answer to "what did my notes say about X" without re-reading the whole document.

## Inappropriate usage

- Treating StudyForge's answers as authoritative fact-checked information independent of the uploaded source.
- Uploading copyrighted material the student does not have the right to use for this purpose, or sharing another person's private notes without consent.
- Using generated quiz content as an official graded assessment without instructor review.
- Relying on it as the sole preparation for a high-stakes exam without cross-referencing other sources.

**StudyForge does not claim to be perfect, unbiased, or a replacement for human instruction.** It is designed to degrade gracefully and disclose its limitations (via `generation_method`, "no match" responses, and this document) rather than mask them.
