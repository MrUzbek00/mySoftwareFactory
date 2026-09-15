# Security Heuristics

The scanner is a tripwire, not a reviewer. It is very good at one thing —
noticing that a change added text matching a known-dangerous shape — and
incapable of everything else.

## What Pattern Matching Catches

Secrets have recognizable shapes, and so do dangerous calls. Those are worth
automating because they are easy to miss by eye and expensive to miss in
practice.

The rule set covers secret material, dangerous sinks (`eval`, `os.system`,
`shell=True`, `pickle.loads`, unsafe `yaml.load`, `innerHTML`, string-built
SQL), weakened protections (disabled TLS verification, wildcard CORS, permissive
file modes, weak hashes), and changes to dependency manifests.

## What It Structurally Cannot Catch

None of these have a textual signature, and all of them are more common than
hardcoded secrets:

- **Missing authorization** — the code correctly fetches a record; nothing checks
  the caller may see it.
- **Broken tenancy** — a query filters by ID but not by account.
- **IDOR** — a user-supplied identifier is trusted as a lookup key.
- **Logic flaws** — a discount, a quota, or a retry that can be driven to an
  unintended state.
- **Race conditions** — a check and a use separated by an await.
- **Over-disclosure** — a serializer that now returns an internal field, or a
  log line that now includes a token.
- **Trust boundary drift** — an internal helper now reachable from a public
  route.

This is why the skill requires reasoning after the scan. A clean scan means the
tripwire did not fire; it does not mean the change is safe.

## Added Lines Only

The scan reads only lines the diff **added**. This is deliberate: it keeps the
report about what this task introduced rather than drowning it in the
repository's existing patterns.

The consequence is that removing a protection can be invisible. Deleting an
authorization check is a deletion, and a deletion has no added line to match. If
the diff removes anything security-relevant, that is a judgment finding — the
scanner will not raise it.

## Redaction Is One-Way

When a secret rule matches, the matched span is replaced with
`<redacted:Nchars>` before it enters the report. That masking exists so the
finding can be discussed, logged, and pasted into a pull request without
spreading the secret further.

Do not undo it. Do not open the file and quote the value to "confirm" the
finding — the file path and line number are enough for a human to look.

## A Secret in the Diff Is Already a History Problem

If a secret appears in the diff, it is in a commit. Deleting the line in a new
commit removes it from the working tree, not from history — anyone who fetches
the branch gets it, and once pushed, it should be treated as disclosed.

The response is always:

1. Stop. Do not push, and do not open a pull request.
2. Rotate the credential. This is the step that actually helps.
3. Escalate to whoever owns the secret.
4. Only then decide what to do about the branch.

Rotation first, cleanup second. A scrubbed history with a live credential is
worse than an honest one, because it looks resolved.

## Dependency Changes

Every added manifest line is reported, at no severity, because the risk is not
in the shape of the line. Ask:

- Is this package the one it appears to be? Check for typosquats on a name close
  to a popular package.
- Is the version pinned, and is it a version that exists?
- Does it pull transitive dependencies the project has not accepted before?
- Does the change add a package that duplicates something already present?

## False Positives

Some rules fire on legitimate code — `subprocess` calls are `LOW` for exactly
this reason, and a test fixture with a fake credential will match the secret
rules.

Dismissing a finding is fine. Dismissing it silently is not. State which finding,
and why it is not a problem here. "False positive" without a reason is not a
review; it is a shrug that a reader has to take on faith.
