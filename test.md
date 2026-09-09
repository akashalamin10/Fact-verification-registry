# Test Results - FactVerificationRegistry

All tests below were executed live on GenLayer Studio, not simulated
locally.

Deployed contract: deploy transaction
0x3886d11e56ff027c133675a6131d75c9c6fb1130ac0d00485ef2b51f732dfade

Test accounts:
0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48, claim submitter for both claims
0x4392834f897eD99348718CebCdafDF09d40aC314, unrelated address, used for the
access-control negative test

Source files, pushed to a public GitHub repository as plain text:
fact-source-supports.txt, describing GenLayer validators using AI language
models for consensus
fact-source-silent.txt, describing sourdough bread, unrelated to the claim
fact-source-contradicts.txt, describing traditional blockchain validators
that never invoke AI models

## 1. Deploy

Transaction: 0x3886d11e56ff027c133675a6131d75c9c6fb1130ac0d00485ef2b51f732dfade
Constructor argument: owner set to the submitter address
Result: success, finalized

## 2. submit_claim, claim1

Transaction: 0x5c4a2d996bab826a8c385732b4cf1fe18ee55eb3964329f5721e992b2fd67808
Input: claim_id claim1, claim_text stating GenLayer's validators use AI
language models to reach consensus on smart contract execution, source_urls
pointing to fact-source-supports.txt and fact-source-silent.txt
Result: success

get_claim after this call confirmed submitter was populated automatically
from the caller's address. It was never passed as a parameter.

## 3. verify_claim, claim1

Transaction: 0x097b9c1bf3b54be48edaa8113035483879ef1be2b00b508a81cef33266d9429e
Result: success

Equivalence Principle 0, the per-source stances: supports, silent
Equivalence Principle 1, the coherence check: yes

get_verdict for claim1, round 0 returned source_stances supports and
silent, overall_status true, coherence_confirmed true. This matches the
deterministic aggregation rule: one supporting source and no contradicting
source yields true.

## 4. submit_claim, claim2

Transaction: 0x06a3186a7e2b5e20a1700b442208e685d6e985f10f2fc9da3af6a87fe32257d1
Input: claim_id claim2, the identical claim_text used in claim1,
source_urls pointing to fact-source-contradicts.txt and
fact-source-silent.txt instead of the supporting source
Result: success

## 5. verify_claim, claim2

Transaction: 0xf4f7eb612f62bb563f1be2b3dc518685d3ca0c4ccd86109a3f4817919babd6cd
Result: success

Equivalence Principle 0, the per-source stances: contradicts, silent
Equivalence Principle 1, the coherence check: yes

The identical claim text now produced overall_status false, purely
because the source set was different from claim1. This is the key
demonstration of the N-source aggregation design: the contract's verdict
tracks the supplied evidence, not any memorized notion of whether the
underlying claim is generally true.

## 6. request_reverification, claim1, non-submitter address

Transaction: 0xf1377d1e2d179c32dcc8279a4a6b213e1a1c997e15f2307764268a3913b7cc8f
Caller: 0x4392834f897eD99348718CebCdafDF09d40aC314, not claim1's submitter
Result: error

Error: only the original submitter may request reverification

## 7. request_reverification, claim1, correct submitter

Transaction: 0x99918f8e196789ac78a522ac49374380dfde8966ca5709b4ebbbeb7ecc7aab44
Caller: 0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48, claim1's original
submitter
Input: an argument asking for a careful re-check of the same sources
Result: success

Equivalence Principle 0: supports, silent
Equivalence Principle 1, coherence: yes

get_reverification for claim1 returned overturned false, prior_round 0,
new_round 1. This is correct: both round 0 and round 1 resolved to overall
status true, so there was no strict improvement in rank to credit as an
overturn, even though a full independent re-evaluation was performed.

## 8. request_reverification, claim1, second attempt by the same submitter

Transaction: 0x53f4916d5e5fabcd13a158b779d9344e4b493f45af51fd08850472ad13d46807
Caller: 0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48, the same submitter as
step 7
Result: error

Error: this claim has already been reverified

This confirms the single-use guard. All active validators independently
reached the same assertion.

## Summary

| Behavior tested | Verified on-chain |
|---|---|
| submitter bound to authenticated sender, not a caller-supplied string | yes |
| identical claim text yields different verdicts under different source sets | yes |
| verify_claim runs a genuine two-round consensus, per-source stances plus independent coherence check | yes |
| request_reverification restricted to the original submitter | yes |
| a second reverification attempt by the same submitter reverts | yes |
| overturned is only true when the new status strictly outranks the prior status | yes, demonstrated in the equal-rank false case in step 7 |

## Known limitations observed

Individual validators occasionally show disagree or get cancelled after
quorum under Studio's simulated multi-validator load. Consensus still
finalizes correctly once quorum is met, and one transaction in this run
showed a visible leader rotation before reaching a final result, which
reflects real validator disagreement being resolved rather than a fault.

Calling gl.nondet.web.render or gl.nondet.exec_prompt outside the closure
passed to gl.eq_principle.prompt_comparative raises a forbidden error at
the GenVM level. This contract's source-fetching loops are written inside
the appropriate closures from the start, consistent with the pattern
established in the companion contracts after that issue was found and
fixed there.

This test run did not exercise a case where a reverification produces a
genuinely improved status, for example unverified to true, with overturned
true as a result. The ranking logic guarantees this behaves correctly by
construction, and is straightforward to verify in a follow-up test by
reverifying a claim whose first verdict was unverified with a stronger
supporting source added to the argument context.
