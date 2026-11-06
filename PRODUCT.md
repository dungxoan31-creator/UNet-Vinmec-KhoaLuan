# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are clinicians and trained reviewers who inspect ovarian ultrasound images and verify AI-generated segmentation in a human-in-the-loop workflow. Administrators configure access and research operations.

## Product Purpose

This research-use-only prototype supports ovarian ultrasound image review, mask correction, measurements, and deterministic decision-support workflows. It does not provide a diagnosis or replace a clinician's assessment.

## Positioning

The workflow keeps the reviewer in control: AI output remains a proposal that can be inspected and corrected before a review is saved.

## Operating Context

The web application is served by FastAPI and uses a browser-based canvas for image review. The repository supports local SQLite operation; PostgreSQL runtime readiness is not established. Testing and demonstrations must use synthetic data unless an approved environment is provided.

## Capabilities and Constraints

- Existing API contracts, image coordinates, measurements, clinical rules, validation, and review workflow are outside the scope of visual redesign.
- Preserve the dark neutral image-viewing surface and the existing Human-in-the-Loop review controls.
- Clinical validation, patient-level independence, hospital deployment approval, and authorization for patient care remain unverified.
- Keep the research-use-only notices visible and distinguish abnormal findings from malignancy.

## Brand Commitments

- Use the supplied VINMEC logo asset at `Biểu tượng VINMEC vàng xanh tinh tế.png` without altering its colors or proportions.
- Use the user-provided VINMEC blue, gold, pale-blue, and navy palette, with accessible functional shades where needed.
- Keep the visible product scope clear: ovarian ultrasound research prototype, RUO.

## Evidence on Hand

- Supplied logo asset: `Biểu tượng VINMEC vàng xanh tinh tế.png`.
- Repository contains source code and synthetic workflow tests. No clinical validation package or expert-approved reference set is established by this product record.

## Product Principles

- Keep the clinician in control of review and confirmation.
- Keep image, laterality, coordinate, and measurement context visible and unambiguous.
- Show uncertainty and missing data plainly; do not invent clinical evidence.
- Preserve RUO limits wherever the workflow may be mistaken for patient care.

## Accessibility & Inclusion

Target WCAG 2.2 AA for the web interface, including keyboard access, visible focus, readable contrast, and responsive layouts at desktop, tablet, and mobile widths.
