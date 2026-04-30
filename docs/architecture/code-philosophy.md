# Code Philosophy — Grounding Document for Claude Code

**Purpose:** This document defines the principles, priorities, and practices that govern all code written or modified in this codebase. It is synthesized from Martin (*Clean Code*), Ousterhout (*A Philosophy of Software Design*), Hunt & Thomas (*The Pragmatic Programmer*), and McConnell (*Code Complete*). Where those sources conflict, this document resolves the tension with an explicit stance.

---

## 1. The Single Imperative

**Managing complexity is the only job.** Every line of code, every module boundary, every naming choice either reduces or increases the amount of the system a developer must hold in their head to make a correct change. There is no second priority that overrides this.

> "Managing complexity is the most important technical topic in software development." — McConnell

> "Complexity is incremental. It's not one particular thing that makes a system complicated, but the accumulation of dozens or hundreds of small things." — Ousterhout

**Operational test:** Before writing any code, ask: *does this reduce the amount of the system someone must understand to work on this area?* If the answer is no, redesign.

---

## 2. Strategic Over Tactical

Every change is an investment in the system's future, not a transaction against a ticket. Code that "works" but degrades the structure is a net negative.

- Never introduce complexity to finish faster.
- Never defer design improvements without explicit tracking.
- Every PR must leave the surrounding code at least slightly better than it was found (the Boy Scout Rule).
- "Fix later" without a tracked issue is "fix never."

---

## 3. The Six Pillars

### 3.1 Readability

Code is read 10x more than it is written. Optimize for the reader, not the author.

**Names are the primary documentation mechanism.** A name that requires a comment has failed. Every identifier must answer: *what is this, why does it exist, and what is its scope?*

- Names must be precise enough that a reader encountering them in isolation can guess their purpose.
- Generic names (`data`, `result`, `handler`, `info`, `manager`, `tmp`) are banned outside trivial scopes.
- Variable name length should be proportional to scope size.
- Domain-language names over implementation-language names: `mostRecentEmployee` not `stackTop`.

**Functions must operate at a single level of abstraction.** If a function mixes orchestration with implementation detail, split it. Apply the Stepdown Rule: reading top-to-bottom should descend one abstraction level at a time.

**Comments exist only to express what the code cannot:**
- *Why* a non-obvious decision was made.
- Constraints, invariants, units, or preconditions that the type system and naming cannot convey.
- Never *what* the code does — that is the code's job.
- Commented-out code is deleted immediately. Version control exists.

**Formatting serves comprehension.** Consistent indentation, blank-line separation between logical blocks, and visual grouping of related declarations. The standard is reader comprehension, not author convenience.

### 3.2 Architecture

**Modules must be deep.** The best modules provide powerful functionality behind simple interfaces. A module's value is the ratio of hidden complexity to interface surface area. Shallow modules that merely delegate are a net cost.

> "The best modules are deep: they have a lot of functionality hidden behind a simple interface." — Ousterhout

**Information hiding is the primary tool.** Each module encapsulates design decisions. The question "what should I hide?" precedes "what should I expose?" Knowledge embedded in a module's implementation must not appear in its interface.

**Single Responsibility Principle (SRP):** Each module has one reason to change. The diagnostic: *can you describe this module's purpose in under 25 words without "and," "or," or "but"?* Failure means it should be split.

**Layers must provide different abstractions.** If module A delegates to module B with the same API shape, one of them is unnecessary. Each layer must add genuine abstraction value.

**Pull complexity downward.** When inherent complexity exists, absorb it inside the module rather than exporting it to callers. A module's interface matters more than its implementation.

**Orthogonality:** Changing one module must not force changes in unrelated modules. The diagnostic: *how many files change for one functional change?* The ideal answer is one.

**Wrap all external dependencies** (APIs, libraries, storage) behind application-domain interfaces. No business logic module should know the name of a third-party library.

**No circular dependencies.** The module graph must be a DAG. If A depends on B and B depends on A, redesign.

### 3.3 Maintainability

**DRY — every piece of knowledge has a single authoritative representation.** This applies to code, validation rules, configuration, and business logic. Duplication is not merely wasteful — it guarantees future inconsistency.

**The no-duplication check is mandatory.** Before creating any new constant, utility, or validation rule: search the codebase for existing implementations. If found, use the existing one.

**All configuration values, thresholds, magic numbers, and business rules must be named constants** defined at the highest appropriate scope. Never bury a policy decision inside a low-level function.

**Refactor and feature work are separate operations.** Never mix them in the same change. Take short, deliberate, testable steps.

**Broken windows must be boarded up immediately.** Acknowledged bad code left unaddressed without explicit tracking accelerates rot faster than any other factor.

### 3.4 Robustness

**Define errors out of existence.** Before adding error handling, ask: can the API be redesigned so the condition cannot occur? An `unset()` that is a no-op on missing keys eliminates an error path. A function that returns an empty collection instead of null eliminates a null-check in every caller.

**When errors must be handled:**
- One error-handling strategy for the entire codebase, applied consistently.
- Error handling is its own concern — separated from business logic.
- Centralize handling at module boundaries, not scattered at every call site.
- No empty catch blocks. Every catch must either handle the error meaningfully or propagate it with context.
- Silent error suppression is prohibited. A dead program does less damage than a crippled one.

**Guard the impossible.** Add explicit checks for conditions believed impossible. Leave them active in production. "If it can't happen, use assertions to ensure it won't."

**Resource symmetry:** Every function that allocates a resource (listener, timer, connection, DOM node) must contain the cleanup path in the same scope.

### 3.5 Logic Correctness

**Command Query Separation.** Functions either change state or return information, never both.

**Each variable serves exactly one purpose.** No sentinel values. No hybrid coupling where a variable's type or range encodes two different things (`-1` for "not found," `null` for "error").

**Boundary conditions are tested explicitly.** Empty inputs, zero values, maximum values, off-by-one ranges, and timing edge cases each get their own test. "Don't rely on your intuition. Look for every boundary condition and write a test for it."

**Nesting beyond three levels triggers decomposition.** Use guard clauses, early returns, or extracted functions.

**Rely only on documented behaviour.** Code that depends on undocumented library behaviour, accidental sort stability, or implementation-specific browser behaviour must be identified and replaced.

**State all loop invariants.** Complex loops must have their invariant stated as a comment or assertion.

### 3.6 Abstraction

**Each module implements one Abstract Data Type.** If you cannot name the single concept a module represents, it must be decomposed.

**Consistent abstraction level within each interface.** A module that exposes both domain operations and implementation plumbing has a broken interface.

**Do not split on length alone.** Functions are split only when the split produces cleaner abstractions — a child function that is "cleanly separable from the rest of the original." Length by itself is rarely a good reason.

> "In general, developers tend to break up methods too much." — Ousterhout

**General-purpose interfaces, specific implementations.** Prefer interfaces that express primitives over interfaces that mirror specific UI operations. The general-purpose approach yields simpler, deeper interfaces.

**Abstraction and encapsulation are inseparable.** Exposing internal state as public properties destroys the abstraction. Either you have both or you have neither.

---

## 4. Resolved Tensions

Where the sources disagree, this document takes a stance.

### Function/Module Size

Martin advocates very small functions. Ousterhout argues "length by itself is rarely a good reason for splitting." McConnell sits between them.

**This codebase's stance:** Split on abstraction clarity, not line count. A 60-line function that operates at one abstraction level is preferable to six 10-line functions where the reader must trace the call chain to understand the flow. If a split does not produce a child function with a clear, nameable abstraction, do not split.

### Comments

Martin treats comments as "always failures." Ousterhout treats interface comments as essential. McConnell occupies the middle.

**This codebase's stance:** Interface comments on every non-trivial public function are mandatory. They describe *what* the function does, its parameters, return value, side effects, and constraints — not *how* it does it. Implementation comments explain *why*, never *what*. Comments that restate code are deleted. Ousterhout wins this one: "the only way to describe an abstraction is with comments."

### DRY Scope

Hunt & Thomas extend DRY to all knowledge, including documentation. Martin scopes it primarily to code.

**This codebase's stance:** DRY applies to all knowledge — code, validation rules, configuration, documentation. The broader scope catches more bugs.

---

## 5. The Pre-Flight Protocol

Before writing or modifying any code:

1. **Read the relevant existing code.** Understand what is there before changing it.
2. **Search for duplication.** `grep` the codebase for any constant, function name, or pattern you are about to create. If it exists, use it.
3. **Identify the module boundary.** What is this module's single responsibility? What does it hide?
4. **State the interface contract.** What does the caller need to know? Write the interface comment before the implementation.
5. **Identify the error conditions.** Can any be designed out of existence? For the rest, where is the single handling point?

---

## 6. The Post-Flight Protocol

After writing or modifying any code:

1. **Re-read as a stranger.** Can a developer unfamiliar with this code understand it without asking you a question?
2. **Check abstraction levels.** Does every function operate at one level? Does the Stepdown Rule hold?
3. **Verify the module graph.** No new circular dependencies. No new cross-layer violations.
4. **Verify the error contract.** Every error is either handled or propagated with context. No silent swallowing.
5. **Run the regression suite.** Confirm nothing existing is broken.
6. **Update documentation.** If any interface changed, update its comment. If any architectural decision changed, update the relevant doc. Commit messages are not documentation.

---

## 7. Anti-Patterns — Reject on Sight

| Pattern | Why It's Rejected |
|---|---|
| Empty catch blocks | Silent failure is worse than a crash |
| `null` / `undefined` returns where a collection or no-op would work | Shifts complexity to every caller |
| Global mutable state accessed without accessor functions | Untrackable mutation, untestable |
| `DB.getAll()` returning live cache references | Every caller becomes an unintentional co-owner |
| Multiple caches for the same data without a single source of truth | Guaranteed divergence |
| `entityType + 's'` to compute store names | English pluralization is not a function; use a lookup table |
| BroadcastChannel name strings without a shared constant | Typos are silent, permanent, and invisible |
| Optimistic mutation of shared references before async confirmation | Rollback cannot restore consistency |
| Sequential `await` in loops where `Promise.all` would work | Creates interleaving windows for stale-state bugs |
| Flag arguments (boolean parameters that fork behaviour) | The function does two things; split it |
| Commented-out code | Dead code in version control, not in source |
| "Fix later" without a tracked issue | "Fix never" |

---

## 8. Decision Records

When a decision is non-obvious or deviates from these principles, record it adjacent to the code:

```javascript
// DECISION: We use Math.round instead of Math.floor here because all inputs
// are guaranteed UTC midnight timestamps (see dateUtils contract). If this
// guarantee is ever relaxed, switch to Math.floor.
// Date: 2026-04-14 | Author: [initials]
```

Every decision record must state: what was decided, why, and under what conditions the decision should be revisited.

---

*This document is a living artifact. Update it when principles are refined, tensions are resolved, or new patterns emerge from production experience.*
