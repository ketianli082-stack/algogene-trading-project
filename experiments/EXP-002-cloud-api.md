# EXP-002 — Cloud API submission attempt

Date: 2026-11-16 HKT
Code commit: 43a130b3f1ffa3b43777e0f7692cceab51832b00

Official specification: https://algogene.com/apidoc.yaml documents POST /run_backtest, GET /get_current_tasks and GET /task_status. This corrects the earlier incomplete API assessment in EXP-001.

GitHub execution: https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/43846452183

Outcome: NOT RUN on ALGOGENE. The GitHub cloud-backtest workflow executed, but stopped before making any platform request because ALGOGENE_USER_ID was empty. ALGOGENE_API_KEY was available (masked by GitHub); its value was neither read nor exported. No Backtest ID, task ID, trade or P/L was produced. Credential-free evidence artifact: 14214169311.

Next action: provide the existing user-ID secret/variable name or configure ALGOGENE_USER_ID in repository Actions secrets. No API key value is needed in chat. Then rerun the workflow. Do not interpret the Actions failure as a rejected ALGOGENE strategy: it was a missing-configuration preflight.
