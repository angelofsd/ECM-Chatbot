# Details

Date : 2025-10-30 16:20:08

Directory c:\\Users\\angela\\dev\\ECM-Chatbot

Total : 56 files,  12295 codes, 1216 comments, 1620 blanks, all 15131 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.dockerignore](/.dockerignore) | Ignore | 28 | 8 | 8 | 44 |
| [AGENTS.md](/AGENTS.md) | Markdown | 220 | 0 | 69 | 289 |
| [OPENAI\_SETUP.md](/OPENAI_SETUP.md) | Markdown | 114 | 0 | 48 | 162 |
| [PHASE3\_SUMMARY.md](/PHASE3_SUMMARY.md) | Markdown | 238 | 0 | 71 | 309 |
| [PROJECT\_STRUCTURE.md](/PROJECT_STRUCTURE.md) | Markdown | 338 | 0 | 85 | 423 |
| [QUICKREF.md](/QUICKREF.md) | Markdown | 102 | 0 | 41 | 143 |
| [README.md](/README.md) | Markdown | 240 | 0 | 71 | 311 |
| [STATUS\_REPORT.md](/STATUS_REPORT.md) | Markdown | 323 | 0 | 79 | 402 |
| [TESTING.md](/TESTING.md) | Markdown | 126 | 0 | 42 | 168 |
| [TEST\_RESULTS.md](/TEST_RESULTS.md) | Markdown | 170 | 0 | 63 | 233 |
| [api/\_\_init\_\_.py](/api/__init__.py) | Python | 1 | 9 | 2 | 12 |
| [api/answer\_generator.py](/api/answer_generator.py) | Python | 147 | 69 | 35 | 251 |
| [api/app\_simple.py](/api/app_simple.py) | Python | 206 | 30 | 29 | 265 |
| [api/config.py](/api/config.py) | Python | 75 | 52 | 24 | 151 |
| [api/db.py](/api/db.py) | Python | 179 | 66 | 65 | 310 |
| [api/embeddings.py](/api/embeddings.py) | Python | 119 | 54 | 40 | 213 |
| [api/extractors/\_\_init\_\_.py](/api/extractors/__init__.py) | Python | 0 | 11 | 1 | 12 |
| [api/extractors/email\_extractor.py](/api/extractors/email_extractor.py) | Python | 178 | 72 | 37 | 287 |
| [api/ingest.py](/api/ingest.py) | Python | 326 | 109 | 98 | 533 |
| [api/ingest\_pdf.py](/api/ingest_pdf.py) | Python | 223 | 86 | 62 | 371 |
| [api/llm.py](/api/llm.py) | Python | 112 | 92 | 28 | 232 |
| [api/main.py](/api/main.py) | Python | 177 | 89 | 62 | 328 |
| [api/requirements.txt](/api/requirements.txt) | pip requirements | 32 | 12 | 11 | 55 |
| [api/retriever.py](/api/retriever.py) | Python | 195 | 119 | 65 | 379 |
| [api/security.py](/api/security.py) | Python | 94 | 71 | 36 | 201 |
| [docker-compose.yml](/docker-compose.yml) | YAML | 38 | 0 | 4 | 42 |
| [docker-init-db.sh](/docker-init-db.sh) | Shell Script | 6 | 3 | 2 | 11 |
| [fix\_qdrant\_full\_text.py](/fix_qdrant_full_text.py) | Python | 120 | 21 | 31 | 172 |
| [ingest\_emails\_batch.py](/ingest_emails_batch.py) | Python | 112 | 29 | 35 | 176 |
| [ingest\_pool.py](/ingest_pool.py) | Python | 172 | 41 | 54 | 267 |
| [init-db.sql](/init-db.sql) | MS SQL | 2 | 4 | 3 | 9 |
| [ocr\_prepare.py](/ocr_prepare.py) | Python | 154 | 13 | 21 | 188 |
| [pg\_hba.conf](/pg_hba.conf) | Properties | 5 | 4 | 1 | 10 |
| [quick\_fix\_qdrant.py](/quick_fix_qdrant.py) | Python | 44 | 7 | 13 | 64 |
| [rebuild\_qdrant\_full\_text.py](/rebuild_qdrant_full_text.py) | Python | 117 | 24 | 37 | 178 |
| [rebuild\_simple.py](/rebuild_simple.py) | Python | 85 | 18 | 26 | 129 |
| [rebuild\_vectors.py](/rebuild_vectors.py) | Python | 78 | 16 | 22 | 116 |
| [requirements.txt](/requirements.txt) | pip requirements | 14 | 0 | 1 | 15 |
| [test\_basic.py](/test_basic.py) | Python | 81 | 13 | 11 | 105 |
| [test\_e2e.py](/test_e2e.py) | Python | 98 | 16 | 22 | 136 |
| [test\_llm\_phase2b.py](/test_llm_phase2b.py) | Python | 97 | 14 | 26 | 137 |
| [test\_system.py](/test_system.py) | Python | 111 | 17 | 19 | 147 |
| [ui/README.md](/ui/README.md) | Markdown | 133 | 0 | 58 | 191 |
| [ui/app/globals.css](/ui/app/globals.css) | PostCSS | 56 | 0 | 4 | 60 |
| [ui/app/layout.tsx](/ui/app/layout.tsx) | TypeScript JSX | 19 | 0 | 4 | 23 |
| [ui/app/page.tsx](/ui/app/page.tsx) | TypeScript JSX | 95 | 6 | 13 | 114 |
| [ui/components/ChatInput.tsx](/ui/components/ChatInput.tsx) | TypeScript JSX | 62 | 3 | 9 | 74 |
| [ui/components/ChatMessage.tsx](/ui/components/ChatMessage.tsx) | TypeScript JSX | 74 | 3 | 8 | 85 |
| [ui/next-env.d.ts](/ui/next-env.d.ts) | TypeScript | 0 | 4 | 2 | 6 |
| [ui/next.config.js](/ui/next.config.js) | JavaScript | 8 | 1 | 2 | 11 |
| [ui/package-lock.json](/ui/package-lock.json) | JSON | 6,343 | 0 | 1 | 6,344 |
| [ui/package.json](/ui/package.json) | JSON | 37 | 0 | 1 | 38 |
| [ui/postcss.config.js](/ui/postcss.config.js) | JavaScript | 6 | 0 | 1 | 7 |
| [ui/tailwind.config.ts](/ui/tailwind.config.ts) | TypeScript | 53 | 1 | 1 | 55 |
| [ui/tsconfig.json](/ui/tsconfig.json) | JSON with Comments | 57 | 0 | 1 | 58 |
| [update\_payloads.py](/update_payloads.py) | Python | 55 | 9 | 15 | 79 |

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)