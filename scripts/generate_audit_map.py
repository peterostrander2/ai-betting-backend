#!/usr/bin/env python3
"""
Generate docs/AUDIT_MAP.md from core/integration_contract.py
Single source of truth - no manual edits to AUDIT_MAP
"""
import sys
sys.path.insert(0, '.')

from core.integration_contract import INTEGRATIONS, REQUIRED_INTEGRATIONS

def generate_audit_map():
    output = []
    
    # Header
    output.append("# Integration Audit Map")
    output.append("")
    output.append("**AUTO-GENERATED from `core/integration_contract.py` - DO NOT EDIT MANUALLY**")
    output.append("")
    output.append("Run `./scripts/generate_audit_map.sh` to regenerate.")
    output.append("")
    
    # Summary
    output.append("## Summary")
    output.append("")
    output.append(f"- **Total Integrations:** {len(INTEGRATIONS)}")
    output.append(f"- **Required:** {len(REQUIRED_INTEGRATIONS)}")
    output.append(f"- **Optional:** {len(INTEGRATIONS) - len(REQUIRED_INTEGRATIONS)}")
    output.append("")
    
    # Table
    output.append("## Integration Details")
    output.append("")
    output.append("| Integration | Env Vars | Required | Owner Modules | Feeds Engine | Description |")
    output.append("|-------------|----------|----------|---------------|--------------|-------------|")
    
    for key in sorted(INTEGRATIONS.keys()):
        integration = INTEGRATIONS[key]
        env_vars = ", ".join([f"`{v}`" for v in integration["env_vars"]])
        required = "✅ Yes" if integration["required"] else "❌ No"
        modules = ", ".join([f"`{m}`" for m in integration["owner_modules"]])
        feeds = integration["feeds_engine"]
        desc = integration["description"]
        
        output.append(f"| **{integration['debug_name']}** | {env_vars} | {required} | {modules} | {feeds} | {desc} |")
    
    output.append("")
    
    # Special rules
    output.append("## Special Rules")
    output.append("")
    output.append("### Weather Integration")
    output.append("")
    output.append("- **Status:** Required but relevance-gated")
    output.append("- **Allowed Statuses:** `VALIDATED`, `CONFIGURED`, `NOT_RELEVANT`, `UNAVAILABLE`, `ERROR`, `MISSING`")
    output.append("- **Banned Statuses:** `FEATURE_DISABLED`, `DISABLED` (hard ban)")
    output.append("- **Behavior:** Returns `NOT_RELEVANT` for indoor sports, never feature-disabled")
    output.append("")
    
    output.append("### BallDontLie Integration")
    output.append("")
    output.append("- **Env Var Aliases:** Accepts both `BALLDONTLIE_API_KEY` and `BDL_API_KEY`")
    output.append("")
    
    # Runtime status section
    output.append("## Runtime Status")
    output.append("")
    output.append("For current integration status, query:")
    output.append("```bash")
    output.append('curl "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" | jq .')
    output.append("```")
    output.append("")
    
    # Validation
    output.append("## Validation")
    output.append("")
    output.append("This document is validated by:")
    output.append("- `scripts/validate_integration_contract.sh` (pre-commit hook)")
    output.append("- Session 4 in CI (`scripts/ci_sanity_check.sh`)")
    output.append("")
    
    return "\n".join(output)

if __name__ == "__main__":
    content = generate_audit_map()
    
    # Write to file
    with open("docs/AUDIT_MAP.md", "w") as f:
        f.write(content)
    
    print("✅ Generated docs/AUDIT_MAP.md")
