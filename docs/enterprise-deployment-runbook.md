# Enterprise Deployment Runbook

## Redis-Backed Distributed Rate Limiting

LumenAI supports distributed API rate limiting for multi-instance enterprise deployments. Single-node deployments can keep the default in-memory backend, but horizontally scaled API deployments should use Redis so counters are shared across workers and application instances.

### Configuration

| Variable | Description | Recommended production value |
| --- | --- | --- |
| `LUMENAI_RATE_LIMIT_BACKEND` | Rate limit store backend: `in_memory` or `redis` | `redis` for multi-instance production |
| `LUMENAI_REDIS_URL` | Redis connection URL used by the rate limit store | Managed Redis or HA Redis endpoint |
| `LUMENAI_REDIS_PREFIX` | Prefix for Redis keys | Environment-specific prefix such as `lumenai-prod` |
| `LUMENAI_REDIS_TIMEOUT_SECONDS` | Redis socket/connect timeout | Low value such as `1.0` to avoid request pileups |
| `LUMENAI_RATE_LIMIT_FAIL_MODE` | Redis failure behavior: `fallback` or `fail_closed` | Choose per customer risk tolerance |

### Deployment Requirements

- Use a dedicated Redis database, logical namespace, or key prefix for rate limiting.
- Require TLS and authentication when Redis is accessed outside a private trusted network.
- Restrict Redis network access to application instances and approved operators.
- Monitor Redis latency, connection errors, memory usage, evictions, and failover events.
- Keep Redis clocks and application clocks synchronized through the platform time service.

### High Availability Considerations

Redis-backed rate limiting protects against bypass through horizontal scaling because all workers increment the same counters. Enterprise deployments should use managed Redis, Redis Sentinel, or Redis Cluster according to the hosting environment's standard high-availability pattern.

Recommended HA posture:

- Use a managed Redis service with automatic failover where available.
- Configure connection timeouts so API requests fail quickly during Redis impairment.
- Use an environment-specific `LUMENAI_REDIS_PREFIX` to prevent key collisions between staging and production.
- Keep rate limit keys ephemeral and TTL-bound; do not persist them as business records.

### Failover Recommendations

Two fail modes are supported:

- `fallback`: if Redis is unavailable, use in-memory counters temporarily. This preserves availability but weakens distributed enforcement until Redis recovers.
- `fail_closed`: if Redis is unavailable, return HTTP 429. This preserves enforcement but may block legitimate traffic during Redis outages.

Recommended selection:

- Use `fallback` for lower-risk internal or pilot environments where availability is more important than strict distributed throttling.
- Use `fail_closed` for high-risk public authentication, export, or abuse-sensitive deployments when the customer accepts stricter availability tradeoffs.

Rate-limit violations should continue to create safe audit events such as `rate_limit_exceeded`, `abuse_detection`, or `auth_throttled` without logging secrets, bearer tokens, or sensitive payloads.
