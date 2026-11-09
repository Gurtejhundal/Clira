# 19 — CLIRA Brand Identity and Product Naming Contract

## Confirmed working brand
- **Product:** Clira
- **Tagline:** Your Creative Intelligence.
- **Category:** General-purpose AI YouTube channel management agent (not an official YouTube product).
- **Character:** Female-coded classical-muse-inspired assistant; intelligent, approachable, strategic and creative.
- **Etymology:** Newly coined name influenced by *Clio* (Greek Muse of history) and *Minerva* (Roman goddess of wisdom). This is creative naming, **not a historically attested Greek/Latin word**.
- **Brand status:** Chosen for the project, but trademark, domain, handles and market clearance are **not verified**.

## Character/logo art direction (future task; no logo included in this pack)
- Create a distinctive illustrated female character inspired by classical myth, **not a reproduction of Hermes or another existing mascot**.
- Recognizable silhouette; restrained laurel or celestial ornament; expressive face; simple emblem representing guidance and publishing.
- Provide portrait, app-icon, and wordmark variants. Ensure the icon reads at small sizes.
- Suggested exploratory palette: charcoal, warm ivory, antique gold; not binding until design review.
- Avoid generic floating AI heads, corporate gradient 'C' icons, and costume details that only work at poster scale.

## Voice and personality
- Clear, practical, direct, resourceful; creative when planning and precise when taking account actions.
- No fabricated metrics, no false promises of virality, and no pretending an upload is complete unless YouTube confirms it.
- Always state the target channel before upload or publication.

## Engineering conventions
- Package/repository: `clira`
- UI display name: `Clira`
- Env key: `APP_DISPLAY_NAME=Clira`
- Default assistant greeting only where needed: `What should we work on for your channel?`
- Never use Hermes as an internal orchestration dependency. Lemo-Opuscar is an **optional external** production provider.
- Keep brand strings in one configuration file, not embedded across business logic.

## Pre-launch checks
Search trademark databases, domain registration and social handles in intended countries before commercial launch. Existing search-derived name proposals are historical alternatives, not the selected product name.
