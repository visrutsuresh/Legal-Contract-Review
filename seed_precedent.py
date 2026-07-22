"""Seed the precedent cabinet with prior reviews. Idempotent: run any time.

Why this exists: precedent.index_reviewed only fires when a lawyer finishes a
review, so on a fresh machine the cabinet is empty and precedent_search returns
nothing. Three agents (compliance, risk, negotiation) advertise that tool in
their system prompts, so without a starter set the tool is dead weight for
every early contract.

These are FICTIONAL past reviews, and deliberately not the contracts in
data/contracts/. Those thirteen are the bench corpus: seeding their planted
defects here would let an inspector retrieve the answer instead of finding it,
and the recall numbers would mean nothing. The entries below cover the same
CLASSES of term (late payment, uncapped liability, one-way indemnity) with
different counterparties and different specifics, which is how precedent works
in practice anyway: you cite the ruling, not the other side's paperwork.

Shape matches what api.finish_review writes, so a seeded hit and a real one
read identically to an agent:
    title   "<filename> (<contract_type>)"
    content "<executive summary>\n\nDecisions:\n<clause_id> <heading>: <verdict>"

Run:  .venv/Scripts/python.exe seed_precedent.py
"""

from app import precedent

REVIEWS = [
    (
        "ashgrove_mutual_nda.docx (nda)",
        "A mutual non-disclosure agreement with Ashgrove Analytics ahead of a data "
        "partnership. Low risk overall once two terms moved. Their draft let either side "
        "share our material with any affiliate or subcontractor without passing the "
        "confidentiality duty down, which in practice means the information is not "
        "confidential at all. We also struck a perpetual survival period in favour of "
        "five years from disclosure, our standard. The definition of Confidential "
        "Information was acceptable as written.",
        [
            ("c03", "Obligations of Confidentiality", "accepted"),
            ("c05", "Term and Survival", "accepted"),
            ("c07", "Return or Destruction", "rejected"),
        ],
    ),
    (
        "pellucid_msa.docx (msa)",
        "A master services agreement with Pellucid Systems for a two-year engagement. "
        "High risk as drafted, chiefly because liability was uncapped in both directions "
        "while the indemnity ran one way only, against us. We capped aggregate liability "
        "at fees paid in the preceding twelve months and made the indemnity mutual. "
        "Payment sat at net-75; we moved it to net-30 and they agreed without argument. "
        "The auto-renewal clause renewed for successive two-year terms on sixty days "
        "notice, which we cut to a one-year renewal on thirty days.",
        [
            ("c06", "Fees and Payment", "accepted"),
            ("c11", "Limitation of Liability", "accepted"),
            ("c12", "Indemnification", "edited"),
            ("c14", "Term and Renewal", "accepted"),
        ],
    ),
    (
        "norwood_vendor_agreement.docx (vendor)",
        "A vendor supply agreement with Norwood Instrument. Medium risk. The pricing "
        "clause allowed the supplier to raise fees at any time on thirty days notice with "
        "no ceiling, so we bound increases to once per year and capped them at CPI. Their "
        "termination right was immediate and for convenience while ours required ninety "
        "days, which we made symmetrical. We accepted their warranty period of twelve "
        "months as within our range.",
        [
            ("c04", "Pricing and Increases", "accepted"),
            ("c09", "Termination", "accepted"),
            ("c10", "Warranties", "rejected"),
        ],
    ),
    (
        "cantillon_sow.docx (sow)",
        "A statement of work with Cantillon Design for a fixed-scope delivery. Medium "
        "risk. The acceptance clause deemed deliverables accepted if we did not object "
        "within three business days, far too short to test anything meaningful; we moved "
        "it to fifteen business days with a written acceptance test. Change control was "
        "absent entirely, so we added it: no scope change binds either side without a "
        "signed change order. Milestone payments were tied to dates rather than "
        "deliverables, which we reversed.",
        [
            ("c05", "Acceptance", "accepted"),
            ("c07", "Payment Milestones", "edited"),
            ("c08", "Change Control", "accepted"),
        ],
    ),
    (
        "bexley_employment.docx (employment)",
        "An employment contract for a senior engineering hire, reviewed for the candidate "
        "side. Medium risk. The restraint of trade ran twenty-four months across the "
        "whole sector with no geographic limit, which is unlikely to be enforceable and "
        "was cut to twelve months within the state and limited to direct competitors. "
        "The IP assignment swept in everything the employee created at any time including "
        "personal projects on their own equipment; we narrowed it to work arising from "
        "their duties. Notice period and salary review terms were left as drafted.",
        [
            ("c08", "Intellectual Property", "accepted"),
            ("c11", "Restraint of Trade", "accepted"),
            ("c13", "Confidentiality", "rejected"),
        ],
    ),
    (
        "thornhill_msa.docx (msa)",
        "A master services agreement with Thornhill Consulting. High risk on the money "
        "terms. Late payment interest ran at 4 percent per month, roughly 60 percent a "
        "year, which we brought down to the statutory rate. The fee schedule quoted a "
        "monthly figure but the total contract value stated in the cover clause did not "
        "match thirty-six months of it; we corrected the arithmetic before signature. "
        "Their data protection clause named no processor obligations at all despite the "
        "work involving personal data, and we inserted the standard set.",
        [
            ("c06", "Fees", "edited"),
            ("c07", "Late Payment", "accepted"),
            ("c15", "Data Protection", "accepted"),
        ],
    ),
    (
        "marrow_nda.docx (nda)",
        "A one-way non-disclosure agreement where we are the disclosing party, with "
        "Marrow Ventures during a funding conversation. Low risk. The remedies clause "
        "set liquidated damages at a fixed sum per breach, which reads as a penalty and "
        "risks being struck out entirely, taking our remedy with it; we replaced it with "
        "injunctive relief plus proven damages. Everything else followed our template.",
        [
            ("c06", "Remedies", "accepted"),
            ("c08", "Governing Law", "rejected"),
        ],
    ),
    (
        "quillon_vendor_agreement.docx (vendor)",
        "A software vendor agreement with Quillon Cloud. High risk before amendment. The "
        "licence grant let the vendor use data we uploaded to improve their products with "
        "no restriction, which we removed outright. Their liability cap sat at three "
        "months of fees while their indemnity obligations were excluded from the cap only "
        "for their benefit; we made the carve-outs mutual. The service credit regime was "
        "the sole remedy for downtime, and we kept termination rights for sustained "
        "outages on top of it.",
        [
            ("c05", "Licence and Data Use", "accepted"),
            ("c09", "Service Levels", "edited"),
            ("c12", "Limitation of Liability", "accepted"),
        ],
    ),
]


def main() -> None:
    precedent.ensure_collection()
    removed = precedent.clear_seeded()
    print(f"cleared {removed} previously seeded entr{'y' if removed == 1 else 'ies'}")
    for title, executive, decisions in REVIEWS:
        digest = "\n".join(f"{cid} {heading}: {verdict}" for cid, heading, verdict in decisions)
        precedent.index_reviewed(title, f"{executive}\n\nDecisions:\n{digest}", source="seed")
        print(f"filed {title}")
    print(f"\n{len(REVIEWS)} precedent entries in the cabinet")


if __name__ == "__main__":
    main()
