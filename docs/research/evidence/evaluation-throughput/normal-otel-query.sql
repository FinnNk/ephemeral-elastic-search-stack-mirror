SELECT name,count() AS spans,countIf(has_error) AS errors,
 uniqExact(trace_id) AS traces,
 countIf(attributes_string['db.collection.name']='retail-gb-1m-v1') AS index_pins
FROM signoz_traces.signoz_index_v3
WHERE timestamp >= toDateTime('2026-10-02 05:30:00')
AND resources_string['service.version']='nexus.localhost:18185/search-api@sha256:90d3180aa108ba917c5b01948b7efa26d7bedd8400f4ff28f9203d47ac641340'
GROUP BY name FORMAT JSONEachRow
