# FactVerificationRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, multi-source
fact verification. Usable by journalism, DAO governance, or any community
fact-checking workflow that needs a neutral, tamper-resistant verdict on a
claim checked against several independent sources at once.

Deployed contract (GenLayer Studio): deploy transaction
0x3886d11e56ff027c133675a6131d75c9c6fb1130ac0d00485ef2b51f732dfade

## Why this is a primitive, not a thin demo

N-source aggregation, not a single comparison. A claim can be checked
against any number of source URLs, not a fixed pair. Validators
independently fetch every source and produce a per-source stance array,
then the contract deterministically aggregates those stances into an
overall true, false, or unverified status. This is a different consensus
shape from a single-document or two-document comparison, since the
contract has to combine several independent judgments into one.

Authenticated party binding. submit_claim binds submitter to
gl.message.sender_address automatically. It is never a caller-supplied
string.

Real two-round consensus. Round one produces a structured, closed-
vocabulary per-source stance array, supports, contradicts, or silent, via
gl.eq_principle.prompt_comparative. Round two is a separately executed
coherence check confirming the stance set and aggregate status are
defensible given the source content. Both rounds are visible on-chain as
distinct Equivalence Principle entries in every transaction receipt, which
is direct proof the coherence check is real rather than a hardcoded flag.
If coherence is not confirmed, the contract falls back to an unverified
status rather than trusting round one alone.

Canonical fallback for invalid stances. If a validator's model returns an
empty or invalid stance for a source, the contract substitutes the neutral
canonical value silent rather than storing an arbitrary or fabricated
value.

Single-use reverification by the original submitter. Only the address
that submitted a claim may request one reverification of it. A second
attempt reverts. This mirrors the access-control pattern already verified
across this builder's other accepted submissions.

A correctly defined overturn. Status quality is explicitly ranked, false
below unverified below true. A reverification only counts as overturned
true when the new status strictly outranks the prior one. A same or worse
replacement status is never credited as a successful overturn.

No non-deterministic wall-clock state. The contract persists no
timestamp anywhere.

## State design

| Field | Type | Purpose |
|---|---|---|
| owner | str | Platform or admin address |
| claims | TreeMap[str, str] | claim_id to JSON: submitter, claim_text, source_urls, status, verdict_count |
| verdicts | TreeMap[str, str] | "claim_id:round" to JSON: source_stances, overall_status, coherence_confirmed |
| reverifications | TreeMap[str, str] | claim_id to JSON reverification record; presence marks the claim as already reverified |

## How consensus is used

submit_claim(claim_id, claim_text, source_urls) stores the submitter from
gl.message.sender_address and the list of source URLs to check against.

verify_claim fetches every source URL inside the validator closure passed
to gl.eq_principle.prompt_comparative, asks for a per-source stance array
matching the source order, normalizes any invalid entries to silent, then
deterministically aggregates the agreed stances: any contradiction that
meets or exceeds the support count yields false; any support with no
contradiction yields true; otherwise unverified. A second, independently
executed coherence round then confirms the result is defensible, refetching
every source again inside its own closure.

request_reverification repeats the same two-round pattern with the
submitter's argument injected, after confirming the caller is the original
submitter and the claim has not already been reverified.

## Verified on-chain test evidence

All transactions below were executed live on GenLayer Studio.

| Step | Method | Transaction | Result |
|---|---|---|---|
| 1 | Deploy | 0x3886d11e56ff027c133675a6131d75c9c6fb1130ac0d00485ef2b51f732dfade | success |
| 2 | submit_claim, claim1, supporting and silent sources | 0x5c4a2d996bab826a8c385732b4cf1fe18ee55eb3964329f5721e992b2fd67808 | success |
| 3 | verify_claim, claim1 | 0x097b9c1bf3b54be48edaa8113035483879ef1be2b00b508a81cef33266d9429e | success, stances supports and silent, coherence yes, overall status true |
| 4 | submit_claim, claim2, same claim text, contradicting and silent sources | 0x06a3186a7e2b5e20a1700b442208e685d6e985f10f2fc9da3af6a87fe32257d1 | success |
| 5 | verify_claim, claim2 | 0xf4f7eb612f62bb563f1be2b3dc518685d3ca0c4ccd86109a3f4817919babd6cd | success, stances contradicts and silent, coherence yes, overall status false |
| 6 | request_reverification, claim1, non-submitter address | 0xf1377d1e2d179c32dcc8279a4a6b213e1a1c997e15f2307764268a3913b7cc8f | error, only the original submitter may request reverification |
| 7 | request_reverification, claim1, correct submitter | 0x99918f8e196789ac78a522ac49374380dfde8966ca5709b4ebbbeb7ecc7aab44 | success, stances supports and silent, coherence yes, overall status remains true, overturned false |
| 8 | request_reverification, claim1, second attempt by the submitter | 0x53f4916d5e5fabcd13a158b779d9344e4b493f45af51fd08850472ad13d46807 | error, this claim has already been reverified |

get_claim after step 3 confirmed submitter was populated automatically
from the caller's address, since submit_claim does not accept one as a
parameter.

The claim2 result demonstrates the core N-source aggregation design point:
the identical claim text produced the opposite overall status, true versus
false, purely because it was checked against a different set of sources.
This shows the contract judges strictly from the supplied evidence rather
than any memorized or hardcoded notion of the claim's truth.

Full test narrative is in TESTS.md.

## Suggested tests to reproduce

Deploy, then submit_claim with two or more source URLs.

verify_claim, confirm source_stances has one entry per source and
coherence_confirmed is present.

Submit a second claim with identical claim text but a different, opposing
set of sources, verify it, and confirm the overall status differs from the
first claim.

request_reverification from a non-submitter address, confirm it reverts.

request_reverification from the correct submitter, confirm it succeeds.

request_reverification a second time from the same submitter, confirm it
reverts with this claim has already been reverified.

## Caveats

GenLayer's exact SDK surface, including gl.nondet.web.render,
gl.eq_principle, and gl.message, is evolving. Verify current method names
and signatures against GenLayer's latest documentation before deploying
elsewhere.

All source URLs must be publicly reachable via gl.nondet.web.render.
Nondet operations must be called from inside the closure passed to
gl.eq_principle.prompt_comparative; calling them directly in the main
method body raises a forbidden error at the GenVM level.

The aggregation rule in _aggregate is a simple majority-style heuristic
intended to be transparent and auditable. Platforms with different
evidentiary standards, for example requiring unanimous support or
weighting sources by reliability, can fork this function without changing
the consensus or access-control design.
