#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

DOC_PATH = Path("SCORING_LOGIC.md")

def load_doc_contract(md: str) -> dict:
    m = re.search(r"<!--\s*SCORING_CONTRACT_JSON\s*(\{.*?\})\s*SCORING_CONTRACT_JSON\s*-->", md, re.S)
    if not m:
        raise SystemExit("❌ Missing SCORING_CONTRACT_JSON block in SCORING_LOGIC.md")
    return json.loads(m.group(1))

def main() -> int:
    md = DOC_PATH.read_text(encoding="utf-8")
    doc_contract = load_doc_contract(md)

    sys.path.insert(0, '.')
    from core.scoring_contract import SCORING_CONTRACT
    code_contract = SCORING_CONTRACT

    if doc_contract != code_contract:
        print("❌ Scoring contract mismatch (docs != code)")
        doc_keys = set(doc_contract.keys())
        code_keys = set(code_contract.keys())
        if doc_keys != code_keys:
            print(f"Keys differ: doc_only={sorted(doc_keys-code_keys)} code_only={sorted(code_keys-doc_keys)}")
        for k in sorted(doc_keys & code_keys):
            if doc_contract[k] != code_contract[k]:
                print(f"Diff @ {k}: docs={doc_contract[k]} code={code_contract[k]}")
        return 1

    print("✅ Scoring contract matches (docs == code)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
