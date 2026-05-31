# Future Improvements

Performance optimizations and architectural improvements identified during judgment day review but deferred for future iterations.

## Performance

### 1. Eviction Priority Inversion

**Current behavior**: When all locks are in use, eviction code `await`s inside the eviction lock. During this wait (potentially up to 127s = 4×30s timeout + 7s backoff), no other coroutine can create any new lock for any key.

**Impact**: Under high concurrency with `_max_locks=1000`, a single slow query can stall all new queries across all endpoints.

**Potential solutions**:
- Release the eviction lock before awaiting the oldest lock, then re-acquire and re-check
- Use a semaphore-based approach instead of OrderedDict eviction
- Implement a priority queue for lock creation requests

**Priority**: Low — Current implementation is correct and sufficient for expected load.

### 2. Connection Pooling

**Current behavior**: Each request creates a new SQLite connection via `database.connect()`.

**Impact**: Connection creation overhead on every request. SQLite has limited concurrency anyway, so pooling may not help much.

**Potential solutions**:
- Use `aiosqlite` with connection pooling
- Implement a simple connection pool with `queue.Queue`

**Priority**: Low — SQLite's write serialization limits concurrency regardless of connection strategy.

## Observability

### 3. Eviction Metrics

**Current behavior**: Lock eviction is a significant event (indicates resource pressure) but there's no logging or metrics.

**Potential solutions**:
- Add structured logging for eviction events
- Track eviction count and reasons in metrics
- Alert on high eviction rates

**Priority**: Medium — Useful for debugging production issues but not critical for MVP.

## Testing

### 4. Enhanced Integration Tests

**Current behavior**: Integration tests verify no exceptions and lock count bounds, but don't verify:
- No duplicate API calls for same cache key
- Cache hits occurred for duplicate keys
- Lock state validation during eviction

**Potential solutions**:
- Add assertions for API call counts
- Verify cache hit/miss ratios
- Add property-based testing for lock invariants

**Priority**: Low — Current tests catch correctness bugs, just not all edge cases.

## Architecture

### 5. Async Context Manager for Client

**Current behavior**: `DataforSEOClient` requires explicit `close()` calls.

**Potential solutions**:
- Implement `__aenter__` and `__aexit__` for safer resource management
- Use `async with DataforSEOClient(...) as client:` pattern

**Priority**: Low — Current `try/finally` pattern works correctly.

### 6. Reservation-Based Budget System

**Current behavior**: Budget check and record are atomic under lock, but API call happens between them.

**Potential solutions**:
- Implement optimistic reservation: reserve budget slot before API call, release if call fails
- Use database-level atomic operations instead of application-level locking

**Priority**: Low — Current implementation is correct and prevents overspend.

---

## Decision Log

**2026-05-31**: Judgment day completed after 6 rounds. All correctness bugs and security vulnerabilities resolved. Remaining issues are performance optimizations and defensive coding improvements that don't affect correctness.

**Verdict**: Code is production-ready. These improvements are nice-to-have but not required for MVP.
