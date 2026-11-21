-- Run in the Databricks SQL editor, then download the result as CSV (answers.csv).
-- The ten questions are the ones choose_questions.py picks by seed; both answers come from
-- Claude Sonnet 4.5 in round 4: repeat 1 with the servers, and the run without tools.
SELECT run_id, model, mode, qid, passed, answer
FROM users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs
WHERE question_set LIKE 'h4-%'
  AND model = 'databricks-claude-sonnet-4-5'
  AND mode IN ('tools_rep1', 'no_tools')
  AND qid IN ('R4-19 obl_mod_amount', 'R4-17 obl_mod_amount', 'R4-28 p5c_cell', 'R4-35 p5c_tse_change',
              'U08 document', 'U01 document', 'R4-38 premise_trap', 'U13 multi_source',
              'U14 judgment', 'U07 regulation')
ORDER BY qid, mode;
