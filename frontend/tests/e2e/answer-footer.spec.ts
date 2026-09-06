import { expect, test } from "@playwright/test";

// No inline [N] markers, so shouldRenderCitationFallback() fires and the
// Sources disclosure renders -- the state this footer group is designed for.
const ANSWER = [
  "Paragraph one. The gospel of the kingdom is an announcement before it is a",
  "doctrine, and the word kingdom carries the whole weight of it.",
  "",
  "Paragraph two. Final line of the answer prose.",
].join("\n");

const CITATIONS = [
  { chunk_id: "c1", document_title: "The Kingdom of God", author: "Derek Prince", content: "..." },
  { chunk_id: "c2", document_title: "Abide in Christ", author: "Andrew Murray", content: "..." },
];

async function metrics(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const q = <T extends Element>(s: string) => document.querySelector<T>(s);
    const footer = q<HTMLElement>("footer");
    const thumbUp = q<HTMLElement>('button[aria-label="Good answer"]');
    const thumbDown = q<HTMLElement>('button[aria-label="Bad answer"]');
    const thumbIcon = thumbUp?.querySelector("svg");
    const sourcesBtn = q<HTMLElement>('section[aria-label="Sources"] button');
    const paras = Array.from(document.querySelectorAll("p"));
    const lastPara = paras.filter((p) => p.textContent?.includes("Final line"))[0];
    if (!footer || !thumbUp || !thumbDown || !thumbIcon || !sourcesBtn || !lastPara) return null;

    // The Sources label's own glyph box, not the 44px touch target around it.
    const range = document.createRange();
    range.selectNodeContents(sourcesBtn.firstChild!);
    const sourcesText = range.getBoundingClientRect();

    return {
      answerBottom: lastPara.getBoundingClientRect().bottom,
      footerTop: footer.getBoundingClientRect().top,
      thumbTarget: thumbUp.getBoundingClientRect().toJSON(),
      thumbDownTarget: thumbDown.getBoundingClientRect().toJSON(),
      thumbIcon: thumbIcon.getBoundingClientRect().toJSON(),
      sourcesTarget: sourcesBtn.getBoundingClientRect().toJSON(),
      sourcesText: sourcesText.toJSON(),
    };
  });
}

test("the answer footer reads as one group under a clear break from the prose", async ({ page }) => {
  await page.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => route.abort());
  await page.route("**/study/teachers", (route) => route.fulfill({ json: { teachers: [] } }));
  await page.route("**/study/pins", (route) => route.fulfill({ json: { pins: [] } }));
  await page.route("**/async-chat/submit", (route) => route.fulfill({ json: { job_id: "job-1" } }));
  await page.route("**/async-chat/result/**", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body:
        `data: ${JSON.stringify({
          answer: ANSWER,
          citations: CITATIONS,
          conversation_id: null,
          message_id: "m1",
          verified_references: [],
          quote_ids: [],
        })}\n\n` + "data: [DONE]\n\n",
    }),
  );

  await page.goto("/");
  const textarea = page.getByLabel("Ask a question about Scripture or theology");
  const send = page.getByRole("button", { name: "Send message" });
  await expect
    .poll(async () => {
      await textarea.fill("What is the gospel?");
      return send.isEnabled();
    }, { timeout: 15_000 })
    .toBe(true);
  await send.click();

  await expect(page.getByText("Final line of the answer prose.")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /^Sources \(2\)/ })).toBeVisible();

  const m = await metrics(page);
  expect(m).not.toBeNull();

  const contentBreak = m!.footerTop - m!.answerBottom;
  const opticalGap = m!.sourcesText.top - m!.thumbIcon.bottom;

  // The spec's rhythm: the larger separation is between the answer and the
  // footer group, the tighter one between the group's own two rows. Before
  // this work the group did not exist -- Sources sat above, feedback dangled
  // below it -- and a naive stack inverted the rhythm at 24 vs 27px, because
  // two 44px touch targets stack 26px of unpainted padding between a 16px
  // icon and a text label.
  expect(opticalGap).toBeLessThan(contentBreak);
  expect(opticalGap).toBeGreaterThan(4);
  expect(contentBreak).toBeGreaterThanOrEqual(20);

  // Own rows, sharing a left edge -- never opposite each other in one row.
  expect(m!.thumbTarget.left).toBe(m!.sourcesTarget.left);
  expect(m!.thumbDownTarget.top).toBe(m!.thumbTarget.top);
  expect(m!.sourcesTarget.top).toBeGreaterThan(m!.thumbTarget.top);
  expect(m!.sourcesText.top).toBeGreaterThanOrEqual(m!.thumbIcon.bottom);

  // Touch targets survive the optical correction. The rows overlap only where
  // both are padding; what the pointer can still reach on the thumb stays
  // past the 24px WCAG 2.5.8 AA floor.
  expect(m!.thumbTarget.width).toBeGreaterThanOrEqual(44);
  expect(m!.thumbTarget.height).toBeGreaterThanOrEqual(44);
  expect(m!.sourcesTarget.height).toBeGreaterThanOrEqual(44);
  const reachableThumb = m!.sourcesTarget.top - m!.thumbTarget.top;
  expect(reachableThumb).toBeGreaterThanOrEqual(24);
  expect(m!.thumbIcon.bottom).toBeLessThanOrEqual(m!.sourcesTarget.top);

  // Expanded, the citation rows span the message rather than shrinking to the
  // section's content width.
  await page.getByRole("button", { name: /^Sources \(2\)/ }).click();
  const widths = await page.evaluate(() => {
    const row = document.querySelector('section[aria-label="Sources"] .mt-2 button');
    const para = Array.from(document.querySelectorAll("p"))
      .filter((p) => p.textContent?.includes("Final line"))[0];
    return { row: row!.getBoundingClientRect().width, para: para.getBoundingClientRect().width };
  });
  expect(widths.row).toBe(widths.para);
});

test("an answer with working inline citations still gets the footer, without a Sources row", async ({ page }) => {
  await page.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => route.abort());
  await page.route("**/study/teachers", (route) => route.fulfill({ json: { teachers: [] } }));
  await page.route("**/study/pins", (route) => route.fulfill({ json: { pins: [] } }));
  await page.route("**/async-chat/submit", (route) => route.fulfill({ json: { job_id: "job-2" } }));
  await page.route("**/async-chat/result/**", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body:
        `data: ${JSON.stringify({
          answer: "Paragraph two. Final line of the answer prose. [1] [2]",
          citations: CITATIONS,
          conversation_id: null,
          message_id: "m2",
          verified_references: [],
          quote_ids: [],
        })}\n\n` + "data: [DONE]\n\n",
    }),
  );

  await page.goto("/");
  const textarea = page.getByLabel("Ask a question about Scripture or theology");
  const send = page.getByRole("button", { name: "Send message" });
  await expect
    .poll(async () => {
      await textarea.fill("What is the gospel?");
      return send.isEnabled();
    }, { timeout: 15_000 })
    .toBe(true);
  await send.click();

  await expect(page.getByText(/Final line of the answer prose/)).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('button[aria-label="Good answer"]')).toBeVisible();
  await expect(page.locator('section[aria-label="Sources"]')).toHaveCount(0);
});
