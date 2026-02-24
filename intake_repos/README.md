# Intake Repos

Use this directory as the single landing zone for new, unscanned repository clones.

Rules:
- Keep canonical output shards (`llm_repos`, `ssh_repos`) separate from raw intake clones.
- Register new intake items in `inputs/intake/intake_manifest.yaml`.
- Apply deletion/retention checks from `inputs/intake/prune_policy.yaml` before removing clones.
