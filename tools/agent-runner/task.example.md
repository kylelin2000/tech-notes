# Task: <what you want, in one sentence>

## Goal
List EVERY <thing> on <site/section> and extract the fields below. Completeness matters more than speed.

## Where to start
- Index / listing: https://example.com/items?page=1  (paginated; follow "next" until there is none)
- If the site shows a total ("123 results"), record it with `set-expected`.

## What counts as an item
<one URL per item / one row per product / ...>. The ledger key is the item's canonical URL.

## Fields (the ledger rejects `done` without the required ones)
- title (required)
- url (required)
- date
- category
- summary: 2-3 sentences in your own words, no copy-paste of long passages
- notes: any assumption you made

## Rules
- Only use pages on example.com.
- If a field is not on the page, leave it out - never guess.
- Record anything odd (duplicate, redirect, page changed shape) in `notes`.

## Done means
Every listed item is `done`, `not-found` or `blocked` (with reason), and the listed count matches the site's total.
