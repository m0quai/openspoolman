# URL split - Docker DNS fallback

No manual command is required.

Configured values remain:

    OPENSPOOLMAN_BASE_URL=http://localhost:8000
    SPOOLMAN_BASE_URL=http://localhost:7912
    SPOOLMAN_INTERNAL_BASE_URL=http://spoolman:8000

Runtime selection is automatic:

1. Native Windows/debugger:
   http://localhost:7912

2. Docker and `spoolman` resolves on the current Docker network:
   http://spoolman:8000

3. Docker but `spoolman` does NOT resolve:
   http://host.docker.internal:7912

The third case is the important fix for separate Compose projects/networks.
`host.docker.internal` is used only by the container for server-to-server
traffic; it is never used as a browser URL.

Missing config.env keys are still added automatically and existing values are
not overwritten.
