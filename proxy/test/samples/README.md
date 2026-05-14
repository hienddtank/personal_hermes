quarantine = automatically captured, not trusted yet
minimized = reduced reproductions
approved = regression fixtures used by pytest
rejected = kept for audit/debug, not used

Workflow:
1. Enable capture.
2. Run the proxy and trigger failures normally.
3. Inspect `proxy/test/samples/quarantine`.
4. Minimize useful samples.
5. Promote useful samples.
6. Run regression tests.

