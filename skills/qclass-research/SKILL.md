---
name: qclass-research
description: "Use when researching QLab topics covered by the imported Figure 53 QClass 5.5 transcripts in docs/qclass/. Load the local index first, search the relevant transcript, and report timestamped evidence without consulting other sources."
---

# QClass Research

Use this skill to research only the Markdown transcripts of Figure 53 QClass
5.5 classes stored in `docs/qclass/`. They are records of live QLab classes,
not a normative manual or a runtime behavior test.

## Scope and sources

The only permitted source is this directory:

- `docs/qclass/README.md`, index of days, topics, and timestamps.
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md`.
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`.
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 3.md`.

The `.txt` names mentioned inside the Markdown are metadata for the imported
transcript; do not treat them as available files. Do not consult other
repository directories, web documentation, code, or external sources to
complete a QClass answer.

## Required workflow

1. Read `docs/qclass/README.md` first. Identify the day and topic closest to the
   question; preserve the timestamp shown in the index.
2. Search for concrete terms in the corresponding Markdown. For example:

   ```sh
   rg -n -i "geometry|camera|video fx" "docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md"
   ```

3. Read the context around each match with `sed -n` or another bounded read. If
   the topic spans days, repeat the search in each transcript and separate the
   evidence by day.
4. Respond with separate sections:
   - **Evidence**: what the transcript says, with day, section, and timestamp.
   - **Interpretation**: a synthesis or reasonable connection derived from the text.
   - **Limits**: what does not appear or cannot be confirmed in these transcripts.
5. If you do not find sufficient evidence, say so explicitly. Do not fill gaps
   with general QLab knowledge or turn an oral explanation into a normative
   claim.

## Reading rules

- Preserve control names, cue types, commands, and technical terms literally
  when they appear in the text; explain them in English when useful.
- Do not edit the transcripts. Add navigation only to the index if the user
  explicitly requests it, and keep the imported text intact.
- This skill is for documentary research: it does not run QLab, send OSC or
  AppleScript, or authorize changes to workspaces, cues, or show files.
- If the question requires a source outside `docs/qclass/`, report that it is
  outside the scope of QClass instead of consulting it automatically.

## Recommended format

```text
Source: Day N — <topic/section> — <timestamp>
Evidence: <brief paraphrase or short transcript quote>
Interpretation: <synthesis, if applicable>
Limits: <what the transcript does not confirm>
```
