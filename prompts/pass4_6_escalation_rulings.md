# Pass 4.6 — Escalation rulings (Sonnet, surgical, no search needed)
Apply Tanner's rulings on the three Pass 4.5 escalations. Log in REMEDIATION_LOG.md.
1. H4b: refine verdict in SYNTHESIS.md — "proxy-only for entailment-structured
   decomposition faithfulness; gold benchmarks exist only for atomic-claim
   identification (CACDD, Zhang et al. 2025, Chinese/WebCPM; cf. FactLens,
   Mitra et al., ACL Findings 2025, fine-grained sub-claim verification).
   Neither tests joint sufficiency / load-bearing structure. None found for
   entailment-preserving decomposition as of Aug 2026." Add literature.jsonl
   rows for CACDD (arxiv.org/pdf/2410.12558, doi 10.1007/978-981-96-1710-4_4)
   and FactLens (aclanthology.org/2025.findings-acl.929), bucket
   claim-decomposition-factuality, with not_handled fields stating the above.
2. product-024 access_model: set per the Doody's review (subscription;
   individual ~$3/mo primary), confidence verified.
3. Move the Nature Index URL from product-024 provenance to product-020
   (scite Reference Check) where it belongs; append "single-source row
   (Doody's only)" to product-024's extraction_note.
Commit: "pass4.6: escalation rulings — H4b refined, RedacTek sourcing fixed".