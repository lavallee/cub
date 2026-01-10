#!/bin/bash
# Set parent relationships for tasks based on phase labels

# Epic IDs by phase
EPIC_PHASE_1="curb-1gq"  # Foundation
EPIC_PHASE_2="curb-0pb"  # Reliability
EPIC_PHASE_3="curb-htk"  # Extensibility
EPIC_PHASE_4="curb-9pe"  # Polish

echo "Setting parent relationships..."

# Phase 1 tasks
for id in curb-iwv curb-1l6 curb-0u2 curb-et7 curb-ohp curb-13j curb-0b5 curb-kiz curb-hp9; do
  echo "  $id -> $EPIC_PHASE_1 (Foundation)"
  bd update $id --parent $EPIC_PHASE_1
done

# Phase 2 tasks
for id in curb-co7 curb-g21 curb-vdw curb-4l8 curb-0ub curb-0hz curb-rvl curb-iji curb-fxr; do
  echo "  $id -> $EPIC_PHASE_2 (Reliability)"
  bd update $id --parent $EPIC_PHASE_2
done

# Phase 3 tasks
for id in curb-xo3 curb-zrg curb-ffn curb-4wz curb-3s0 curb-d9l curb-lop curb-kod curb-fpg curb-tw9 curb-ch2; do
  echo "  $id -> $EPIC_PHASE_3 (Extensibility)"
  bd update $id --parent $EPIC_PHASE_3
done

# Phase 4 tasks
for id in curb-gp6 curb-zlk curb-2d6 curb-ehj curb-a4p curb-god curb-61a; do
  echo "  $id -> $EPIC_PHASE_4 (Polish)"
  bd update $id --parent $EPIC_PHASE_4
done

echo "Done! Syncing..."
bd sync
echo "Parent relationships set."
