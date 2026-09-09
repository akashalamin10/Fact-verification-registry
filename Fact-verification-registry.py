# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


STANCES = ("supports", "contradicts", "silent")
STATUS_RANK = {"false": 0, "unverified": 1, "true": 2}


class FactVerificationRegistry(gl.Contract):
    owner: str
    claims: TreeMap[str, str]
    verdicts: TreeMap[str, str]
    reverifications: TreeMap[str, str]

    def __init__(self, owner: str):
        self.owner = owner
        self.claims = TreeMap()
        self.verdicts = TreeMap()
        self.reverifications = TreeMap()

    def _sender(self) -> str:
        return str(gl.message.sender_address)

    def _sources_block(self, source_urls: list) -> str:
        return "\n".join(f"{i}. {u}" for i, u in enumerate(source_urls))

    def _normalize_stances(self, parsed: dict, source_urls: list) -> list:
        raw = parsed.get("stances", [])
        if not isinstance(raw, list):
            raw = []
        result = []
        for i in range(len(source_urls)):
            if i < len(raw):
                stance = str(raw[i]).strip().lower()
            else:
                stance = ""
            if stance not in STANCES:
                stance = "silent"
            result.append(stance)
        return result

    def _verification_prompt(self, claim_text: str, source_urls: list, source_texts: list, extra: str = "") -> str:
        sources_with_content = "\n\n".join(
            f"SOURCE {i} ({source_urls[i]}):\n\"\"\"{source_texts[i]}\"\"\""
            for i in range(len(source_urls))
        )
        return f"""
You are a fact-checking validator. Evaluate the CLAIM against each numbered
SOURCE below. Return ONLY JSON with exactly this key:
{{"stances": ["supports", "contradicts", "silent", ...]}}

The array must have exactly {len(source_urls)} entries, in the same order
as the sources. "supports" means the source provides evidence the claim is
true. "contradicts" means the source provides evidence the claim is false.
"silent" means the source is not relevant to the claim either way.

CLAIM:
\"\"\"{claim_text}\"\"\"

{extra}

{sources_with_content}
""".strip()

    def _coherence_prompt(self, claim_text: str, source_urls: list, source_texts: list, stances: list, overall: str) -> str:
        pairs = "\n".join(f"{i}. {source_urls[i]} -> {stances[i]}" for i in range(len(source_urls)))
        sources_with_content = "\n\n".join(
            f"SOURCE {i} ({source_urls[i]}):\n\"\"\"{source_texts[i]}\"\"\""
            for i in range(len(source_urls))
        )
        return f"""
A fact-checking system evaluated this CLAIM and reached these per-source
stances, then an overall status of "{overall}":
{pairs}

Given the source content below, answer ONLY "yes" or "no": are these
stances and the overall status defensible given the sources?

CLAIM:
\"\"\"{claim_text}\"\"\"

{sources_with_content}
""".strip()

    def _aggregate(self, stances: list) -> str:
        supports = stances.count("supports")
        contradicts = stances.count("contradicts")
        if contradicts > 0 and contradicts >= supports:
            return "false"
        if supports > 0 and contradicts == 0:
            return "true"
        return "unverified"

    def _agree_stances(self, claim_text: str, source_urls: list, extra: str = "") -> list:
        def get_verdict() -> str:
            source_texts = [gl.nondet.web.render(u, mode="text") for u in source_urls]
            prompt = self._verification_prompt(claim_text, source_urls, source_texts, extra)
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            normalized = self._normalize_stances(raw, source_urls)
            return json.dumps(normalized)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "the stances array must be identical, entry by entry, "
                "in the same order."
            ),
        )
        return json.loads(agreed_raw)

    def _agree_coherence(self, claim_text: str, source_urls: list, stances: list, overall: str) -> bool:
        def get_bool() -> str:
            source_texts = [gl.nondet.web.render(u, mode="text") for u in source_urls]
            prompt = self._coherence_prompt(claim_text, source_urls, source_texts, stances, overall)
            raw = gl.nondet.exec_prompt(prompt)
            text = str(raw).strip().lower()
            return "yes" if text.startswith("y") else "no"

        agreed = gl.eq_principle.prompt_comparative(
            get_bool,
            principle="the yes/no answer must be exactly the same.",
        )
        return agreed == "yes"

    @gl.public.write
    def submit_claim(self, claim_id: str, claim_text: str, source_urls: DynArray[str]) -> None:
        assert claim_id not in self.claims, "claim already exists"
        assert len(source_urls) > 0, "at least one source is required"
        submitter = self._sender()
        record = {
            "submitter": submitter,
            "claim_text": claim_text,
            "source_urls": list(source_urls),
            "status": "open",
            "verdict_count": 0,
        }
        self.claims[claim_id] = json.dumps(record)

    @gl.public.view
    def get_claim(self, claim_id: str) -> dict:
        assert claim_id in self.claims, "no such claim"
        return json.loads(self.claims[claim_id])

    @gl.public.view
    def debug_has_claim(self, claim_id: str) -> bool:
        return claim_id in self.claims

    @gl.public.write
    def verify_claim(self, claim_id: str) -> None:
        assert claim_id in self.claims, "no such claim"
        claim = json.loads(self.claims[claim_id])
        assert claim["status"] == "open", "claim already has a verdict"

        claim_text = claim["claim_text"]
        source_urls = claim["source_urls"]

        stances = self._agree_stances(claim_text, source_urls)
        overall = self._aggregate(stances)
        coherent = self._agree_coherence(claim_text, source_urls, stances, overall)
        if not coherent:
            overall = "unverified"

        verdict_record = {
            "claim_id": claim_id,
            "round": 0,
            "source_stances": stances,
            "overall_status": overall,
            "coherence_confirmed": coherent,
        }
        self.verdicts[f"{claim_id}:0"] = json.dumps(verdict_record)

        claim["status"] = overall
        claim["verdict_count"] = 1
        self.claims[claim_id] = json.dumps(claim)

    @gl.public.view
    def get_verdict(self, claim_id: str, round_number: int) -> dict:
        key = f"{claim_id}:{round_number}"
        assert key in self.verdicts, "no such verdict"
        return json.loads(self.verdicts[key])

    @gl.public.write
    def request_reverification(self, claim_id: str, argument: str) -> None:
        assert claim_id in self.claims, "no such claim"
        claim = json.loads(self.claims[claim_id])
        caller = self._sender()
        assert caller == claim["submitter"], "only the original submitter may request reverification"
        assert claim["status"] != "open", "claim has not yet received an initial verdict"
        assert claim_id not in self.reverifications, "this claim has already been reverified"

        prior_round = claim["verdict_count"] - 1
        prior_verdict = json.loads(self.verdicts[f"{claim_id}:{prior_round}"])
        prior_overall = prior_verdict["overall_status"]

        claim_text = claim["claim_text"]
        source_urls = claim["source_urls"]
        extra = (
            f"A prior evaluation reached overall status '{prior_overall}'. "
            f"The submitter disputes this and argues:\n{argument}\n"
            f"Re-evaluate independently; you are not bound by the prior evaluation."
        )

        new_stances = self._agree_stances(claim_text, source_urls, extra)
        new_overall = self._aggregate(new_stances)
        coherent = self._agree_coherence(claim_text, source_urls, new_stances, new_overall)
        if not coherent:
            new_overall = "unverified"

        overturned = STATUS_RANK[new_overall] > STATUS_RANK[prior_overall]

        new_round = claim["verdict_count"]
        verdict_record = {
            "claim_id": claim_id,
            "round": new_round,
            "source_stances": new_stances,
            "overall_status": new_overall,
            "coherence_confirmed": coherent,
        }
        self.verdicts[f"{claim_id}:{new_round}"] = json.dumps(verdict_record)

        claim["status"] = new_overall
        claim["verdict_count"] = new_round + 1
        self.claims[claim_id] = json.dumps(claim)

        self.reverifications[claim_id] = json.dumps({
            "claim_id": claim_id,
            "requester": caller,
            "argument": argument,
            "prior_round": prior_round,
            "new_round": new_round,
            "overturned": overturned,
        })

    @gl.public.view
    def get_reverification(self, claim_id: str) -> dict:
        assert claim_id in self.reverifications, "no such reverification"
        return json.loads(self.reverifications[claim_id])
