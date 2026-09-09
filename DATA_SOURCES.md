# Data Sources

Financial statements and company announcements are obtained from CNINFO. The source register records each document's disclosure date, URL, version, PDF page, and SHA-256 hash.

| Source | Coverage | Location |
|---|---|---|
| Midea Group (`000333.SZ`) | Annual and quarterly disclosures, 2019–2026 | [2024 Annual Report](https://static.cninfo.com.cn/finalpage/2025-03-29/1222951181.PDF) |
| Chuanzhi Education (`003032.SZ`) | Annual and quarterly disclosures, 2022–2025 | [2023 Annual Report](https://static.cninfo.com.cn/finalpage/2024-04-16/1219619115.PDF) |
| Risk-warning announcements | Event announcement and implementation dates | [Delisting risk-warning notice](https://static.cninfo.com.cn/finalpage/2025-04-22/1223197666.PDF) |
| Chinese FinBERT | Text encoder, revision `e91b1a3af10e1e8c9c03429d3cd7d5e9a1c8000d` | [Model repository](https://huggingface.co/yiyanghkust/finbert-tone-chinese) |

Coverage describes the periods represented by the included documents, not a complete company panel. All 26 source URLs are stored in `data/raw/records.json`. To download the PDFs into `data/raw/disclosures/`, run:

```bash
python -m distress download-sources
```

Company names and document titles use English display labels. Source PDFs retain their original language. Financial values retain their original units and signs, with normalized amounts in CNY and share counts in shares. Net profit includes non-controlling interests. PDF page numbers start at one.

Only disclosures available before the prediction date enter predictors. Later restatements are retained as separate versions. Unknown outcomes remain blank; they are not treated as non-distress. The text model's training-data cutoff is unknown, so its availability at earlier prediction dates is unverified.
