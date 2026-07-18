# Profile metrics

`scripts/update_profile_metrics.py` updates the single metrics block in the
profile README. The scheduled workflow counts active, owned, non-fork
repositories and excludes the profile repository and
`gleam-browser-extension`.

The public profile exposes:

- exact public source lines, source files, and repository count;
- private source lines rounded to the nearest thousand;
- one aggregate GitHub Linguist language mix across included public
  repositories.

It never publishes private repository names, private file counts, private
repository counts, private language data, or exact private line totals. A
failed private repository request aborts the update without logging the
repository name.

## Credential

The scheduled update requires an Actions secret named
`PROFILE_METRICS_TOKEN`. Use a fine-grained personal access token owned by
`aiwaki` with:

- repository access limited to the repositories that should contribute;
- `Contents: Read-only` and `Metadata: Read-only` repository permissions;
- no account, organization, or write permissions.

The secret is available only to the scheduled/manual update step. Pull request
checks run the unit tests without it.
