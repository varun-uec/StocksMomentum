# Contributing to Wickstreet

Thank you for helping. This file says how to set up, what every change must pass, and the rules the project does not bend.

## Set up

```bash
make backend-install      # Python 3.12 and uv; installs the locked versions
make web-install          # Node 22
cp .env.example .env
docker compose up -d db redis
```

Tests need PostgreSQL. They refuse any database whose name does not end in `_test`. End-to-end tests run against a clone whose name ends in `_e2e` (`make e2e-db`, then set `E2E_DATABASE_URL`).

## Every change must pass

```bash
cd backend
uv run ruff check src tests
uv run mypy src           # strict
uv run lint-imports       # dependencies point inward
uv run pytest
cd ../web
npm run lint && npm test && npm run build
npm run gen:api && git diff --exit-code src/lib/api-schema.ts   # when the API changed
E2E_DATABASE_URL=... npm run e2e                                  # when the web app changed
```

Do not weaken an assertion to make a test pass. A business change comes with a test that fails without it.

## Rules

- **Architecture.** Hexagonal: domain, application, infrastructure, interface. The domain does no I/O. Read [`docs/architecture/`](docs/architecture/) before changing structure. A change to an accepted ADR needs a new ADR or an amendment, not a quiet edit.
- **Determinism (ADR-009).** The same inputs give the same scores, ranks and explanations. No hidden state, no randomness, no wall-clock reads in business logic.
- **No guessing.** Do not invent business rules, data or thresholds. If something is missing, say so and ask.
- **Strategies are data (ADR-005).** Rule parameters have declared bounds (ADR-014 §2). A new parameter needs a schema entry.
- **Research results.** Only the Strategy Studio's three labels describe evaluated performance: Screening Result, Historical Research — In-Sample, Out-of-Sample Evaluation (ADR-014 §5). Never call a result "validated".
- **Clean room.** TradingView and OpenChart are usability references only. Do not copy their code, names, logos or assets.
- **Data.** Do not commit market data, database dumps or credentials. NSE's terms apply to each user's own retrieval ([ADR-012](docs/architecture/adr/ADR-012-open-source-self-hosted.md)).
- **Dependencies.** Add one only when a few lines of code cannot do the job. Lock it (`uv lock`, `package-lock.json`).
- **Writing.** Short sentences, active voice, one term for one thing. This applies to code comments, commit messages, docs and UI text (see `Claude.md`, "Writing").

## Licence

The licence is still to be chosen ([ADR-015](docs/architecture/adr/ADR-015-licence.md)). Until it is, please do not send contributions you are not willing to license under it.
