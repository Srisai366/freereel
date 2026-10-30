# Monthly infrastructure cost estimation

Figures checked on **2026-10-30** against vendor pages and recent reviews. Free tiers
change, so re-check each vendor's pricing page before relying on these numbers.
Nothing here is unlimited.

## Free-tier facts used

| Service | Free allowance | What starts charging |
|---|---|---|
| Cloudflare R2 | 10 GB-month storage, 1M Class A (writes/lists), 10M Class B (reads) per month, **egress free** | $0.015/GB-month storage, $4.50/M Class A, $0.36/M Class B |
| Cloudflare CDN (R2 custom domain) | Included | — |
| Cloudflare Workers (frontend) | Free plan daily request limit (check current figure) | Workers Paid ($5/month) if exceeded |
| Render web service | 750 instance-hours/month, spins down after 15 min idle; small RAM (~512 MB, unconfirmed) | Starter instance (~$7/month) for always-on. A third-party review reports a Render plan change on 2026-08-01 that cut bandwidth, so check current terms |
| Supabase Postgres | 500 MB DB, 2 active projects, pauses after ~7 days idle, no backups | Pro ~$25/month |
| Neon Postgres (alternative) | Small free DB with autosuspend | Paid plans |
| AWS (new accounts since July 2025) | Up to $200 credits, free plan ends after 6 months or when credits run out | Everything after that |
| AWS CloudFront | 1 TB transfer + 10M requests per month, always-free | ~$0.085/GB beyond (US/EU; India is higher) |
| GitHub Actions | Free for public repos; private repos get a monthly minute quota | Extra minutes |

## Assumptions

- Average film: 100 minutes. HLS bitrates: 360p 0.8 Mbps, 480p 1.4, 720p 2.8, 1080p 5.0.
- Storage for all four renditions ≈ 100 min × 10 Mbps ≈ **7.5 GB per film** (≈ 4 GB without 1080p).
- Average watched data per play ≈ 40 min at a 2.8 Mbps mix ≈ **0.85 GB**.
- Laptop does transcoding (free).

## Scenarios

| Stage | Library | Plays / month | Bandwidth | Storage | Estimated monthly cost |
|---|---|---|---|---|---|
| Launch | 5 films (720p max) | 500 | ~0.4 TB | ~20 GB | **$0–1** (R2 storage over 10 GB: ~$0.15; all else free) |
| Growing | 30 films | 10,000 | ~8.5 TB | ~150 GB | **~$10–35** — R2 ~$2.10 storage, egress $0; Render Starter $7 (no cold starts); Supabase Pro $25 is optional |
| Established | 200 films | 100,000 | ~85 TB | ~1.2 TB | **~$60–120** — R2 ~$18 + operations; bigger API instance; Postgres Pro; Workers Paid $5 |
| Same 100k plays on AWS S3 + CloudFront | | | 85 TB | 1.2 TB | **~$6,000+** for CloudFront egress alone. Only move video delivery to AWS with negotiated pricing |

**Takeaway:** keep video on R2. Move the API and database to AWS when you need SLAs or
VPC features. Video delivery is what makes AWS expensive.

## Budget alerts (do this on day one)

- **Cloudflare:** Billing → set a usage notification for R2 storage and operations.
- **Render / Supabase:** keep services on the free plan and don't add a payment method
  until needed. Supabase's spend cap stays on by default.
- **AWS** (when you start):
  ```powershell
  aws budgets create-budget --account-id <ACCOUNT_ID> `
    --budget '{"BudgetName":"monthly-5usd","BudgetLimit":{"Amount":"5","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' `
    --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.com"}]}]'
  ```

## Services that can generate surprise charges

- AWS NAT Gateway (~$32/month plus data, even idle). Avoid it in the MVP.
- AWS RDS after the free plan ends (~$15+/month for the smallest instance).
- CloudFront/S3 egress beyond the free allowance.
- Elastic IPs that aren't attached to a running instance.
- Render bandwidth overage. Video doesn't pass through Render in this design, so this stays low.
