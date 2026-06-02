# Repo Wiki Layer Rules

You maintain a persistent repo wiki in `/wiki`.

## Goal
Do not repeatedly rediscover the codebase from scratch. When you learn stable information about the repo, write it into `/wiki` so future sessions can start from the wiki first.

## Source of truth
The actual source code is the final source of truth.
The wiki is a compiled understanding layer and may be stale.

## Required workflow

Before answering repo questions:
1. Read `/wiki/index.md` if it exists.
2. Read the most relevant wiki pages.
3. Only then inspect source files if needed.
4. If the source contradicts the wiki, trust the source and update the wiki.

When learning something durable:
- Update the relevant page in `/wiki`.
- Add links between related pages.
- Update `/wiki/index.md`.
- Append a short entry to `/wiki/log.md`.

## Wiki structure

- `/wiki/index.md`: map of all wiki pages.
- `/wiki/architecture.md`: high-level architecture.
- `/wiki/modules/*.md`: one page per major module.
- `/wiki/decisions/*.md`: architectural decisions.
- `/wiki/glossary.md`: important terms.
- `/wiki/log.md`: chronological changelog of wiki updates.

## Page format

Each wiki page should include:
- Purpose
- Key files
- Important concepts
- Data flow
- Dependencies
- Known caveats
- Links to related wiki pages
- Last verified date