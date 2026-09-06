import { expect, test } from "@playwright/test";

/**
 * Regression test for the standalone /study word-search path.
 *
 * `handleWordStudySelect` has fetched the word-study article into
 * `wordStudyContent` since 40cdb4c, but `WordStudyPanel` never received it,
 * so picking a word from the search dropdown rendered a definition and no
 * article. CLAUDE.md's Landmines entry records this as accidental, unlike the
 * two deliberate Study Panel decisions beside it.
 *
 * Reverting the `content`/`loading` props on WordStudyPanel fails this test.
 */

const STRONGS = "G26";
const ARTICLE = [
  "## Agape in the New Testament",
  "",
  "The noun agape denotes a love that is chosen rather than felt, and the",
  "New Testament writers reach for it when the object of the love has done",
  "nothing to earn it.",
].join("\n");

const RESULT = {
  id: "doc-word-study-1",
  title: "Agape Word Study",
  author: "Precept Austin",
  word: "agape",
  transliteration: "agape",
  strongs_number: STRONGS,
};

test("the standalone /study word search renders the word study article", async ({ page }) => {
  // Registered first so every later stub takes priority: nothing in this test
  // may reach the real API host that .env.local points at.
  await page.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => route.abort());

  await page.route("**/study/wordsearch**", (route) =>
    route.fulfill({ json: { results: [RESULT] } }),
  );
  await page.route("**/study/wordstudy/**", (route) =>
    route.fulfill({ json: { content: ARTICLE, source: "excerpt" } }),
  );
  await page.route("**/study/lexicon**", (route) =>
    route.fulfill({
      json: {
        entries: [
          {
            strongs: STRONGS,
            word: "ἀγάπη",
            transliteration: "agape",
            gloss: "love",
            meaning: "affection, benevolence, charity",
          },
        ],
      },
    }),
  );
  await page.route("**/study/verses**", (route) => route.fulfill({ json: { verses: [] } }));

  await page.goto("/study");

  // Both the desktop and mobile trees are in the DOM (hidden md:flex /
  // md:hidden), so every assertion filters to the one actually shown.
  const input = page.getByPlaceholder(/Search verse or word/).filter({ visible: true });
  await expect(input).toHaveCount(1);
  await input.fill("agape");

  const dropdownItem = page
    .getByRole("button", { name: new RegExp(STRONGS) })
    .filter({ visible: true });
  await expect(dropdownItem).toHaveCount(1);
  await dropdownItem.click();

  // The regression: this section label and the article body below it were
  // absent entirely, while the definition above them rendered fine.
  await expect(page.getByText("Word Study", { exact: true }).filter({ visible: true })).toHaveCount(1);
  await expect(
    page.getByText(/a love that is chosen rather than felt/).filter({ visible: true }),
  ).toHaveCount(1);
  await expect(
    page.getByText("Agape in the New Testament").filter({ visible: true }),
  ).toHaveCount(1);
});
