# Grug Roadmap

## Agent Quality & Oversight

- **Manager / Supervisor Agent** — A second agent that monitors Grug's responses and
  corrects him when he drifts from core instructions (e.g. refusing a request because of
  active context, breaking voice rules). Could use the "LLM-as-judge" or reflection
  pattern. Open questions: does the manager run as a separate pydantic-ai agent or a
  post-processing step? Does it silently rewrite responses or post a visible correction?
- **User Feedback Loop** — Let users provide feedback about Grug's responses directly
  in the app (thumbs up/down, short text). The manager agent would ingest this feedback
  to steer Grug's behaviour over time (lightweight RLHF-style).
