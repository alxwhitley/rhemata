# Answer-level sermon exposure audit — 2026-09-05

Stage 3 of `docs/superpowers/specs/2026-09-04-sermon-passage-quality-design.md`,
the gate that `docs/roadmap.md` puts in front of any filter, down-weight, or
model-scored quality gate on sermon passages.

Read-only. No database write, no model call, no deploy. The question it answers:
**do kill-grade sermon passages reach served answers, and when they do, is the
answer materially worse?**

## Answer

Exposure is real but uncommon, and measured harm is zero.

| Measure | Value |
|---|---|
| Distinct question groups | **50** (across 76 answer jobs) |
| Groups where a kill-grade **chunk** was retrieved | **6 / 50 — 12%** |
| Of those, reached top 8 | **6 / 6** (positions 2, 3, 4, 4, 4, 7) |
| Groups where a kill passage's **document** was retrieved | 8 / 50 — 16% |
| Groups where a kill-grade chunk was **cited in a served answer** | **3 / 50 — 6%** |
| Of those, **materially degraded** the answer | **0 / 3** |
| Theological errors found | **0** |
| Teacher misrepresentations found | **0** |

Top-8 is a real discriminator here, not an artifact: `retrieved_chunk_ids`
holds up to 29 candidates (mean 13.0), so a passage can be retrieved and miss
the top 8. Every kill-grade retrieval in this population landed inside it.

Of the 6 exposed groups: 3 cited the passage, 1 returned
`refused_attribution` so no answer was served at all, and 2 retrieved it
without citing it.

## The three cited cases, checked claim by claim

**1. "What does it mean to walk in the fear of the Lord day by day?"** —
passage #16, Shabaka Williams, CLF Church, cited at retrieval position 4.
**The speaker is never named anywhere in the answer prose.** Nothing is
attributed to him, so misrepresentation is not possible; the passage's
contribution is diffuse and unattributed.

**2. "How to hear God?"** — passage #6, Josh Fisher, CLF Church, cited twice.
The answer attributes specific claims to Fisher by name. Each was checked
against the stored passage:

- "God's spoken word never contradicts His written word" — the passage says
  *"his rama never contradicts the logos… The spoken word of God never
  contradicts the word of God."* **Supported.**
- "submitting impressions to Scripture and to trusted community rather than
  asserting 'God told me'" — the passage says *"not using definitives… it's
  not coming with the God told me card"* and *"submit what God's saying to us,
  to our pastors, to our leaders, to our community."* **Supported.**
- "delayed or casual obedience dulls spiritual sensitivity over time" — a mild
  inversion of the passage's *"when we cultivate a practice of hearing him on
  the small things and being obedient… it becomes significantly easier."*
  **Defensible paraphrase**, slightly stronger than the source.

Worth recording: this passage contains the caption artifacts `>>` and the
mistranscription *"rama"* for *rhema*. The answer rendered the concept
correctly and repeated neither artifact.

**3. "What does it mean for believers to reign with Christ…?"** — passage #13,
Zac Poonen, cited at position 7. The answer attributes four specifics to
Poonen. The sampled chunk contains only one of them, which initially reads as
fabrication. It is not: the answer drew on 12 chunks, and the rest are grounded
in **a different Poonen document** in the same retrieval
(*Study Scripture Carefully*).

- Hebrews 2:14 — the passage has *"Hebrews in chapter 2. Verse 14… he made the
  devil powerless."* **Supported** (a literal `Hebrews 2:14` string search
  misses this; the spoken form is what is stored).
- authority requires submission — passage: *"this is the reason why many
  Christians don't have authority in their life."* **Supported.**
- the centurion / Matthew 8 — **supported**, in the second Poonen document.
- "thirty years" under authority — **supported**; the evidence says
  *"30 years"* and the model spelled it out.

Method note, because it nearly produced a wrong finding twice: a claim absent
from the graded chunk is not fabricated until the whole retrieved set has been
searched, in the phrasings the corpus actually uses. Both a literal
`Hebrews 2:14` and a literal `thirty years` returned false negatives.

## Limits — read before treating 12% as a point estimate

1. **12% is a floor, not an estimate.** 65 of the 635 chunk ids referenced by
   answer jobs (10%) no longer exist, and 30 of 72 jobs reference at least one
   deleted chunk. Where a kill passage's chunk was deleted and rebuilt, its
   historical exposure is invisible to an id match. The design doc marks
   passages #15 (Jack Deere) and #18 (Ravenhill) as rebuilt, so those two
   cannot be measured historically at all.
2. **The roadmap says "20 distinct question groups"; the live data has 50
   across 76 jobs.** The 20 appears to describe the questions represented in
   the 30-passage sample, not the job population. This audit uses all 50, which
   is the larger and more conservative denominator.
3. **This measures the corpus as it is now**, after the 2026-09-04 rebuild
   improved 79 documents. Historical harm may have been higher and is not
   recoverable from this data.
4. Passage #19 (Robert Trail, borderline) could not be located in the corpus by
   text match, though its document still exists. 9 of the 10 graded
   kill/borderline passages were located; all 8 kill-grade ones were.
5. Harm was judged by reading three answers against their evidence. That is a
   small numerator. It is enough to say no error was found; it is not enough to
   put a tight bound on a rate.

## Recommendation

**Do not build the filter.** Kill-grade passages reach the top 8 in 12% of
question groups and are cited in 6%, and in every cited case the served answer
was faithful to the evidence. The two failure modes the roadmap names as
promotion-worthy — theological error and teacher misrepresentation — did not
occur. Stages 4 and 5 (calibration set, classifier, mechanism comparison) are
substantial work against a harm rate measured at zero.

The finding underneath the number is that passage quality and answer quality
are not the same thing. These passages were graded unreadable as prose; the
answer path summarised them accurately anyway, discarding caption artifacts and
a mistranscribed word along the way.

If Alex prefers a cheaper safeguard than a classifier, the one intervention
this evidence would support is on **attribution rather than quality**: case 1
cited a CLF passage while never naming its speaker. That is the surface where a
weak passage could quietly influence prose with no attributable owner.

Per the roadmap's stop condition, work stops here until Alex makes the
filter/no-filter decision.
