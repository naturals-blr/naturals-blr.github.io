# Project Context: Naturals Salon & Spa Bangalore

This document provides a focused overview of the repository's file structure, styling patterns, and how the five store locations are managed within the codebase. For a more exhaustive technical reference, please see the existing `NATURALS_PROJECT_CONTEXT.md`.

## 1. File Structure
The project is a statically generated website with the following key directories and files:

- **Root HTML Files**: Standalone pages such as `index.html`, `services.html`, `offers.html`, `contact.html`, and `about.html`.
- **`stores/`**: Contains the generated HTML pages for the 5 individual store locations (e.g., `devasandra.html`, `elements-mall.html`, `frazer-town.html`, `hennur.html`, `jpnagar.html`).
- **`build/`**: The static site generation pipeline.
  - `build.py`: A Python script that fetches data and builds the site.
  - `templates/`: Contains Jinja2 layout templates (`index.html.j2`, `header.j2`, `macros.j2`, `store.html.j2`, etc.).
- **`images/`**: Assets organized by context (`heroes/`, `services/`, `offers/`, `stylists/`).
- **Review Automation**: References exist for a Node.js-based review automation bot, configured via YAML files and separate scripts.

## 2. Styling Patterns
The repository strictly avoids external CSS frameworks (like Tailwind or Bootstrap) in favor of a highly custom, lightweight approach:

- **Vanilla CSS & Variables**: The design system relies heavily on CSS variables mapped to the `:root` pseudo-class (`--dark`, `--green`, `--gold`, etc.) located within embedded `<style>` blocks.
- **Theming**: A dual-theme system exists (Default "Luxury" vs. "Naturals" purple brand theme) toggled via a `[data-theme="naturals"]` attribute and persisted via `localStorage`.
- **Typography**: Uses modern Google Fonts: **Cormorant Garamond** (serif) for premium, elegant headings and **Jost** (sans-serif) for clean body copy.
- **Responsiveness**: Hand-written `@media` queries are utilized at `1024px` (tablet), `640px` (mobile), and `400px` (narrow mobile). Mobile features include a fixed bottom sticky bar containing action CTAs.

## 3. Store Locations Management
The 5 store locations (JP Nagar, Elements Mall, Devasandra, Frazer Town, and Hennur) are actively managed through a hybrid data/build pipeline:

- **Data Layer (Google Sheets)**: Store details, services availability, offers, and stylists are all maintained in a central Google Sheet. Business users can edit this without touching code.
- **Build Generation (`build.py`)**: The `build.py` script fetches data via Google Sheets CSV exports. It normalizes data (like phone numbers) and uses Jinja2 to dynamically render the `store.html.j2` template 5 times (once per active store). The output results in the static files saved in the `stores/` directory.
- **Client-Side Personalization**: The site heavily uses JavaScript and `localStorage` (`naturals-store` key) to remember the user's selected location. Action buttons for Book, WhatsApp, Call, and Directions rely on a `storePickerThen()` JavaScript function to dynamically apply the correct store's details and active branch data across the UI.

## 4. Button & Colour Standards
The application's calls to action (CTAs) adhere to the following strict color requirements to ensure uniformity and clarity in all the pages, including the home page, services page, offers page, contact page, and store pages and the sticky :
- **Book Now (Appointment)** - Blue (`#1A73E8`, matching the Google Appointment button style in Google Maps)
- **WhatsApp** - Green (`#25D366`, the native WhatsApp green color)
- **Call Now** - Grey Color (`#5F6368`)
- **Directions** - Red (`#D93025`)

## 5. Stylists
The stylists are managed in the Google Sheet and are displayed in the services page and store pages. The stylists are displayed in a grid layout and are displayed in alpha order by their name. If the stylists photo is not avalable in /images/stylists then the default photo stylist_default.png is displayed. The stylist photo is displayed in a circular frame. The stylist photo to be displayed is 200x200px.

## 6. Recent Enhancements & UI Standards
- **Store Pages (`store.html.j2`)**: Enhanced the above-the-fold layout by updating the `<h1>` format and adding a localized subtitle. Introduced a `store-reviews` block, restructured the CTA hierarchy to emphasize the primary "Book Appointment" button, overhauled the "What We Offer" section with detailed service listings and pricing, and integrated dynamic stylist data (ensuring at least 3 stylists per store with a "Book Stylist" CTA). A placeholder gallery section was also added.
- **Service Categories (`services.html.j2`)**: The Service filter maintains its classic `<select>` dropdown format functionality within the `cat-select-wrap` layout as per standard requirements.
- **Global Header Normalization**: A unified `header.j2` acts as the single source of truth for the top navigation (Logo + Hamburger Drawer). Legacy `<nav>` styling was stripped individually from `services.html.j2`, `contact.html.j2`, `offers.html.j2`, and the policy pages to ensure the global header functions consistently across all pages without visual collision.
