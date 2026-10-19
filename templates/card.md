# Card <ID>: <one-line title>

- **Maker:** <role/model> · **date:** <clock read> · **parent:** <spec or plan item>
- **Goal it serves:** <the goal-list line this advances>

## What and why
<2-5 lines: the change and the reason. Link the finding, spec or ruling.>

## Write set (the ONLY files the builder may change)
- `<path>`: <what changes>
- `<probe path>`: <new or changed asserts>
- generated: `<dist/ ...>` (rebuilt by the suite, never hand-edited)

## Decisions
- Taken: <decision> (by <who>, <provisional?>)
- Needs user: <item>, or "none"

## Behaviour contract
- Flag: `<SETTINGS.x>`, default **OFF** (or: why not)
- Flag OFF: behaviour is byte-identical to before (how this is proven: <digest / parity probe>)
- Flag ON: <what changes>

## Edits this card licenses
<Every existing assert, count or snapshot the change necessarily moves. Name each one with its old and new value. If none: "none".>

## Exit criteria (each satisfiable and visible to the named instrument)
1. <instrument / command> shows <measured pair, e.g. AFTER == BEFORE + 1>
2. New probe assert <name>: RED on the old code, GREEN on the new (3 standalone runs)
3. Mutations M1..Mn: each turns <assert> RED for <reason>
4. Suite gate: the suite's own line `N failing; allowlist = M`, N == M, with the same failing set as the baseline
5. Lint and hygiene: <command> = <value>

## Risks and order
- Interacts with <other cards>; must run after <ID> (precondition: `git log` shows `[<ID>]`)
