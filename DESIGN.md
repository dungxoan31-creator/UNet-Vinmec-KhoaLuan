# VINMEC Premium Healthcare — Product UI

## Direction

Operate-mode interface for repeated clinical research review. The Taste Skill `framed-sheet` direction (seed `1365840150`) is the starting composition: pale-blue frame, white working surface, quiet borders, and no resting panel shadow. The supplied brief pins a navy sidebar and white header, so those replace the direction's neutral chrome. Do not restore the discarded light sidebar.

The face is the unchanged VINMEC full mark on a white tile, paired with the explicit ovarian-ultrasound and RUO product label. The product-specific working element is the existing dark image-review workspace with its segmentation overlay, laterality, caliper, and reviewer controls; keep its image geometry and interaction semantics intact.

## Tokens

- Brand blue `#187DBB`; accessible interaction blue `#0059B8`.
- Brand gold `#D99A2B`, used sparingly; pale gold `#FFF3D8`.
- Application ground `#F2F8FC`; white surface `#FFFFFF`; soft surface `#EAF4FA`.
- Sidebar `#102A43`; hover `#1C4665`.
- Text `#243746`; secondary text `#64748B`; border `#E2E8F0`.
- Success `#16805D`; warning `#B7791F`; error `#C93636`; info `#1479B8`.
- Inter is self-hosted with Vietnamese glyph coverage. Keep tabular figures for measurements and identifiers.
- Use the shared spacing scale, 8–16px surface radii, 24px desktop content gutter, 8px sheet inset, and 1px borders. No gradients or resting card shadows.

## Shell and Components

- White header with the supplied logo at its original aspect ratio and a compact product label.
- Navy labelled navigation on desktop; on narrow screens, use a keyboard-operable off-canvas menu with visible labels.
- White content sheet on the pale-blue page frame. Keep its title, controls, tables, and data aligned to one content grid.
- Use semantic status colors only for their meaning. Provide visible keyboard focus, error/loading/empty states, and sufficient text contrast.
- Keep the ultrasound viewer on a dark neutral surface. Controls, overlays, measurements, and image coordinates must not move or change meaning as a result of visual styling.
- Use white or very pale blue behind the VINMEC logo; never filter, recolor, distort, or recreate it.

## Responsive and Motion

Verify at 375px, 768px, 1280px, and 1440px. Fold the sidebar into a labelled drawer on mobile, stack data blocks without clipping, and preserve deliberate horizontal scrolling for wide tables. Motion is limited to short interaction feedback; respect `prefers-reduced-motion`.

## Scope Guard

Visual redesign only. Do not change backend behavior, API contracts, clinical rules, image geometry, measurement calculations, or review state transitions. Preserve RUO disclosures and do not imply clinical validation or institutional endorsement.
