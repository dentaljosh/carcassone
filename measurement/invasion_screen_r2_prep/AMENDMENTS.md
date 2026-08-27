# invasion_screen_r2_prep — post-freeze amendments

## IS-A1 — 2026-08-27: cross-box G-REV short-sha false void; owner-authorized amended re-read
The frozen adjudicator's cross-box clause compared the boxes' EMITTED short revs for string
equality; `git rev-parse --short` length varies per clone, so the two boxes at the IDENTICAL
commit emitted `240626a3-dirty` (local) vs `240626a31f-dirty` (laptop) and the round falsely
voided (frozen verdict U-UNREADABLE — stands unedited on the record). Proof of single-rev:
both boxes' PINNED_SRC_REV files byte-identical (240626a31feeab01e22e73b42230a80a9889ec6f);
every boundary clean against that pin on both boxes. Same defect class as h2h_22016 G-REV
(short-vs-full sha), cross-box variant. Owner ruled the re-read (verbatim "option 1 and
shit", per the h2h-option-1 precedent). `analyze_screen_amended.py` = the frozen script with
ONE clause canonicalized (strip -dirty; each rev must prefix the shared 40-hex pin);
selftest GREEN; all other gates byte-identical. AMENDED VERDICT: BRACKET-CONTINUE
(A_LOW BRACKET / A_HIGH REVERSED / B both NULL / C_LOW BRACKET / C_MID NULL / C_HIGH NULL).
Lesson for future two-box pairs: canonicalize revs against the pin, never rev-vs-rev.
