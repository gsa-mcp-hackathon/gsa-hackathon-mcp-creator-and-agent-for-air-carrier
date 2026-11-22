# Blind review seal

The SHA-256 of the seed that placed each answer with the servers in column A or B of
`blind_sheet.csv`, recorded before any sheet went out:

`46eeaa3b229d54779a3f1c0568bb46f7c0cc36a8a26a0b97a7c150d44b56e618`

Built 2026-11-22 with `build_blind_pack.py answers.tsv --seed <seed>`. The seed stays with the
project owner, outside this repository, until every rater's sheet is back; then
`score_blind.py --seed <seed> --hash 46eeaa3b229d54779a3f1c0568bb46f7c0cc36a8a26a0b97a7c150d44b56e618 blind_sheet_*.csv` checks it and unblinds.
