#!/bin/bash
# tvOS 26.x compatibility patch for pyatv
# Fixes FetchAttentionState timeout that blocks Companion initialize
VENV=$(dirname $(dirname "$0"))/venv
FILE="$VENV/lib/python3.12/site-packages/pyatv/protocols/companion/__init__.py"
if grep -q "skip-power" "$FILE"; then
  echo "Patch already applied."; exit 0
fi
python3 <<EOF
src = open("$FILE").read()
new = src.replace(
    "            system_status = await self.api.fetch_attention_state()",
    """            try:
                system_status = await asyncio.wait_for(self.api.fetch_attention_state(), timeout=3)
            except Exception:
                _LOGGER.warning("FetchAttentionState failed (tvOS 26.x bug), skipping power_state")
                system_status = None
            if system_status is None:
                raise Exception("skip-power")  # jump to outer except""")
open("$FILE","w").write(new)
print("Patched.")
EOF
