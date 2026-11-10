---
name: primeqe-universal-web-app-excellence
description: Apply PrimeQE's portfolio-wide engineering, UX, QA, accessibility, security, routing, data quality, branding and deployment standards to every app change.
---
# PrimeQE Universal Web App Excellence
Mandatory during development, code review, bug fixes, refactoring and releases. Preserve existing app features, URLs, users' data, saved progress, schedules, counters, integrations and history. Do not simulate functionality.

## P0 release blockers
- WCAG 2.2 AA-oriented text/control legibility in default, hover, active/clicked, focus, selected, disabled, loading and error states, both themes; 4.5:1 normal text and 3:1 large text/UI components, semantic markup, keyboard focus/navigation, labels and responsive touch targets.
- Every significant page has its own stable, directly loadable URL. Check deep links, refresh, browser back/forward and legacy redirects.
- Favicon must visually match official logo; use crisp responsive brand assets, accurate labels, title/meta and correct product identity.
- Validate working navigation, search, filter, forms, CRUD, sorting, import/export, link handling, empty/error states, mobile layout and regression coverage. A visual test is not proof of behavior.
- Secure secrets, sanitize inputs, enforce auth/RBAC and tenant boundaries server-side where relevant; prevent data leakage.
- Never silently remove user content, integrations, live data sources or functionality.

## P1 relevant capabilities
- Freshness: cite official source, true last-refreshed time and timezone; actual scheduled/event-driven refresh where needed; communicate failed/stale sync. No fake realtime badges.
- Useful collapsible sidebar, searchable content, keyboard controls, loading/empty/error/retry states and clear dark mode.
- Offline-first caching, backups, import/export and transparent storage/sync status only where useful.
- Working instructional videos (verify playable), accessibility and mobile performance.
- Verified data provenance, deduplication, original rates and dated PHP equivalents for opportunities; useful source links.
- Archive Catalog: maintain canonical URL, title, logo/favicon, description, category, screenshots and correct status if authorized access exists.

## P2 when appropriate
- Competitive differentiation substantiated by researched competitor features.
- Hackathon readiness: compelling use case, working demo, evidence/audit export, documentation, safe sandbox and explicit limitations.
- Authentic backend operations for scheduler/task pause/resume/force-run/progress, role controls, multi-tenancy and exports.

## Mandatory execution loop
1. Inventory project source, routes, relevant data/integrations and production deployment.
2. Build an applicability matrix; mark capabilities applicable or N/A with reason.
3. Implement reversible, minimal, testable changes without damaging functionality.
4. Verify build, unit/integration checks, actual interactions, contrast, mobile, keyboard, security, recovery, offline and routing as relevant.
5. Publish only when authorized; verify the deployed URL and update catalog when connected.
6. Report per-app files/commits, verified fixes, deployed status and open gaps. Never claim tests or releases without evidence.

Application-specific preservation: Task Pulse uses actual automations state/counters; maritime/jobs/TESDA/events need genuine dated sources; Training Academy/SkillSpring needs genuine playable course videos and saved progress; QE Nexus/ALex/Terra preserve domain evidence and access controls; FloodSolve preserves hazard evidence quality and explicit offline limitations.
