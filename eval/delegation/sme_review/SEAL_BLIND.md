# Blind review seal

The SHA-256 of the seed that placed each answer with the servers in column A or B of
`blind_sheet.csv`, recorded before any sheet went out:

`46eeaa3b229d54779a3f1c0568bb46f7c0cc36a8a26a0b97a7c150d44b56e618`

Built 2026-11-22 with `build_blind_pack.py answers.tsv --seed <seed>`. The seed stays with the
project owner, outside this repository, until every rater's sheet is back; then
`score_blind.py --seed <seed> --hash 46eeaa3b229d54779a3f1c0568bb46f7c0cc36a8a26a0b97a7c150d44b56e618 blind_sheet_*.csv` checks it and unblinds.

## Unblinded 2026-11-22

One rater's sheet came back (`blind_sheet_AB.csv`, initials AB, a teammate who did not build the
servers). The project owner decided to score with that sheet alone. The seed, revealed now:

`hXGfy_th_qsJTjnwby6NmKgf`

Check: its SHA-256 is the hash above. `score_blind.py` refused to run unless they matched, then
wrote [BLIND_RESULTS.md](BLIND_RESULTS.md).

