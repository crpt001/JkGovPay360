# GovPay 360 — live official-order index starter

This package preserves the existing GovPay 360 calculator app and adds a **hosted, scheduled index** of official J&K General Administration Department (GAD) order-list records. It does not claim to attach PDFs when the source only exposes a record page.

## Personalised Government Order Alerts

- The Home screen includes topic preferences for DA/HRA, pay/arrears, pension/NPS/UPS/OPS, promotion/service, leave/conduct, recruitment, and SLI/benefits.
- The alert list combines the hosted live index with the app’s curated summaries and clearly labels each record type.
- On first successful load, existing live-index entries are treated as the baseline; records appearing in later feed refreshes are marked NEW / UNREAD on that device.
- **Check updates** re-fetches the hosted JSON feed and can show a browser notification for a new matching record if permission has been granted.
- Browser notifications require HTTPS and only fire when the app is open and a check is run. True background push notifications would require an additional push-notification service and service worker; this package does not claim to provide that.
- Topic preferences and read status are stored in that browser/device’s local storage and are not synced across devices.

## What the live sync does

- Runs automatically every 6 hours through GitHub Actions, and can also be run manually.
- Checks the official GAD lists for Orders, Circulars, Notifications, and SRO/SO records.
- Saves official record metadata and source links in `data/live-archive.json`, retaining previously indexed records across runs.
- Shows the records in separate **Live official orders** and **Live official SROs / rules** areas in the app.
- Shows a direct PDF button only when a direct PDF URL is detected. Otherwise it labels the action **Open official record**. It never invents a PDF or describes a summary as an original.
- Deploys the app to GitHub Pages on pushes to `main`; the scheduled sync workflow also deploys after a successful refresh, because pushes made with `GITHUB_TOKEN` do not trigger other workflows.

Official sources used by the index:
- https://jkgad.nic.in/En/OrderCirculer.aspx?ordType=O
- https://jkgad.nic.in/En/OrderCirculer.aspx?ordType=C
- https://jkgad.nic.in/En/OrderCirculer.aspx?ordType=N
- https://jkgad.nic.in/En/OrderCirculer.aspx?ordType=S

## One-time setup (required for automatic updates)

1. Create a new GitHub repository and upload the contents of this folder (keep `.github/workflows/` and `data/`).
2. Use `main` as the default branch, or change the branch in `.github/workflows/deploy-pages.yml` to match your default branch.
3. In repository **Settings → Pages**, set the build/deployment source to **GitHub Actions**.
4. Open **Actions → Sync official J&K orders and rules index → Run workflow** once. The workflow also runs every 6 hours after setup.
5. The Pages deployment workflow publishes `GovPay360.html` as the site home page and serves the JSON feed beside it.
6. Open the GitHub Pages URL shown under **Settings → Pages**. Do not open the HTML as a local file if you want live sync; browsers block local `file://` fetches.

## Important limitations

- This package is prepared for deployment; it is **not yet hosted or connected to your GitHub account**. I cannot turn on scheduled execution until you upload it to a repository you control.
- The scraper reads the latest listing page for each category. The frequent schedule reduces the chance of missing new entries, but if the government site publishes more than one page of new entries between runs, records could be missed. It also depends on the source site retaining its current HTML structure.
- The listing page may not expose a direct PDF link. When it does not, the app links to the official record page and does not claim a PDF is attached.
- This initial feed is not a full historical crawl of every record ever issued. It accumulates records observed after deployment; the app's existing curated library remains available separately.
- Automatically indexed titles are not legal interpretations. Read the original order/rule and verify amendments before relying on it.

## Validation included

- The parser reads actual table rows rather than scanning every page link, so menu/pager links are not treated as orders.
- The parser rejects JavaScript postback URLs and only labels a URL as a direct PDF when its path ends in `.pdf`.
- Unit tests cover record-row extraction, date parsing, source URLs, direct PDF detection, and ignoring pager/navigation links.
- The scheduled workflow runs these tests before it updates the feed.

## Local test

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python sync_orders.py
```

The script refuses to replace the feed if it cannot parse any official listing, and retains the existing feed if one or more categories temporarily fail.


## Employee Toolkit additions (local-device tools)

The Toolkit tab adds: a personal service-record form; increment/promotion milestone tracker; gross arrears estimator; deadline/follow-up tracker; editable letter draft generator with copy/download; search across the currently loaded curated and live order/rule records; and JSON export/import backup of GovPay 360 localStorage keys. These records remain in the user's browser and are not synced to a server. The arrears calculator is a simple gross difference estimate, not a legal entitlement or payroll computation. Letter drafts are templates requiring verification.

Existing screens already provide salary and tax estimates, pay matrix/fixation, NPS/UPS/OPS tools, retirement roadmap/gratuity/SLI, official order archive and personalised order alerts. These are retained. The live archive still requires hosting and the scheduled workflow to be configured as described above.


## Security and reliability patches

- Backup imports are limited to known GovPay 360 keys, capped at 5 MB, validated before writes, and rolled back where possible if a storage write fails.
- Toolkit remove buttons use data attributes and delegated listeners instead of interpolating record IDs into inline JavaScript.
- Profile-save storage failures are shown to the user instead of silently ignored.
- A successful scheduled sync deploys the refreshed JSON feed in the same workflow run.
- Financial calculator results still require independent rule-by-rule verification before production use.
