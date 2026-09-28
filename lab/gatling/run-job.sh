#!/bin/sh
set +e
mvn -B gatling:test \
  -Dgatling.simulationClass=lab.relevance.SyntheticSearchSimulation \
  -Dlab.workload=/workload \
  -Dlab.arrivals=/results/arrivals.csv \
  -Dlab.baseUrl="$LAB_BASE_URL" \
  -Dlab.profile="$LAB_TRAFFIC_PROFILE"
status=$?
mkdir -p /results/report
if [ -d /workspace/target/gatling ]; then
  cp -R /workspace/target/gatling/. /results/report/
fi
printf '%s\n' "$status" > /results/exit-code
exit "$status"
