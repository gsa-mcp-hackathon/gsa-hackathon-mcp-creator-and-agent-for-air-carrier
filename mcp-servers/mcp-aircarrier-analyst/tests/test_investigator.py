"""Investigator tests on fake sources: the clue chain, the cases, the review flag."""
from __future__ import annotations

from mcp_aircarrier_analyst import investigator as inv

K = inv.Knowledge(
    contracts={
        "N0002415C2114": {"label": "N00024-15-C-2114", "props": {"name": "CVN 79 DD&C"},
                          "rels": [("prime_contract_for", "hull:CVN-79", {}), ("awarded_to", "vendor:CAGE-43689", {})]},
        "N0002416C2116": {"label": "N00024-16-C-2116", "props": {"excluded": True, "why": "CVN-80 and CVN-81 DD&C"},
                          "rels": [("excluded_from", "hull:CVN-79", {"rule": "full PIID only"})]},
        "N0002409C2116": {"label": "N00024-09-C-2116", "props": {}, "rels": [("prime_contract_for", "hull:CVN-79", {})]},
        "N0001914C0037": {"label": "N00019-14-C-0037", "props": {},
                          "rels": [("partial_scope_for", "hull:CVN-79", {"cvn79_share_usd_m": 830.438})]},
    },
    neg_terms={"Large Aperture Bow": "LAB array is a submarine bow sonar. Carriers do not carry one",
               "consistent with": "coherence is not confirmation"},
    vendors={"43689": {"name": "HII Newport News Shipbuilding"}},
    budget_links={"program_element:0204112N": [("funds", "hull:CVN-79")], "bli:2001": [("line_of", "appropriation:1611N")]},
    cvn79_tas={"017-2018/2022-1611-000": ["N0002415C2114"]},
    program_codes={"223": "CVN 78"},
    psc_codes={"1905"},
)

TX = {"contract_transaction_unique_key": "K1", "award_id_piid": "N0002415C2114", "modification_number": "P00067",
      "action_date": "2020-03-10", "federal_action_obligation": "454765071.00",
      "transaction_description": "DETAIL DESIGN AND CONSTRUCTION CVN 79",
      "treasury_accounts_funding_this_award": "017-2018/2022-1611-000;017-2014/2018-1611-000",
      "cage_code": "43689", "recipient_name": "HUNTINGTON INGALLS", "dod_acquisition_program_code": "223",
      "product_or_service_code": "1905", "_row_num": "12", "_table": "aircarrier_src_2114_contract_transactions"}


class Fake:
    def __init__(self, tx=(), calls=None):
        self.tx, self.calls = list(tx), calls if calls is not None else []

    def fpds_by_amount(self, amount):
        self.calls.append(("fpds", amount))
        return [r for r in self.tx if r["federal_action_obligation"] == amount]

    def filec_by_amount(self, amount):
        return []

    def subawards(self, uei="", name="", amount=""):
        return []

    def exhibit_cells(self, values):
        return []

    def search_pages(self, term, limit=8):
        return []

    def hull_mentions(self, page_ids):
        return {}

    def node_hull_mentions(self, node_id):
        return {}

    def mechanisms(self, terms, limit=5):
        return []


def run(rec, tx=()):
    return inv.investigate(rec, K, Fake(tx))


def top(r):
    return r["cases"][0]["case"], r["cases"][0]["confidence"]


def test_normalize_maps_free_form_names():
    known, other = inv.normalize({"GL Amount": "1", "Contract No": "x", "Fund Code": "1611", "Weird": "y"})
    assert known == {"amount": "1", "piid": "x", "tas": "1611"} or known.get("piid") == "x"
    assert "Weird" in other


def test_profile_names_missing_elements_with_holder():
    p = inv.profile({"amount": "100.00"})
    miss = {m["element"] for m in p["missing_critical"]}
    assert {"piid", "tas", "vendor", "budget_line"} <= miss
    assert all(m["held_by"] for m in p["missing_critical"])


def test_amount_alone_chains_to_cvn79_deterministically():
    r = run({"GL Amount": "$454,765,071.00"}, [TX])
    h, conf = top(r)
    assert h == "CVN-79" and conf > 0.9
    assert r["cases"][0]["basis"] == "deterministic"
    skills = [s["skill"] for s in r["trail"]]
    assert skills.index("fpds_amount") < skills.index("keyset")          # amount found the PIID first
    piid = [c for c in r["clue_chain"] if c["key"] == "piid"][0]
    assert piid["from"] == "fpds_amount" and piid["strength"] == "exact" and piid["parent"] == 1
    assert any(e["value"] == "N0002415C2114" for e in r["data_elements_recovered"]["piid"])
    assert r["perfect_match"] is True and r["human_review"]["required"] is False


def test_collision_contract_goes_to_cvn80_81():
    r = run({"contract": "N00024-16-C-2116"})
    assert top(r)[0] == "CVN-80/81"
    against79 = [c for c in r["cases"] if c["case"] == "CVN-79"]
    assert not against79 or against79[0]["against"]


def test_near_miss_piid_raises_collision_flag_not_evidence():
    r = run({"contract": "N00024-17-C-2114"})
    assert any("collision" in f.lower() for f in r["flags"])
    assert r["human_review"]["required"] is True


def test_kennedy_name_only_needs_review():
    r = run({"description": "Kennedy outfitting material"})
    assert top(r)[0] == "CVN-79"
    assert r["human_review"]["required"] is True
    assert any("CV-67" in f for f in r["flags"])


def test_submarine_vocabulary_goes_not_carrier():
    r = run({"memo": "Large Aperture Bow array component"})
    assert top(r)[0] == "NOT_CARRIER"


def test_tas_on_cvn79_award_supports_cvn79_but_reviews():
    r = run({"tas": "017-2018/2022-1611-000"})
    assert top(r)[0] == "CVN-79"
    assert r["human_review"]["required"] is True          # an account alone is not a hull
    assert any(e["value"].startswith("1611") for e in r["data_elements_recovered"]["appropriation"])


def test_text_hides_a_piid_that_becomes_a_clue():
    r = run({"note": "per mod on N00024-15-C-2114, hull work"})
    assert any(c["key"] == "piid" and c["from"] == "text_cues" for c in r["clue_chain"])
    assert top(r)[0] == "CVN-79"


def test_multi_hull_contract_points_to_class_shared():
    r = run({"contract": "N00019-14-C-0037"})
    assert top(r)[0] == "CLASS_SHARED"
    assert any("multi-hull" in f for f in r["flags"])


def test_nothing_usable_is_uniform_and_reviewed():
    r = run({"foo": "bar"})
    assert abs(r["cases"][0]["confidence"] - 1 / 6) < 1e-3
    assert r["human_review"]["required"] is True


def test_same_cue_twice_counts_once():
    a = run({"description": "CVN 79"})
    b = run({"description": "CVN 79", "memo": "CVN 79 again"})
    assert a["cases"][0]["confidence"] == b["cases"][0]["confidence"]


def test_cooccurrence_weighs_lift_over_corpus_baseline():
    k = inv.Knowledge(**{**K.__dict__, "hull_baseline": {"hull:CVN-78": 70, "hull:CVN-79": 30}})

    class Docs(Fake):
        def search_pages(self, term, limit=8):
            return [{"artifact_id": "a", "page": 1, "grade": "AUTHORITATIVE", "filename": "x.pdf", "snippet": ""}]

        def hull_mentions(self, page_ids):
            return {"hull:CVN-78": 7, "hull:CVN-79": 3}   # exactly the baseline: no lift
    r = inv.investigate({"contract": "N00024-99-C-0001"}, k, Docs())
    assert not any(e["skill"] == "cooccurrence" for c in r["cases"] for e in c["for"])


def test_scn_main_account_alone_moves_nothing():
    r = run({"fund": "1611"})
    assert abs(r["cases"][0]["confidence"] - 1 / 6) < 1e-3
    assert r["data_elements_recovered"]["appropriation"]


def test_failing_source_does_not_end_the_case():
    class Broken(Fake):
        def fpds_by_amount(self, amount):
            raise RuntimeError("down")
    r = inv.investigate({"amount": "5.00", "description": "CVN 79"}, K, Broken())
    assert any("unavailable" in str(s["found"]) for s in r["trail"])
    assert top(r)[0] == "CVN-79"


def test_ambiguous_amount_is_weaker_than_unique():
    tx2 = {**TX, "contract_transaction_unique_key": "K2", "award_id_piid": "N0002416C2116"}
    r = run({"amount": "454765071.00"}, [TX, tx2])
    assert r["human_review"]["required"] is True
    assert any("candidates" in f for f in r["flags"])
    assert not [c for c in r["clue_chain"] if c["key"] == "piid"]          # leads, not links
    assert {c["value"] for c in r["clue_chain"] if c["key"] == "piid_candidate"} >= {"N0002415C2114", "N0002416C2116"}


def test_candidates_are_shown_but_never_weighed():
    tx2 = {**TX, "contract_transaction_unique_key": "K2", "award_id_piid": "N0002416C2116"}

    class Docs(Fake):
        def search_pages(self, term, limit=8):
            return [{"artifact_id": "a", "page": 1, "grade": "AUTHORITATIVE", "filename": "x.pdf",
                     "snippet": "see N00024-16-C-2116"}]

        def hull_mentions(self, page_ids):
            return {"hull:CVN-80": 9}
    r = inv.investigate({"amount": "454765071.00"}, K, Docs([TX, tx2]))
    assert not [e for c in r["cases"] for e in c["for"] + c["against"]]
    assert any("candidate only" in str(s["found"]) for s in r["trail"])


def test_summary_detail_condenses_trail_and_keeps_the_answer():
    from mcp_aircarrier_analyst.tools import _compact_investigation

    r = run({"amount": "454765071.00"}, [TX])
    s = _compact_investigation(r)
    assert s["cases"] == r["cases"] and s["clue_chain"] == r["clue_chain"]
    assert s["human_review"] == r["human_review"]
    assert all(set(h) == {"hop", "skill", "found"} for h in s["trail"])
    assert len(s["trail"]) == len(r["trail"])
    assert any("matches" in h for h in r["trail"])
    assert not any("matches" in h or "reads" in h for h in s["trail"])
    assert s["detail"] == "summary" and "trail" in r and "detail" not in r


def test_round_amount_single_match_is_not_deterministic():
    tx = {**TX, "federal_action_obligation": "1000000.00"}
    r = run({"amount": "1,000,000.00"}, [tx])
    assert r["cases"][0]["basis"] == "inferred"
    assert r["perfect_match"] is False
    assert any("round amount" in f for f in r["flags"])
