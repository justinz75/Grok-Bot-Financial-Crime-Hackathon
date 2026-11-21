# Grok-Bot-Financial-Crime-Hackathon

Our entry for Track 2 (sanctions screening) of the Grok Bot London Financial Crime Hackathon,
21 November 2026. For every watchlist hit raised against a bank customer, the system decides
whether the hit is the customer, a different person or company, or needs a person to review it.

- **The system:** [system/README.md](system/README.md) explains how it works. Run it with
  `system/run <data folder> <output file>`.
- **Predictions on the development set:** [output/dev.jsonl](output/dev.jsonl).
- **See it:** open [viewer/index.html](viewer/index.html) in a browser. It starts on a built-in
  sample of invented hits decided by the real system; choose `output/dev.jsonl` to see a run.
- **Working on this repo, as a person or an AI agent:** start at [AGENTS.md](AGENTS.md).
